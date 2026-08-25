"""Emisiones de escape reproducibles para E10, E15 y E20.

El módulo mantiene separados los controles agregados publicados y la
actualización abierta basada en la serie internacional de EIA.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class LogLinearFit:
    """Parámetros y diagnósticos de una tendencia log-lineal."""

    fit_start_year: int
    fit_end_year: int
    n_observations: int
    center_year: int
    intercept_at_center: float
    slope_per_year: float
    annual_growth_rate: float
    r_squared_log_scale: float
    rmse_log_scale: float

    def predict(self, year: int) -> float:
        """Predice energía en TJ para un año."""

        return math.exp(
            self.intercept_at_center
            + self.slope_per_year * (year - self.center_year)
        )


def load_config(repo_root: str | Path) -> dict[str, Any]:
    """Lee la configuración versionada del módulo."""

    path = Path(repo_root) / "03_configuracion" / "emisiones_ttw.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_eia_observations(
    repo_root: str | Path, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Carga y valida la serie EIA publicable declarada en configuración."""

    source_path = Path(repo_root) / config["source_csv"]
    observations: list[dict[str, Any]] = []
    metadata: dict[str, str] = {}
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "year",
            "energy_tj",
            "series_id",
            "series_name",
            "units",
            "source",
            "last_updated",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Columnas EIA requeridas ausentes en {source_path}")
        for row in reader:
            year = int(row["year"])
            if not (
                int(config["observed_start_year"])
                <= year
                <= int(config["observed_end_year"])
            ):
                continue
            energy_tj = float(row["energy_tj"])
            if not math.isfinite(energy_tj) or energy_tj <= 0:
                raise ValueError(f"Energía no positiva o no finita en {year}")
            if row["series_id"] != config["eia_series_id"]:
                raise ValueError(f"Identificador EIA inesperado en {year}")
            observations.append(
                {
                    "year": year,
                    "energy_tj": energy_tj,
                    "data_status": "observed",
                    "source_series_id": row["series_id"],
                }
            )
            if not metadata:
                metadata = {
                    "series_id": row["series_id"],
                    "name": row["series_name"],
                    "units": row["units"],
                    "source": row["source"],
                    "last_updated": row["last_updated"],
                }

    observations.sort(key=lambda row: int(row["year"]))
    expected_years = list(
        range(
            int(config["observed_start_year"]),
            int(config["observed_end_year"]) + 1,
        )
    )
    observed_years = [int(row["year"]) for row in observations]
    if observed_years != expected_years:
        raise ValueError(
            f"Cobertura EIA incompleta: {observed_years}; se esperaba {expected_years}"
        )
    return observations, metadata


def fit_log_linear(
    observations: list[dict[str, Any]], fit_start: int, fit_end: int
) -> LogLinearFit:
    """Ajusta OLS de log(energía) contra año con origen temporal centrado."""

    selected = [
        row for row in observations if fit_start <= int(row["year"]) <= fit_end
    ]
    expected_n = fit_end - fit_start + 1
    if len(selected) != expected_n:
        raise ValueError(
            f"La ventana requiere {expected_n} observaciones; se hallaron "
            f"{len(selected)}"
        )

    center_year = fit_start
    x_values = [int(row["year"]) - center_year for row in selected]
    y_values = [math.log(float(row["energy_tj"])) for row in selected]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    if denominator == 0:
        raise ValueError("La ventana de ajuste no tiene variación temporal")
    slope = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values)
    ) / denominator
    intercept = y_mean - slope * x_mean
    fitted = [intercept + slope * value for value in x_values]
    residuals = [actual - estimate for actual, estimate in zip(y_values, fitted)]
    ss_residual = sum(value**2 for value in residuals)
    ss_total = sum((value - y_mean) ** 2 for value in y_values)

    return LogLinearFit(
        fit_start_year=fit_start,
        fit_end_year=fit_end,
        n_observations=len(selected),
        center_year=center_year,
        intercept_at_center=intercept,
        slope_per_year=slope,
        annual_growth_rate=math.exp(slope) - 1.0,
        r_squared_log_scale=1.0 - ss_residual / ss_total if ss_total else 1.0,
        rmse_log_scale=math.sqrt(ss_residual / len(residuals)),
    )


def blend_metrics(blend_share: float, lhv_ratio: float) -> dict[str, float]:
    """Calcula la sustitución fósil manteniendo servicio energético."""

    if not 0.10 <= blend_share < 1.0:
        raise ValueError("La participación de mezcla debe estar entre 0.10 y 1")
    relative_blend_energy = (1.0 - blend_share) + blend_share * lhv_ratio
    fossil_emissions_factor = (1.0 - blend_share) / relative_blend_energy
    return {
        "relative_blend_energy": relative_blend_energy,
        "fossil_emissions_factor": fossil_emissions_factor,
        "ttw_reduction_fraction": 1.0 - fossil_emissions_factor,
    }


def _half_up_integer(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_published_reproduction(
    config: dict[str, Any]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Separa la reproducción E10 de las extensiones físicas superiores."""

    ratio = Decimal(str(config["ethanol_to_gasoline_lhv_ratio"]))
    published_rows: list[dict[str, Any]] = []
    extension_rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for control in config["published_controls"]:
        reference = Decimal(str(control["reference_co2_tonnes"]))
        for scenario_id, raw_share in config["blend_shares"].items():
            share = Decimal(str(raw_share))
            relative_energy = (Decimal("1") - share) + share * ratio
            fossil_factor = (Decimal("1") - share) / relative_energy
            scenario_value = _half_up_integer(reference * fossil_factor)
            avoided_value = int(reference) - scenario_value
            row = {
                "period_id": control["period_id"],
                "year_start": control["year_start"],
                "year_end": control["year_end"],
                "scenario_id": scenario_id,
                "blend_share": float(share),
                "relative_blend_energy": float(relative_energy),
                "fossil_emissions_factor": float(fossil_factor),
                "ttw_reduction_fraction": float(Decimal("1") - fossil_factor),
                "reference_co2_tonnes": int(reference),
                "scenario_co2_tonnes": scenario_value,
                "avoided_co2_tonnes": avoided_value,
                "control_status": "published" if scenario_id == "E10" else "derived",
            }
            if scenario_id == "E10":
                published_rows.append(row)
                for metric, computed, expected in (
                    (
                        "scenario_co2_tonnes",
                        scenario_value,
                        int(control["E10_co2_tonnes"]),
                    ),
                    (
                        "avoided_co2_tonnes",
                        avoided_value,
                        int(control["E10_avoided_co2_tonnes"]),
                    ),
                ):
                    checks.append(
                        {
                            "check_id": f"published_{control['period_id']}_{metric}",
                            "check_type": "exact_integer",
                            "computed": computed,
                            "expected": expected,
                            "difference": computed - expected,
                            "status": "PASS" if computed == expected else "FAIL",
                        }
                    )
            else:
                extension_rows.append(row)
    return published_rows, extension_rows, checks


def build_open_update(
    observations: list[dict[str, Any]],
    fit: LogLinearFit,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construye energía observada/proyectada y emisiones anuales por mezcla."""

    annual_energy = list(observations)
    for year in range(
        int(config["forecast_start_year"]), int(config["forecast_end_year"]) + 1
    ):
        annual_energy.append(
            {
                "year": year,
                "energy_tj": fit.predict(year),
                "data_status": "projected_log_linear",
                "source_series_id": config["eia_series_id"],
            }
        )

    factor = float(config["co2_factor_tonnes_per_tj"])
    lhv_ratio = float(config["ethanol_to_gasoline_lhv_ratio"])
    emissions_rows: list[dict[str, Any]] = []
    for energy_row in annual_energy:
        reference_co2 = float(energy_row["energy_tj"]) * factor
        for scenario_id, raw_share in config["blend_shares"].items():
            share = float(raw_share)
            metrics = blend_metrics(share, lhv_ratio)
            scenario_co2 = reference_co2 * metrics["fossil_emissions_factor"]
            emissions_rows.append(
                {
                    "year": energy_row["year"],
                    "data_status": energy_row["data_status"],
                    "source_series_id": energy_row["source_series_id"],
                    "scenario_id": scenario_id,
                    "blend_share": share,
                    "energy_tj": float(energy_row["energy_tj"]),
                    "co2_factor_tonnes_per_tj": factor,
                    "relative_blend_energy": metrics["relative_blend_energy"],
                    "fossil_emissions_factor": metrics["fossil_emissions_factor"],
                    "ttw_reduction_fraction": metrics["ttw_reduction_fraction"],
                    "reference_co2_tonnes": reference_co2,
                    "scenario_co2_tonnes": scenario_co2,
                    "avoided_co2_tonnes": reference_co2 - scenario_co2,
                }
            )
    return annual_energy, emissions_rows


def summarize_open_update(
    emissions_rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Agrega la actualización abierta en períodos de auditoría."""

    periods = (
        ("observed_1986_2023", 1986, 2023),
        ("observed_1986_2024", 1986, 2024),
        ("projected_2025_2030", 2025, 2030),
        ("projected_2026_2030", 2026, 2030),
    )
    summary: list[dict[str, Any]] = []
    for period_id, year_start, year_end in periods:
        for scenario_id in config["blend_shares"]:
            selected = [
                row
                for row in emissions_rows
                if row["scenario_id"] == scenario_id
                and year_start <= int(row["year"]) <= year_end
            ]
            summary.append(
                {
                    "period_id": period_id,
                    "year_start": year_start,
                    "year_end": year_end,
                    "scenario_id": scenario_id,
                    "blend_share": selected[0]["blend_share"],
                    "reference_co2_tonnes": sum(
                        float(row["reference_co2_tonnes"]) for row in selected
                    ),
                    "scenario_co2_tonnes": sum(
                        float(row["scenario_co2_tonnes"]) for row in selected
                    ),
                    "avoided_co2_tonnes": sum(
                        float(row["avoided_co2_tonnes"]) for row in selected
                    ),
                    "ttw_reduction_fraction": selected[0][
                        "ttw_reduction_fraction"
                    ],
                    "source_lineage": "EIA_open_update",
                }
            )
    return summary


def compare_lineages(
    open_summary: list[dict[str, Any]], published_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Cuantifica diferencias sin concatenar ni calibrar los dos linajes."""

    open_by_key = {
        (row["year_start"], row["year_end"], row["scenario_id"]): row
        for row in open_summary
    }
    comparisons: list[dict[str, Any]] = []
    for published in published_rows:
        key = (
            int(published["year_start"]),
            int(published["year_end"]),
            published["scenario_id"],
        )
        open_row = open_by_key.get(key)
        if open_row is None:
            continue
        published_reference = float(published["reference_co2_tonnes"])
        open_reference = float(open_row["reference_co2_tonnes"])
        comparisons.append(
            {
                "year_start": key[0],
                "year_end": key[1],
                "scenario_id": key[2],
                "published_reference_co2_tonnes": published_reference,
                "eia_reference_co2_tonnes": open_reference,
                "absolute_difference_tonnes": open_reference - published_reference,
                "relative_difference": open_reference / published_reference - 1.0,
                "interpretation": "different_source_lineage_not_a_reproduction_error",
            }
        )
    return comparisons


def build_checks(
    published_checks: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    annual_energy: list[dict[str, Any]],
    emissions_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Devuelve cuatro controles exactos y cinco controles estructurales."""

    checks = list(published_checks)

    def add_boolean(check_id: str, passed: bool, computed: Any, expected: Any) -> None:
        checks.append(
            {
                "check_id": check_id,
                "check_type": "boolean",
                "computed": computed,
                "expected": expected,
                "difference": "",
                "status": "PASS" if passed else "FAIL",
            }
        )

    observed_years = [int(row["year"]) for row in observations]
    expected_observed = list(
        range(
            int(config["observed_start_year"]),
            int(config["observed_end_year"]) + 1,
        )
    )
    add_boolean(
        "eia_observed_year_coverage",
        observed_years == expected_observed,
        f"{min(observed_years)}-{max(observed_years)}; n={len(observed_years)}",
        f"{expected_observed[0]}-{expected_observed[-1]}; n={len(expected_observed)}",
    )

    forecast_years = [
        int(row["year"])
        for row in annual_energy
        if row["data_status"] == "projected_log_linear"
    ]
    expected_forecast = list(
        range(
            int(config["forecast_start_year"]),
            int(config["forecast_end_year"]) + 1,
        )
    )
    add_boolean(
        "forecast_year_coverage",
        forecast_years == expected_forecast,
        forecast_years,
        expected_forecast,
    )

    observed_scenarios = sorted({row["scenario_id"] for row in emissions_rows})
    expected_scenarios = sorted(config["blend_shares"])
    add_boolean(
        "scenario_set",
        observed_scenarios == expected_scenarios,
        observed_scenarios,
        expected_scenarios,
    )

    minimum_share = min(float(value) for value in config["blend_shares"].values())
    add_boolean(
        "minimum_blend_share",
        minimum_share >= 0.10,
        minimum_share,
        ">=0.10",
    )
    all_positive = all(float(row["energy_tj"]) > 0 for row in annual_energy)
    add_boolean("positive_energy", all_positive, all_positive, True)
    return checks


def _write_csv(
    path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def run_emissions_pipeline(
    repo_root: str | Path,
    *,
    output_root: str | Path | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Ejecuta el flujo TTW y devuelve resultados aptos para el script maestro.

    `repo_root` identifica la fuente y configuración versionadas. Cuando se
    proporciona `output_root`, los derivados se escriben bajo esa raíz con la
    misma estructura de directorios; esto permite pruebas sin modificar el
    repositorio.
    """

    source_root = Path(repo_root).resolve()
    destination_root = (
        Path(output_root).resolve() if output_root is not None else source_root
    )
    config = load_config(source_root)
    observations, source_metadata = load_eia_observations(source_root, config)
    fit = fit_log_linear(
        observations,
        int(config["fit_start_year"]),
        int(config["fit_end_year"]),
    )
    published_rows, extension_rows, published_checks = (
        build_published_reproduction(config)
    )
    annual_energy, emissions_rows = build_open_update(observations, fit, config)
    open_summary = summarize_open_update(emissions_rows, config)
    comparisons = compare_lineages(open_summary, published_rows)
    checks = build_checks(
        published_checks, observations, annual_energy, emissions_rows, config
    )
    diagnostics = {
        "model": "ordinary_least_squares_on_log_energy",
        "equation": "ln(energy_tj) = intercept_at_center + slope_per_year * (year - center_year)",
        "retransformation": "exp_without_smearing_correction",
        "fit": asdict(fit),
        "source_metadata": source_metadata,
    }

    output_paths = {
        "processed_energy": destination_root
        / "01_datos"
        / "procesados"
        / "energia_gasolina_observada_y_proyectada_1986_2030.csv",
        "published_reproduction": destination_root
        / "06_resultados"
        / "emisiones"
        / "reproduccion_publicada.csv",
        "published_aggregate_extensions": destination_root
        / "06_resultados"
        / "emisiones"
        / "extensiones_mezclas_superiores.csv",
        "open_annual": destination_root
        / "06_resultados"
        / "emisiones"
        / "actualizacion_eia_anual.csv",
        "open_summary": destination_root
        / "06_resultados"
        / "emisiones"
        / "actualizacion_eia_resumen.csv",
        "lineage_comparison": destination_root
        / "06_resultados"
        / "emisiones"
        / "comparacion_linajes.csv",
        "checks": destination_root
        / "07_verificacion"
        / "controles_emisiones_ttw.csv",
        "forecast_diagnostics": destination_root
        / "07_verificacion"
        / "diagnostico_proyeccion_emisiones.json",
    }

    if write_outputs:
        _write_csv(
            output_paths["processed_energy"],
            annual_energy,
            ["year", "energy_tj", "data_status", "source_series_id"],
        )
        _write_csv(
            output_paths["published_reproduction"],
            published_rows,
            [
                "period_id",
                "year_start",
                "year_end",
                "scenario_id",
                "blend_share",
                "relative_blend_energy",
                "fossil_emissions_factor",
                "ttw_reduction_fraction",
                "reference_co2_tonnes",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
                "control_status",
            ],
        )
        _write_csv(
            output_paths["published_aggregate_extensions"],
            extension_rows,
            [
                "period_id",
                "year_start",
                "year_end",
                "scenario_id",
                "blend_share",
                "relative_blend_energy",
                "fossil_emissions_factor",
                "ttw_reduction_fraction",
                "reference_co2_tonnes",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
                "control_status",
            ],
        )
        _write_csv(
            output_paths["open_annual"],
            emissions_rows,
            [
                "year",
                "data_status",
                "source_series_id",
                "scenario_id",
                "blend_share",
                "energy_tj",
                "co2_factor_tonnes_per_tj",
                "relative_blend_energy",
                "fossil_emissions_factor",
                "ttw_reduction_fraction",
                "reference_co2_tonnes",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
            ],
        )
        _write_csv(
            output_paths["open_summary"],
            open_summary,
            [
                "period_id",
                "year_start",
                "year_end",
                "scenario_id",
                "blend_share",
                "reference_co2_tonnes",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
                "ttw_reduction_fraction",
                "source_lineage",
            ],
        )
        _write_csv(
            output_paths["lineage_comparison"],
            comparisons,
            [
                "year_start",
                "year_end",
                "scenario_id",
                "published_reference_co2_tonnes",
                "eia_reference_co2_tonnes",
                "absolute_difference_tonnes",
                "relative_difference",
                "interpretation",
            ],
        )
        _write_csv(
            output_paths["checks"],
            checks,
            [
                "check_id",
                "check_type",
                "computed",
                "expected",
                "difference",
                "status",
            ],
        )
        _write_json(output_paths["forecast_diagnostics"], diagnostics)

    failed = [row for row in checks if row["status"] != "PASS"]
    if failed:
        failed_ids = ", ".join(row["check_id"] for row in failed)
        raise RuntimeError(f"Fallaron controles de emisiones: {failed_ids}")

    return {
        "config": config,
        "fit": fit,
        "published_reproduction": published_rows,
        "published_aggregate_extensions": extension_rows,
        "annual_energy": annual_energy,
        "open_annual": emissions_rows,
        "open_summary": open_summary,
        "lineage_comparison": comparisons,
        "checks": checks,
        "diagnostics": diagnostics,
        "output_paths": output_paths,
    }


__all__ = [
    "LogLinearFit",
    "blend_metrics",
    "build_open_update",
    "build_published_reproduction",
    "fit_log_linear",
    "load_config",
    "load_eia_observations",
    "run_emissions_pipeline",
]
