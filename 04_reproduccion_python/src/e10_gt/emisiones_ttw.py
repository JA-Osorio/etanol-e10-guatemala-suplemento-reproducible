"""Emisiones de escape trazables para E10, E15 y E20.

Hay tres linajes que nunca se concatenan: (1) la reconstrucción anual del artículo
desde los outputs incrustados en un cuaderno privado, validada contra una copia
recuperada del libro primario, (2) los agregados publicados usados solo como
controles golden y (3) una actualización anual abierta basada en EIA. Los
identificadores de artefactos privados se omiten en la rama pública; el libro
primario no se redistribuye porque su procedencia estadística y licencia siguen
pendientes de documentación.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


FLOAT_TOLERANCE = 1e-12
EMISSIONS_BALANCE_TOLERANCE = 1e-8


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


def _sha256(path: Path) -> str:
    """Calcula SHA-256 por bloques para fijar el insumo observado."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_eia_observations(
    repo_root: str | Path, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carga y valida la serie EIA publicable declarada en configuración."""

    source_path = Path(repo_root) / config["source_csv"]
    source_sha256 = _sha256(source_path)
    expected_sha256 = str(config["source_sha256"])
    if source_sha256 != expected_sha256:
        raise ValueError(
            "SHA-256 inesperado para la serie EIA: "
            f"{source_sha256}; se esperaba {expected_sha256}"
        )
    observations: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}
    expected_metadata = config["source_metadata_expected"]
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
            observed_metadata = {
                "series_name": row["series_name"],
                "units": row["units"],
                "source": row["source"],
                "last_updated": row["last_updated"],
            }
            if observed_metadata != expected_metadata:
                raise ValueError(
                    f"Metadatos EIA inesperados en {year}: {observed_metadata}"
                )
            observations.append(
                {
                    "year": year,
                    "energy_tj": energy_tj,
                    "data_status": "observed",
                    "source_series_id": row["series_id"],
                    "source_lineage": "EIA_open_data_observed",
                }
            )
            if not metadata:
                metadata = {
                    "series_id": row["series_id"],
                    "name": row["series_name"],
                    "units": row["units"],
                    "source": row["source"],
                    "last_updated": row["last_updated"],
                    "source_csv": config["source_csv"],
                    "source_url": config["source_url"],
                    "source_sha256": source_sha256,
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
    metadata["row_count"] = len(observations)
    metadata["year_start"] = observed_years[0]
    metadata["year_end"] = observed_years[-1]
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


def load_recovered_article_history(
    repo_root: str | Path, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Carga las 38 observaciones recuperadas de los outputs Plotly del cuaderno.

    ``btu_recovered`` es una reconstrucción algebraica desde la curva E0
    incrustada. Sus 38 valores fueron contrastados con una copia recuperada del
    libro primario externo y coinciden al serializarlos con 15 cifras
    significativas. El hash fija exactamente el derivado forense versionado; el
    libro no se redistribuye porque su procedencia y licencia no están
    documentadas.
    """

    lineage = config["article_recovered_lineage"]
    source_path = Path(repo_root) / lineage["source_csv"]
    actual_sha256 = _sha256(source_path)
    expected_sha256 = lineage["source_csv_sha256"]
    if actual_sha256 != expected_sha256:
        raise ValueError(
            "SHA-256 inesperado para la serie recuperada del artículo: "
            f"{actual_sha256}; se esperaba {expected_sha256}"
        )

    required = {
        "year",
        "btu_recovered",
        "reference_co2_tonnes_notebook_output",
        "million_us_gallons_notebook_output",
        "value_status",
    }
    rows: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(
                f"Columnas de recuperación requeridas ausentes en {source_path}"
            )
        for raw in reader:
            year = int(raw["year"])
            row = {
                "year": year,
                "btu_recovered": float(raw["btu_recovered"]),
                "reference_co2_tonnes_notebook_output": float(
                    raw["reference_co2_tonnes_notebook_output"]
                ),
                "million_us_gallons_notebook_output": float(
                    raw["million_us_gallons_notebook_output"]
                ),
                "value_status": raw["value_status"],
            }
            if row["value_status"] != lineage["value_status"]:
                raise ValueError(f"Estado de recuperación inesperado en {year}")
            if any(
                not math.isfinite(float(row[field])) or float(row[field]) <= 0
                for field in (
                    "btu_recovered",
                    "reference_co2_tonnes_notebook_output",
                    "million_us_gallons_notebook_output",
                )
            ):
                raise ValueError(f"Valor recuperado no positivo o no finito en {year}")
            rows.append(row)

    rows.sort(key=lambda row: int(row["year"]))
    expected_years = list(
        range(
            int(lineage["observed_start_year"]),
            int(lineage["observed_end_year"]) + 1,
        )
    )
    actual_years = [int(row["year"]) for row in rows]
    if actual_years != expected_years:
        raise ValueError(
            f"Cobertura recuperada incompleta: {actual_years}; "
            f"se esperaba {expected_years}"
        )

    metadata = {
        "source_csv": lineage["source_csv"],
        "source_csv_sha256": actual_sha256,
        "value_status": lineage["value_status"],
        "row_count": len(rows),
        "year_start": actual_years[0],
        "year_end": actual_years[-1],
        "primary_notebook": lineage["primary_notebook"],
        "corroborating_notebook": lineage["corroborating_notebook"],
        "expected_workbook": lineage["expected_workbook"],
    }
    return rows, metadata


def build_recovered_article_counterfactual(
    history: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    LogLinearFit,
]:
    """Reconstruye las cuatro series del artículo y sus tres contextos.

    La serie base tiene 38 observaciones recuperadas y siete proyecciones
    log-lineales. El contexto prospectivo deja 2024-2025 en E0; la figura
    integrada original, en cambio, aplica E10 a los 45 años. El resumen del
    artículo agrega únicamente 1986-2023 y 2026-2030.
    """

    lineage = config["article_recovered_lineage"]
    btu_to_mj = float(lineage["btu_to_mj"])
    gasoline_lhv = float(lineage["gasoline_lhv_mj_per_liter"])
    ethanol_lhv = float(lineage["ethanol_lhv_mj_per_liter"])
    liter_to_us_gallon = float(lineage["liter_to_us_gallon"])
    blend_share = float(lineage["e10_volumetric_share"])
    co2_factor = float(lineage["co2_factor_tonnes_per_tj"])
    rho = ethanol_lhv / gasoline_lhv
    reduction = blend_metrics(blend_share, rho)["ttw_reduction_fraction"]

    series_rows: list[dict[str, Any]] = []
    fit_input: list[dict[str, Any]] = []
    for source in history:
        energy_tj = float(source["btu_recovered"]) * btu_to_mj / 1e6
        row = {
            "year": int(source["year"]),
            "data_status": "recovered_notebook_output",
            "source_lineage": "article_notebook_recovered",
            "btu": float(source["btu_recovered"]),
            "energy_tj": energy_tj,
            "million_us_gallons": (
                energy_tj * liter_to_us_gallon / gasoline_lhv
            ),
            "reference_co2_tonnes": energy_tj * co2_factor,
            "value_status": source["value_status"],
        }
        series_rows.append(row)
        fit_input.append({"year": row["year"], "energy_tj": energy_tj})

    fit = fit_log_linear(
        fit_input,
        int(lineage["fit_start_year"]),
        int(lineage["fit_end_year"]),
    )
    for year in range(
        int(lineage["forecast_start_year"]),
        int(lineage["forecast_end_year"]) + 1,
    ):
        energy_tj = fit.predict(year)
        series_rows.append(
            {
                "year": year,
                "data_status": "projected_log_linear_2014_2023",
                "source_lineage": "article_notebook_recovered",
                "btu": energy_tj * 1e6 / btu_to_mj,
                "energy_tj": energy_tj,
                "million_us_gallons": (
                    energy_tj * liter_to_us_gallon / gasoline_lhv
                ),
                "reference_co2_tonnes": energy_tj * co2_factor,
                "value_status": (
                    "recalculated_and_checked_against_embedded_notebook_"
                    "plotly_output"
                ),
            }
        )

    def context_rows(
        context: str,
        selected: list[dict[str, Any]],
        share_for_year: Any,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for base in selected:
            applied_share = float(share_for_year(int(base["year"])))
            applied_reduction = reduction if applied_share == blend_share else 0.0
            reference = float(base["reference_co2_tonnes"])
            scenario_value = reference * (1.0 - applied_reduction)
            rows.append(
                {
                    **base,
                    "scenario_context": context,
                    "scenario_id": "E10" if applied_share else "E0",
                    "blend_share_applied": applied_share,
                    "scenario_co2_tonnes": scenario_value,
                    "avoided_co2_tonnes": reference - scenario_value,
                }
            )
        return rows

    observed_end = int(lineage["observed_end_year"])
    policy_start = int(lineage["policy_start_year"])
    historical = [row for row in series_rows if int(row["year"]) <= observed_end]
    prospective = [row for row in series_rows if int(row["year"]) > observed_end]
    counterfactual_rows = context_rows(
        "historical_counterfactual_1986_2023",
        historical,
        lambda _year: blend_share,
    )
    counterfactual_rows.extend(
        context_rows(
            "prospective_policy_2024_2030",
            prospective,
            lambda year: blend_share if year >= policy_start else 0.0,
        )
    )
    counterfactual_rows.extend(
        context_rows(
            "integrated_figure_1986_2030",
            series_rows,
            lambda _year: blend_share,
        )
    )

    by_context = {
        context: [
            row
            for row in counterfactual_rows
            if row["scenario_context"] == context
        ]
        for context in (
            "historical_counterfactual_1986_2023",
            "prospective_policy_2024_2030",
            "integrated_figure_1986_2030",
        )
    }
    summary_specs = (
        (
            "historical_1986_2023",
            by_context["historical_counterfactual_1986_2023"],
            "1986-2023",
            "",
        ),
        (
            "prospective_2026_2030",
            [
                row
                for row in by_context["prospective_policy_2024_2030"]
                if int(row["year"]) >= policy_start
            ],
            "2026-2030",
            "",
        ),
    )
    summary_rows: list[dict[str, Any]] = []
    for period_id, selected, coverage, excluded in summary_specs:
        reference = sum(float(row["reference_co2_tonnes"]) for row in selected)
        scenario_value = sum(float(row["scenario_co2_tonnes"]) for row in selected)
        avoided = sum(float(row["avoided_co2_tonnes"]) for row in selected)
        summary_rows.append(
            {
                "period_id": period_id,
                "year_coverage": coverage,
                "excluded_years": excluded,
                "n_years": len(selected),
                "reference_co2_tonnes": reference,
                "scenario_co2_tonnes": scenario_value,
                "avoided_co2_tonnes": avoided,
                "reference_co2_tonnes_rounded": round_half_up_integer(
                    Decimal(str(reference))
                ),
                "scenario_co2_tonnes_rounded": round_half_up_integer(
                    Decimal(str(scenario_value))
                ),
                "avoided_co2_tonnes_rounded": round_half_up_integer(
                    Decimal(str(avoided))
                ),
                "source_lineage": "article_notebook_recovered",
                "calculation_scope": "annual_reconstruction_from_notebook_outputs",
            }
        )

    historical_summary, prospective_summary = summary_rows
    summary_rows.append(
        {
            "period_id": "reported_periods_combined_excluding_2024_2025",
            "year_coverage": "1986-2023|2026-2030",
            "excluded_years": "2024|2025",
            "n_years": int(historical_summary["n_years"])
            + int(prospective_summary["n_years"]),
            "reference_co2_tonnes": float(
                historical_summary["reference_co2_tonnes"]
            )
            + float(prospective_summary["reference_co2_tonnes"]),
            "scenario_co2_tonnes": float(
                historical_summary["scenario_co2_tonnes"]
            )
            + float(prospective_summary["scenario_co2_tonnes"]),
            "avoided_co2_tonnes": float(
                historical_summary["avoided_co2_tonnes"]
            )
            + float(prospective_summary["avoided_co2_tonnes"]),
            "reference_co2_tonnes_rounded": int(
                historical_summary["reference_co2_tonnes_rounded"]
            )
            + int(prospective_summary["reference_co2_tonnes_rounded"]),
            "scenario_co2_tonnes_rounded": int(
                historical_summary["scenario_co2_tonnes_rounded"]
            )
            + int(prospective_summary["scenario_co2_tonnes_rounded"]),
            "avoided_co2_tonnes_rounded": int(
                historical_summary["avoided_co2_tonnes_rounded"]
            )
            + int(prospective_summary["avoided_co2_tonnes_rounded"]),
            "source_lineage": "article_notebook_recovered",
            "calculation_scope": "disjoint_reported_periods_not_continuous_1986_2030",
        }
    )
    return series_rows, counterfactual_rows, summary_rows, fit


def build_recovered_article_checks(
    history: list[dict[str, Any]],
    source_metadata: dict[str, Any],
    series_rows: list[dict[str, Any]],
    counterfactual_rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    fit: LogLinearFit,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Verifica procedencia, round-trips, contextos y goldens del artículo."""

    lineage = config["article_recovered_lineage"]
    checks: list[dict[str, Any]] = []

    def add_boolean(
        check_id: str, passed: bool, computed: Any, expected: Any, evidence: str
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "check_type": "boolean",
                "computed": computed,
                "expected": expected,
                "difference": "",
                "tolerance": 0,
                "scope": "article_notebook_recovered",
                "evidence": evidence,
                "status": "PASS" if passed else "FAIL",
            }
        )

    def add_numeric(
        check_id: str,
        computed: float,
        expected: float,
        tolerance: float,
        evidence: str,
    ) -> None:
        difference = computed - expected
        checks.append(
            {
                "check_id": check_id,
                "check_type": "absolute_tolerance",
                "computed": computed,
                "expected": expected,
                "difference": difference,
                "tolerance": tolerance,
                "scope": "article_notebook_recovered",
                "evidence": evidence,
                "status": "PASS" if abs(difference) <= tolerance else "FAIL",
            }
        )

    add_boolean(
        "article_recovered_source_sha256",
        source_metadata["source_csv_sha256"] == lineage["source_csv_sha256"],
        source_metadata["source_csv_sha256"],
        lineage["source_csv_sha256"],
        lineage["source_csv"],
    )
    primary = lineage["primary_notebook"]
    corroborating = lineage["corroborating_notebook"]
    private_identifiers_sanitized = all(
        item["original_sha256"] == "omitido_en_rama_publica"
        and item["drive_file_id"] == "omitido_en_rama_publica"
        and item["publicacion_identificadores"] == "sanitizada"
        and item["stored_in_repository"] is False
        for item in (primary, corroborating)
    )
    add_boolean(
        "article_private_notebook_identifiers_sanitized",
        private_identifiers_sanitized,
        private_identifiers_sanitized,
        True,
        "private notebook IDs and binary hashes are omitted from the public branch",
    )
    workbook = lineage["expected_workbook"]
    add_boolean(
        "article_primary_workbook_copy_recovered",
        workbook["recovery_status"] == "recovered_external_copy_verified",
        workbook["recovery_status"],
        "recovered_external_copy_verified",
        "an external workbook copy was recovered and computationally verified",
    )
    add_boolean(
        "article_primary_workbook_identifier_sanitized",
        "sha256" not in workbook
        and workbook["identifier_status"]
        == "omitted_in_public_review_branch",
        workbook["identifier_status"],
        "omitted_in_public_review_branch",
        "the external workbook identifier is retained only in the local full audit",
    )
    cross_validation = workbook["cross_validation"]
    add_boolean(
        "article_primary_workbook_cross_validation_complete",
        all(
            int(cross_validation[field]) == int(workbook["row_count"])
            for field in (
                "matched_btu_rows",
                "matched_reference_co2_rows",
                "matched_million_us_gallons_rows",
            )
        ),
        (
            f"BTU={cross_validation['matched_btu_rows']}; "
            f"CO2={cross_validation['matched_reference_co2_rows']}; "
            f"volume={cross_validation['matched_million_us_gallons_rows']}"
        ),
        f"{workbook['row_count']} matches for each series",
        "comparison against recovered Plotly arrays at 15 significant digits",
    )
    add_boolean(
        "article_primary_workbook_not_redistributed_without_license",
        workbook["stored_in_repository"] is False
        and workbook["redistribution_allowed"] is False
        and workbook["source_provenance_status"]
        == "source_provenance_and_license_pending",
        (
            f"stored={workbook['stored_in_repository']}; "
            f"redistribution={workbook['redistribution_allowed']}; "
            f"status={workbook['source_provenance_status']}"
        ),
        "stored=False; redistribution=False; source_provenance_and_license_pending",
        "computational verification does not establish statistical provenance or license",
    )

    expected_history_years = list(
        range(
            int(lineage["observed_start_year"]),
            int(lineage["observed_end_year"]) + 1,
        )
    )
    actual_history_years = [int(row["year"]) for row in history]
    add_boolean(
        "article_history_coverage_unique",
        actual_history_years == expected_history_years,
        f"{actual_history_years[0]}-{actual_history_years[-1]}; n={len(actual_history_years)}",
        f"{expected_history_years[0]}-{expected_history_years[-1]}; n={len(expected_history_years)}",
        "38 consecutive x values embedded in the retrospective Plotly output",
    )

    history_by_year = {int(row["year"]): row for row in history}
    series_by_year = {int(row["year"]): row for row in series_rows}
    base_roundtrip = []
    volume_roundtrip = []
    btu_relative_roundtrip = []
    btu_to_mj = float(lineage["btu_to_mj"])
    co2_factor = float(lineage["co2_factor_tonnes_per_tj"])
    for year, source in history_by_year.items():
        calculated = series_by_year[year]
        recovered_base = float(source["reference_co2_tonnes_notebook_output"])
        recovered_btu = float(source["btu_recovered"])
        base_roundtrip.append(
            abs(float(calculated["reference_co2_tonnes"]) - recovered_base)
        )
        volume_roundtrip.append(
            abs(
                float(calculated["million_us_gallons"])
                - float(source["million_us_gallons_notebook_output"])
            )
        )
        inverted_btu = recovered_base * 1e6 / (co2_factor * btu_to_mj)
        btu_relative_roundtrip.append(abs(inverted_btu / recovered_btu - 1.0))
    add_numeric(
        "article_roundtrip_BTU_to_C0",
        max(base_roundtrip, default=0.0),
        0.0,
        1e-7,
        "max |BTU * 0.001055056 / 1e6 * 69.3 - embedded C0| tonnes",
    )
    add_numeric(
        "article_roundtrip_BTU_to_million_us_gallons",
        max(volume_roundtrip, default=0.0),
        0.0,
        1e-9,
        "max volume residual against the embedded Plotly series",
    )
    add_numeric(
        "article_roundtrip_C0_to_BTU_relative",
        max(btu_relative_roundtrip, default=0.0),
        0.0,
        2e-14,
        "inverse forensic reconstruction from embedded C0",
    )

    expected_all_years = list(
        range(
            int(lineage["observed_start_year"]),
            int(lineage["forecast_end_year"]) + 1,
        )
    )
    actual_all_years = [int(row["year"]) for row in series_rows]
    add_boolean(
        "article_series_coverage_unique",
        actual_all_years == expected_all_years,
        f"{actual_all_years[0]}-{actual_all_years[-1]}; n={len(actual_all_years)}",
        f"{expected_all_years[0]}-{expected_all_years[-1]}; n={len(expected_all_years)}",
        "38 recovered observations plus 7 recalculated projections",
    )

    actual_fit = asdict(fit)
    for field, expected in lineage["golden_log_linear_fit_recalculated"].items():
        computed = actual_fit[field]
        if isinstance(expected, int):
            add_boolean(
                f"article_golden_fit_{field}",
                computed == expected,
                computed,
                expected,
                "centered log-energy form equivalent to notebook log-liters OLS, 2014-2023",
            )
        else:
            add_numeric(
                f"article_golden_fit_{field}",
                float(computed),
                float(expected),
                FLOAT_TOLERANCE,
                "centered log-energy form equivalent to notebook log-liters OLS, 2014-2023",
            )

    golden_projection = lineage["golden_projection_notebook_outputs"]
    prospective_policy = {
        str(row["year"]): row
        for row in counterfactual_rows
        if row["scenario_context"] == "prospective_policy_2024_2030"
    }
    projection_base_residuals = []
    projection_volume_residuals = []
    projection_scenario_residuals = []
    for year, expected in golden_projection.items():
        calculated = series_by_year[int(year)]
        policy_row = prospective_policy[year]
        projection_base_residuals.append(
            abs(
                float(calculated["reference_co2_tonnes"])
                - float(expected["reference_co2_tonnes"])
            )
        )
        projection_volume_residuals.append(
            abs(
                float(calculated["million_us_gallons"])
                - float(expected["million_us_gallons"])
            )
        )
        projection_scenario_residuals.append(
            abs(
                float(policy_row["scenario_co2_tonnes"])
                - float(expected["scenario_co2_tonnes_policy_context"])
            )
        )
    add_numeric(
        "article_golden_projection_C0",
        max(projection_base_residuals, default=0.0),
        0.0,
        1e-3,
        "maximum residual against Plotly prospective E0 y-values",
    )
    add_numeric(
        "article_golden_projection_million_us_gallons",
        max(projection_volume_residuals, default=0.0),
        0.0,
        1e-8,
        "maximum residual against Plotly volume y-values",
    )
    add_numeric(
        "article_golden_projection_policy_scenario",
        max(projection_scenario_residuals, default=0.0),
        0.0,
        1e-3,
        "maximum residual against Plotly prospective scenario y-values",
    )

    context_expected_years = {
        "historical_counterfactual_1986_2023": set(range(1986, 2024)),
        "prospective_policy_2024_2030": set(range(2024, 2031)),
        "integrated_figure_1986_2030": set(range(1986, 2031)),
    }
    keys = [
        (str(row["scenario_context"]), int(row["year"]))
        for row in counterfactual_rows
    ]
    actual_context_years = {
        context: {
            int(row["year"])
            for row in counterfactual_rows
            if row["scenario_context"] == context
        }
        for context in context_expected_years
    }
    add_boolean(
        "article_context_year_coverage_unique",
        actual_context_years == context_expected_years
        and len(keys) == len(set(keys)) == 90,
        {key: len(value) for key, value in actual_context_years.items()},
        {key: len(value) for key, value in context_expected_years.items()},
        "38 historical + 7 prospective + 45 integrated rows",
    )
    policy_2024_2025 = [
        row
        for row in counterfactual_rows
        if row["scenario_context"] == "prospective_policy_2024_2030"
        and int(row["year"]) in (2024, 2025)
    ]
    integrated_2024_2025 = [
        row
        for row in counterfactual_rows
        if row["scenario_context"] == "integrated_figure_1986_2030"
        and int(row["year"]) in (2024, 2025)
    ]
    add_boolean(
        "article_2024_2025_context_difference_explicit",
        all(float(row["blend_share_applied"]) == 0.0 for row in policy_2024_2025)
        and all(
            float(row["blend_share_applied"]) == 0.1
            for row in integrated_2024_2025
        ),
        "policy=E0; integrated=E10",
        "policy=E0; integrated=E10",
        "the original prospective and integrated figures use different context rules",
    )
    expected_share = float(lineage["e10_volumetric_share"])
    policy_application_ok = all(
        float(row["blend_share_applied"])
        == (expected_share if int(row["year"]) >= 2026 else 0.0)
        for row in prospective_policy.values()
    )
    add_boolean(
        "article_policy_application_2026",
        policy_application_ok,
        policy_application_ok,
        True,
        "E0 in 2024-2025 and E10 in 2026-2030",
    )

    balance_residuals = [
        abs(
            float(row["reference_co2_tonnes"])
            - float(row["scenario_co2_tonnes"])
            - float(row["avoided_co2_tonnes"])
        )
        for row in counterfactual_rows
    ]
    add_numeric(
        "article_annual_balance_C0_Cs_A",
        max(balance_residuals, default=0.0),
        0.0,
        EMISSIONS_BALANCE_TOLERANCE,
        "all three contexts: C0 = Cs + A",
    )

    summary_by_id = {row["period_id"]: row for row in summary_rows}
    historical_summary = summary_by_id["historical_1986_2023"]
    golden_historical = lineage["golden_historical_notebook_totals"]
    for field in (
        "reference_co2_tonnes",
        "scenario_co2_tonnes",
        "avoided_co2_tonnes",
    ):
        add_numeric(
            f"article_golden_historical_{field}",
            float(historical_summary[field]),
            float(golden_historical[field]),
            1e-5,
            "sum of the 38 retrospective Plotly values",
        )

    control_by_period = {
        row["period_id"]: row for row in config["published_controls"]
    }
    metric_mapping = (
        ("C0", "reference_co2_tonnes_rounded", "reference_co2_tonnes"),
        ("C10", "scenario_co2_tonnes_rounded", "E10_co2_tonnes"),
        ("A", "avoided_co2_tonnes_rounded", "E10_avoided_co2_tonnes"),
    )
    for period_id in ("historical_1986_2023", "prospective_2026_2030"):
        summary = summary_by_id[period_id]
        control = control_by_period[period_id]
        for metric_id, summary_field, control_field in metric_mapping:
            computed = int(summary[summary_field])
            expected = int(control[control_field])
            add_boolean(
                f"article_annual_{period_id}_row_{metric_id}",
                computed == expected,
                computed,
                expected,
                "annual reconstruction rounded half-up versus published table",
            )

    combined = summary_by_id[
        "reported_periods_combined_excluding_2024_2025"
    ]
    add_boolean(
        "article_summary_gap_2024_2025",
        combined["year_coverage"] == "1986-2023|2026-2030"
        and combined["excluded_years"] == "2024|2025"
        and int(combined["n_years"]) == 43,
        (
            combined["year_coverage"],
            combined["excluded_years"],
            combined["n_years"],
        ),
        ("1986-2023|2026-2030", "2024|2025", 43),
        "published total is a disjoint union, not a continuous 1986-2030 sum",
    )
    integrated_rows = [
        row
        for row in counterfactual_rows
        if row["scenario_context"] == "integrated_figure_1986_2030"
    ]
    integrated_totals = {
        field: sum(float(row[field]) for row in integrated_rows)
        for field in (
            "reference_co2_tonnes",
            "scenario_co2_tonnes",
            "avoided_co2_tonnes",
        )
    }
    golden_integrated = lineage["golden_integrated_figure_notebook_totals"]
    for field, expected in golden_integrated.items():
        add_numeric(
            f"article_golden_integrated_figure_{field}",
            integrated_totals[field],
            float(expected),
            1e-3,
            "sum of the 45 values embedded in the integrated Plotly figure",
        )
    integrated_minus_disjoint = (
        integrated_totals["avoided_co2_tonnes"]
        - float(combined["avoided_co2_tonnes"])
    )
    add_numeric(
        "article_integrated_minus_reported_disjoint_avoided",
        integrated_minus_disjoint,
        float(
            lineage[
                "golden_integrated_minus_reported_disjoint_avoided_co2_tonnes"
            ]
        ),
        1e-3,
        "the 929,824.8 t difference is the integrated E10 treatment of 2024-2025",
    )
    return checks


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


def round_half_up_integer(value: Decimal) -> int:
    """Redondea a tonelada entera con la regla explícita ``ROUND_HALF_UP``."""

    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_published_aggregate_reconciliation(
    config: dict[str, Any]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Concilia los agregados E10 y separa extensiones no publicadas.

    Los totales de referencia son entradas reportadas, no sumas reconstruidas
    desde observaciones anuales. Por ello la salida se etiqueta expresamente
    como conciliación aritmética agregada.
    """

    ratio = Decimal(str(config["ethanol_to_gasoline_lhv_ratio"]))
    lineage = config["published_aggregate_lineage"]
    published_rows: list[dict[str, Any]] = []
    extension_rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for control in config["published_controls"]:
        reference = Decimal(str(control["reference_co2_tonnes"]))
        for scenario_id, raw_share in config["blend_shares"].items():
            share = Decimal(str(raw_share))
            relative_energy = (Decimal("1") - share) + share * ratio
            fossil_factor = (Decimal("1") - share) / relative_energy
            scenario_value = round_half_up_integer(reference * fossil_factor)
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
                "control_status": (
                    "published_aggregate_control"
                    if scenario_id == "E10"
                    else "derived_not_published"
                ),
                "calculation_scope": lineage["calculation_scope"],
                "source_lineage": "manuscript_reported_aggregate_totals",
                "annual_reproduction_status": lineage[
                    "annual_reproduction_status"
                ],
                "rho_provenance": config["lhv_ratio_provenance"],
                "rounding_method": lineage["rounding_method"],
            }
            if scenario_id == "E10":
                published_rows.append(row)
                for metric_id, metric, computed, expected in (
                    (
                        "C0",
                        "reference_co2_tonnes",
                        int(reference),
                        int(control["reference_co2_tonnes"]),
                    ),
                    (
                        "C10",
                        "scenario_co2_tonnes",
                        scenario_value,
                        int(control["E10_co2_tonnes"]),
                    ),
                    (
                        "A",
                        "avoided_co2_tonnes",
                        avoided_value,
                        int(control["E10_avoided_co2_tonnes"]),
                    ),
                ):
                    checks.append(
                        {
                            "check_id": (
                                f"published_aggregate_{control['period_id']}_"
                                f"row_{metric_id}"
                            ),
                            "check_type": "exact_integer",
                            "computed": computed,
                            "expected": expected,
                            "difference": computed - expected,
                            "tolerance": 0,
                            "scope": "aggregate_arithmetic_reconciliation_only",
                            "evidence": metric,
                            "status": "PASS" if computed == expected else "FAIL",
                        }
                    )
            else:
                extension_rows.append(row)
    return published_rows, extension_rows, checks


def build_published_reproduction(
    config: dict[str, Any]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """Alias compatible; el alcance real es conciliación aritmética agregada."""

    return build_published_aggregate_reconciliation(config)


def build_open_update(
    observations: list[dict[str, Any]],
    fit: LogLinearFit,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construye energía observada/proyectada y emisiones anuales por mezcla."""

    annual_energy = [dict(row) for row in observations]
    for year in range(
        int(config["forecast_start_year"]), int(config["forecast_end_year"]) + 1
    ):
        annual_energy.append(
            {
                "year": year,
                "energy_tj": fit.predict(year),
                "data_status": "projected_log_linear",
                "source_series_id": config["eia_series_id"],
                "source_lineage": "EIA_open_data_log_linear_projection",
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
                    "source_lineage": energy_row["source_lineage"],
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
            expected_years = year_end - year_start + 1
            if len(selected) != expected_years:
                raise ValueError(
                    f"Cobertura incompleta en {period_id}/{scenario_id}: "
                    f"{len(selected)} filas; se esperaban {expected_years}"
                )
            summary.append(
                {
                    "period_id": period_id,
                    "year_start": year_start,
                    "year_end": year_end,
                    "scenario_id": scenario_id,
                    "blend_share": selected[0]["blend_share"],
                    "n_years": len(selected),
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
                    "source_lineage": "EIA_open_data_separate_lineage",
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
    open_summary: list[dict[str, Any]],
    published_rows: list[dict[str, Any]],
    extension_rows: list[dict[str, Any]],
    fit: LogLinearFit,
    source_metadata: dict[str, Any],
    article_series: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Construye controles numéricos, estructurales y de procedencia."""

    checks = list(published_checks)

    def add_boolean(
        check_id: str,
        passed: bool,
        computed: Any,
        expected: Any,
        *,
        scope: str,
        evidence: str,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "check_type": "boolean",
                "computed": computed,
                "expected": expected,
                "difference": "",
                "tolerance": 0,
                "scope": scope,
                "evidence": evidence,
                "status": "PASS" if passed else "FAIL",
            }
        )

    def add_numeric(
        check_id: str,
        computed: float,
        expected: float,
        tolerance: float,
        *,
        scope: str,
        evidence: str,
    ) -> None:
        difference = computed - expected
        checks.append(
            {
                "check_id": check_id,
                "check_type": "absolute_tolerance",
                "computed": computed,
                "expected": expected,
                "difference": difference,
                "tolerance": tolerance,
                "scope": scope,
                "evidence": evidence,
                "status": "PASS" if abs(difference) <= tolerance else "FAIL",
            }
        )

    # Procedencia de la fuente abierta: hash, metadatos y cobertura.
    add_boolean(
        "eia_source_sha256",
        source_metadata["source_sha256"] == config["source_sha256"],
        source_metadata["source_sha256"],
        config["source_sha256"],
        scope="EIA_open_update",
        evidence=config["source_csv"],
    )
    add_boolean(
        "eia_series_id",
        source_metadata["series_id"] == config["eia_series_id"],
        source_metadata["series_id"],
        config["eia_series_id"],
        scope="EIA_open_update",
        evidence="source_metadata.series_id",
    )
    expected_metadata = config["source_metadata_expected"]
    actual_metadata = {
        "series_name": source_metadata["name"],
        "units": source_metadata["units"],
        "source": source_metadata["source"],
        "last_updated": source_metadata["last_updated"],
    }
    add_boolean(
        "eia_source_metadata",
        actual_metadata == expected_metadata,
        actual_metadata,
        expected_metadata,
        scope="EIA_open_update",
        evidence="all source rows validated while loading",
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
        scope="EIA_open_update",
        evidence="observed annual rows",
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
        scope="EIA_open_update",
        evidence="log-linear projected rows",
    )
    observed_set = set(observed_years)
    forecast_set = set(forecast_years)
    add_boolean(
        "observed_forecast_years_disjoint",
        observed_set.isdisjoint(forecast_set),
        sorted(observed_set & forecast_set),
        [],
        scope="EIA_open_update",
        evidence="observed and projected statuses must not overlap",
    )
    all_energy_years = [int(row["year"]) for row in annual_energy]
    expected_all_years = list(
        range(
            int(config["observed_start_year"]),
            int(config["forecast_end_year"]) + 1,
        )
    )
    add_boolean(
        "annual_energy_unique_complete_years",
        all_energy_years == expected_all_years,
        f"{min(all_energy_years)}-{max(all_energy_years)}; n={len(all_energy_years)}",
        f"{expected_all_years[0]}-{expected_all_years[-1]}; n={len(expected_all_years)}",
        scope="EIA_open_update",
        evidence="one energy row per year",
    )

    observed_scenarios = sorted({row["scenario_id"] for row in emissions_rows})
    expected_scenarios = sorted(config["blend_shares"])
    add_boolean(
        "scenario_set",
        observed_scenarios == expected_scenarios,
        observed_scenarios,
        expected_scenarios,
        scope="EIA_open_update",
        evidence="scenario_id values",
    )
    year_scenario_keys = [
        (int(row["year"]), str(row["scenario_id"])) for row in emissions_rows
    ]
    expected_row_count = len(expected_all_years) * len(expected_scenarios)
    add_boolean(
        "unique_year_scenario_rows",
        len(year_scenario_keys) == len(set(year_scenario_keys))
        and len(year_scenario_keys) == expected_row_count,
        f"unique={len(set(year_scenario_keys))}; rows={len(year_scenario_keys)}",
        f"unique={expected_row_count}; rows={expected_row_count}",
        scope="EIA_open_update",
        evidence="year x scenario_id primary key",
    )

    minimum_share = min(float(value) for value in config["blend_shares"].values())
    add_boolean(
        "minimum_blend_share",
        minimum_share >= 0.10,
        minimum_share,
        ">=0.10",
        scope="all_scenarios",
        evidence="blend_shares configuration",
    )
    all_positive = all(float(row["energy_tj"]) > 0 for row in annual_energy)
    add_boolean(
        "positive_energy",
        all_positive,
        all_positive,
        True,
        scope="EIA_open_update",
        evidence="observed and projected energy_tj",
    )

    # rho proviene explícitamente de 21.1/32.0 en el cuaderno recuperado.
    rho = float(config["ethanol_to_gasoline_lhv_ratio"])
    rho_trace = config["rho_parameter_provenance"]
    inferred_rho = float(rho_trace["ethanol_lhv_mj_per_liter"]) / float(
        rho_trace["gasoline_lhv_mj_per_liter"]
    )
    add_numeric(
        "rho_notebook_parameter_ratio",
        inferred_rho,
        rho,
        FLOAT_TOLERANCE,
        scope="physical_model_recovered_notebook",
        evidence=rho_trace["equation"],
    )
    add_boolean(
        "rho_not_independent_empirical_input",
        rho_trace["independent_empirical_input"] is False,
        rho_trace["independent_empirical_input"],
        False,
        scope="physical_model_recovered_notebook",
        evidence=config["lhv_ratio_provenance"],
    )

    # Identidades físicas r(s), F(s) y d(s) para cada mezcla.
    for scenario_id, raw_share in config["blend_shares"].items():
        share = float(raw_share)
        metrics = blend_metrics(share, rho)
        relative_energy = (1.0 - share) + share * rho
        fossil_factor = (1.0 - share) / relative_energy
        reduction = 1.0 - fossil_factor
        add_numeric(
            f"identity_r_{scenario_id}",
            metrics["relative_blend_energy"],
            relative_energy,
            FLOAT_TOLERANCE,
            scope="all_scenarios",
            evidence="r(s) = (1-s) + s*rho",
        )
        add_numeric(
            f"identity_F_{scenario_id}",
            metrics["fossil_emissions_factor"],
            fossil_factor,
            FLOAT_TOLERANCE,
            scope="all_scenarios",
            evidence="F(s) = (1-s) / r(s)",
        )
        add_numeric(
            f"identity_d_{scenario_id}",
            metrics["ttw_reduction_fraction"],
            reduction,
            FLOAT_TOLERANCE,
            scope="all_scenarios",
            evidence="d(s) = 1 - F(s)",
        )

    # C0, Cs y A se verifican tanto por fórmula como por balance fila a fila.
    factor = float(config["co2_factor_tonnes_per_tj"])
    c0_residuals = [
        abs(
            float(row["reference_co2_tonnes"])
            - float(row["energy_tj"]) * factor
        )
        for row in emissions_rows
    ]
    cs_residuals = [
        abs(
            float(row["scenario_co2_tonnes"])
            - float(row["reference_co2_tonnes"])
            * float(row["fossil_emissions_factor"])
        )
        for row in emissions_rows
    ]
    avoided_formula_residuals = [
        abs(
            float(row["avoided_co2_tonnes"])
            - float(row["reference_co2_tonnes"])
            * float(row["ttw_reduction_fraction"])
        )
        for row in emissions_rows
    ]
    balance_residuals = [
        abs(
            float(row["reference_co2_tonnes"])
            - float(row["scenario_co2_tonnes"])
            - float(row["avoided_co2_tonnes"])
        )
        for row in emissions_rows
    ]
    for check_id, residuals, evidence in (
        ("annual_identity_C0", c0_residuals, "C0 = energy_tj * EF"),
        ("annual_identity_Cs", cs_residuals, "Cs = C0 * F(s)"),
        ("annual_identity_A", avoided_formula_residuals, "A = C0 * d(s)"),
        ("annual_balance_C0_Cs_A", balance_residuals, "C0 = Cs + A"),
    ):
        add_numeric(
            check_id,
            max(residuals, default=0.0),
            0.0,
            EMISSIONS_BALANCE_TOLERANCE,
            scope="EIA_open_update",
            evidence=f"maximum absolute residual: {evidence}",
        )

    # Los resúmenes deben ser sumas completas de las filas anuales.
    summary_residuals: list[float] = []
    summary_coverage_ok = True
    for summary_row in open_summary:
        selected = [
            row
            for row in emissions_rows
            if row["scenario_id"] == summary_row["scenario_id"]
            and int(summary_row["year_start"])
            <= int(row["year"])
            <= int(summary_row["year_end"])
        ]
        summary_coverage_ok = summary_coverage_ok and len(selected) == int(
            summary_row["n_years"]
        )
        for field in (
            "reference_co2_tonnes",
            "scenario_co2_tonnes",
            "avoided_co2_tonnes",
        ):
            summary_residuals.append(
                abs(
                    float(summary_row[field])
                    - sum(float(row[field]) for row in selected)
                )
            )
    add_boolean(
        "open_summary_year_coverage",
        summary_coverage_ok,
        summary_coverage_ok,
        True,
        scope="EIA_open_update",
        evidence="n_years in every period x scenario summary",
    )
    add_numeric(
        "open_summary_sums",
        max(summary_residuals, default=0.0),
        0.0,
        EMISSIONS_BALANCE_TOLERANCE,
        scope="EIA_open_update",
        evidence="maximum residual of annual-to-period sums for C0, Cs and A",
    )

    # Los intervalos publicados son disjuntos y omiten explícitamente 2024-2025.
    period_sets = [
        set(range(int(row["year_start"]), int(row["year_end"]) + 1))
        for row in config["published_controls"]
    ]
    overlaps: set[int] = set()
    for index, first in enumerate(period_sets):
        for second in period_sets[index + 1 :]:
            overlaps.update(first & second)
    expected_gap = set(config["published_aggregate_lineage"]["excluded_gap_years"])
    covered = set().union(*period_sets)
    bounds = set(range(min(covered), max(covered) + 1))
    actual_gap = bounds - covered
    add_boolean(
        "published_periods_disjoint",
        not overlaps,
        sorted(overlaps),
        [],
        scope="published_aggregate_reconciliation",
        evidence="reported period bounds",
    )
    add_boolean(
        "published_period_gap_2024_2025",
        actual_gap == expected_gap,
        sorted(actual_gap),
        sorted(expected_gap),
        scope="published_aggregate_reconciliation",
        evidence="years deliberately absent from the two aggregate controls",
    )

    aggregate_rows = published_rows + extension_rows
    published_period_scenarios = {
        (row["period_id"], row["scenario_id"]) for row in aggregate_rows
    }
    expected_period_scenarios = {
        (control["period_id"], scenario_id)
        for control in config["published_controls"]
        for scenario_id in config["blend_shares"]
    }
    add_boolean(
        "aggregate_period_scenario_rows",
        published_period_scenarios == expected_period_scenarios
        and len(aggregate_rows) == len(published_period_scenarios),
        sorted(published_period_scenarios),
        sorted(expected_period_scenarios),
        scope="published_aggregate_reconciliation",
        evidence="one aggregate row per reported period x scenario",
    )
    aggregate_balance_ok = all(
        int(row["reference_co2_tonnes"])
        == int(row["scenario_co2_tonnes"]) + int(row["avoided_co2_tonnes"])
        for row in aggregate_rows
    )
    aggregate_half_up_ok = all(
        int(row["scenario_co2_tonnes"])
        == round_half_up_integer(
            Decimal(str(row["reference_co2_tonnes"]))
            * Decimal(str(row["fossil_emissions_factor"]))
        )
        for row in aggregate_rows
    )
    add_boolean(
        "aggregate_balance_C0_Cs_A",
        aggregate_balance_ok,
        aggregate_balance_ok,
        True,
        scope="published_aggregate_reconciliation",
        evidence="integer balance C0 = Cs + A",
    )
    add_boolean(
        "aggregate_round_half_up",
        aggregate_half_up_ok,
        aggregate_half_up_ok,
        True,
        scope="published_aggregate_reconciliation",
        evidence="Decimal.quantize(1, ROUND_HALF_UP)",
    )
    add_boolean(
        "round_half_up_contract",
        [
            round_half_up_integer(Decimal("1.5")),
            round_half_up_integer(Decimal("2.5")),
        ]
        == [2, 3],
        [
            round_half_up_integer(Decimal("1.5")),
            round_half_up_integer(Decimal("2.5")),
        ],
        [2, 3],
        scope="published_aggregate_reconciliation",
        evidence="sentinel values distinguish half-up from banker's rounding",
    )

    # Golden values detectan cambios en OLS o en la retransformation exp().
    actual_fit = asdict(fit)
    for field, expected in config["golden_log_linear_fit"].items():
        computed = actual_fit[field]
        if isinstance(expected, int):
            add_boolean(
                f"golden_fit_{field}",
                computed == expected,
                computed,
                expected,
                scope="EIA_open_update",
                evidence="versioned golden OLS diagnostic",
            )
        else:
            add_numeric(
                f"golden_fit_{field}",
                float(computed),
                float(expected),
                FLOAT_TOLERANCE,
                scope="EIA_open_update",
                evidence="versioned golden OLS diagnostic",
            )
    projected_by_year = {
        str(row["year"]): float(row["energy_tj"])
        for row in annual_energy
        if row["data_status"] == "projected_log_linear"
    }
    forecast_golden = {
        str(year): float(value)
        for year, value in config["golden_forecast_energy_tj"].items()
    }
    add_boolean(
        "golden_forecast_years",
        set(projected_by_year) == set(forecast_golden),
        sorted(projected_by_year),
        sorted(forecast_golden),
        scope="EIA_open_update",
        evidence="versioned forecast years",
    )
    forecast_residual = max(
        (
            abs(projected_by_year[year] - expected)
            for year, expected in forecast_golden.items()
        ),
        default=0.0,
    )
    add_numeric(
        "golden_forecast_energy_tj",
        forecast_residual,
        0.0,
        1e-9,
        scope="EIA_open_update",
        evidence="maximum absolute residual against versioned 2025-2030 values",
    )

    add_boolean(
        "lineages_remain_separate",
        all(
            row["source_lineage"] == "article_notebook_recovered"
            for row in article_series
        )
        and all(
            str(row["source_lineage"]).startswith("EIA_open_data")
            for row in emissions_rows
        )
        and all(
            row["source_lineage"] == "manuscript_reported_aggregate_totals"
            for row in aggregate_rows
        ),
        "article_notebook_recovered annual; manuscript aggregates golden; EIA open annual",
        "article_notebook_recovered annual; manuscript aggregates golden; EIA open annual",
        scope="all_outputs",
        evidence="three source_lineage labels; no concatenation or calibration",
    )
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
    article_history, article_source_metadata = load_recovered_article_history(
        source_root, config
    )
    (
        article_series,
        article_counterfactual,
        article_summary,
        article_fit,
    ) = build_recovered_article_counterfactual(article_history, config)
    article_checks = build_recovered_article_checks(
        article_history,
        article_source_metadata,
        article_series,
        article_counterfactual,
        article_summary,
        article_fit,
        config,
    )
    observations, source_metadata = load_eia_observations(source_root, config)
    fit = fit_log_linear(
        observations,
        int(config["fit_start_year"]),
        int(config["fit_end_year"]),
    )
    published_rows, extension_rows, published_checks = (
        build_published_aggregate_reconciliation(config)
    )
    annual_energy, emissions_rows = build_open_update(observations, fit, config)
    open_summary = summarize_open_update(emissions_rows, config)
    comparisons = compare_lineages(open_summary, published_rows)
    checks = article_checks + build_checks(
        published_checks,
        observations,
        annual_energy,
        emissions_rows,
        open_summary,
        published_rows,
        extension_rows,
        fit,
        source_metadata,
        article_series,
        config,
    )
    diagnostics = {
        "model": "ordinary_least_squares_on_log_energy",
        "equation": "ln(energy_tj) = intercept_at_center + slope_per_year * (year - center_year)",
        "retransformation": "exp_without_smearing_correction",
        "fit": asdict(fit),
        "source_metadata": source_metadata,
        "lineage": {
            "open_update": config["open_update_lineage"],
            "published_aggregates": config["published_aggregate_lineage"],
            "rho": config["rho_parameter_provenance"],
            "separation_rule": (
                "Recovered article annual values, manuscript aggregate golden "
                "controls, and EIA annual values remain separate and are only "
                "compared"
            ),
        },
        "golden_values": {
            "fit": config["golden_log_linear_fit"],
            "forecast_energy_tj": config["golden_forecast_energy_tj"],
        },
        "article_recovered": {
            "model": "ordinary_least_squares_on_log_energy",
            "original_notebook_equation": config["article_recovered_lineage"][
                "original_fit_equation"
            ],
            "implementation_equation": config["article_recovered_lineage"][
                "implementation_fit_equation"
            ],
            "equivalence": config["article_recovered_lineage"][
                "fit_equivalence"
            ],
            "retransformation": "exp_without_smearing_correction",
            "fit": asdict(article_fit),
            "source_metadata": article_source_metadata,
            "contexts": {
                "historical_counterfactual_1986_2023": (
                    "E10 applied to all recovered historical years"
                ),
                "prospective_policy_2024_2030": (
                    "E0 in 2024-2025; E10 in 2026-2030"
                ),
                "integrated_figure_1986_2030": (
                    "E10 applied to all 45 years, as in the original figure"
                ),
            },
            "summary_rule": (
                "1986-2023 plus 2026-2030; excludes 2024-2025"
            ),
        },
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
        "article_series": destination_root
        / "06_resultados"
        / "emisiones"
        / "serie_articulo_anual.csv",
        "article_counterfactual": destination_root
        / "06_resultados"
        / "emisiones"
        / "contrafactual_articulo_anual.csv",
        "article_summary": destination_root
        / "06_resultados"
        / "emisiones"
        / "contrafactual_articulo_resumen.csv",
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
            output_paths["article_series"],
            article_series,
            [
                "year",
                "data_status",
                "source_lineage",
                "btu",
                "energy_tj",
                "million_us_gallons",
                "reference_co2_tonnes",
                "value_status",
            ],
        )
        _write_csv(
            output_paths["article_counterfactual"],
            article_counterfactual,
            [
                "year",
                "data_status",
                "source_lineage",
                "btu",
                "energy_tj",
                "million_us_gallons",
                "reference_co2_tonnes",
                "value_status",
                "scenario_context",
                "scenario_id",
                "blend_share_applied",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
            ],
        )
        _write_csv(
            output_paths["article_summary"],
            article_summary,
            [
                "period_id",
                "year_coverage",
                "excluded_years",
                "n_years",
                "reference_co2_tonnes",
                "scenario_co2_tonnes",
                "avoided_co2_tonnes",
                "reference_co2_tonnes_rounded",
                "scenario_co2_tonnes_rounded",
                "avoided_co2_tonnes_rounded",
                "source_lineage",
                "calculation_scope",
            ],
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
                "calculation_scope",
                "source_lineage",
                "annual_reproduction_status",
                "rho_provenance",
                "rounding_method",
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
                "calculation_scope",
                "source_lineage",
                "annual_reproduction_status",
                "rho_provenance",
                "rounding_method",
            ],
        )
        _write_csv(
            output_paths["open_annual"],
            emissions_rows,
            [
                "year",
                "data_status",
                "source_series_id",
                "source_lineage",
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
                "n_years",
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
                "tolerance",
                "scope",
                "evidence",
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
        "article_source_metadata": article_source_metadata,
        "article_fit": article_fit,
        "article_series": article_series,
        "article_counterfactual": article_counterfactual,
        "article_summary": article_summary,
        "fit": fit,
        "published_reproduction": published_rows,
        "published_aggregate_reconciliation": published_rows,
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
    "build_recovered_article_checks",
    "build_recovered_article_counterfactual",
    "build_published_aggregate_reconciliation",
    "build_published_reproduction",
    "fit_log_linear",
    "load_config",
    "load_eia_observations",
    "load_recovered_article_history",
    "round_half_up_integer",
    "run_emissions_pipeline",
]
