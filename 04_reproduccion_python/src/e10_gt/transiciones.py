"""Escenarios de transición normalizados y alcance normativo vigente."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .emisiones_ttw import blend_metrics


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No hay filas para escribir en {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ejecutar_transiciones(
    raiz_repositorio: str | Path,
    *,
    escribir_resultados: bool = True,
) -> dict[str, Any]:
    """Calcula reducciones normalizadas sin inventar ventas por tipo de gasolina."""

    repo_root = Path(raiz_repositorio).resolve()
    calendar = _read_rows(repo_root / "03_configuracion" / "calendario_transicion.csv")
    with (repo_root / "03_configuracion" / "emisiones_ttw.json").open(
        encoding="utf-8"
    ) as handle:
        emissions_config = json.load(handle)

    blend_shares = {
        name: float(value) for name, value in emissions_config["blend_shares"].items()
    }
    lhv_ratio = float(emissions_config["ethanol_to_gasoline_lhv_ratio"])
    factor = float(emissions_config["co2_factor_tonnes_per_tj"])
    output_rows: list[dict[str, Any]] = []
    fraction_residuals: list[float] = []

    for row in calendar:
        fraction = float(row["fraccion_anio_en_vigencia"])
        days = int(row["dias_en_vigencia"])
        days_year = int(row["dias_anio"])
        fraction_residuals.append(abs(fraction - days / days_year))
        blend_name = row["mezcla_en_periodo"]
        share: float | str = ""
        relative_energy: float | str = ""
        reduction: float | str = ""
        avoided_per_tj: float | str = ""
        availability = "no_modelado_pendiente_de_norma_y_datos"
        if blend_name in blend_shares:
            share = blend_shares[blend_name]
            metrics = blend_metrics(float(share), lhv_ratio)
            relative_energy = metrics["relative_blend_energy"]
            reduction = metrics["ttw_reduction_fraction"]
            avoided_per_tj = factor * float(reduction) * fraction
            if row["familia_analitica"] == "reproduccion_publicada":
                availability = "identidad_normalizada_y_control_publicado_separado"
            else:
                availability = "normalizado_por_tj_de_actividad_anual_del_producto"

        output_rows.append(
            {
                "familia_analitica": row["familia_analitica"],
                "trayectoria": row["trayectoria"],
                "producto": row["producto"],
                "anio": int(row["anio"]),
                "mezcla_en_periodo": blend_name,
                "fraccion_alcohol": share,
                "fraccion_anio_en_vigencia": fraction,
                "energia_relativa_mezcla": relative_energy,
                "reduccion_ttw_fraccion_durante_vigencia": reduction,
                "co2_evitado_t_por_tj_actividad_anual_producto": avoided_per_tj,
                "disponibilidad_cuantitativa": availability,
                "caracter": row["caracter"],
                "estado_normativo": row["estado_normativo"],
                "fuente_id": row["fuente_id"],
            }
        )

    modeled_shares = [
        float(row["fraccion_alcohol"])
        for row in output_rows
        if row["fraccion_alcohol"] != ""
    ]
    factual_superior = [
        row
        for row in output_rows
        if row["familia_analitica"] == "actualizacion_normativa_2026"
        and row["producto"] == "gasolina_superior"
    ]
    controls = [
        {
            "control": "fracciones_calendario_coinciden_con_dias",
            "valor": max(fraction_residuals),
            "esperado": "<=1e-12",
            "cumple": max(fraction_residuals) <= 1e-12,
        },
        {
            "control": "mezclas_modeladas_desde_diez_por_ciento",
            "valor": min(modeled_shares),
            "esperado": ">=0.10",
            "cumple": min(modeled_shares) >= 0.10,
        },
        {
            "control": "superior_pendiente_sin_estimacion",
            "valor": len(factual_superior),
            "esperado": 1,
            "cumple": len(factual_superior) == 1
            and factual_superior[0]["fraccion_alcohol"] == ""
            and factual_superior[0]["co2_evitado_t_por_tj_actividad_anual_producto"]
            == "",
        },
        {
            "control": "regular_vigente_presente",
            "valor": sum(
                row["familia_analitica"] == "actualizacion_normativa_2026"
                and row["producto"] == "gasolina_regular"
                and row["mezcla_en_periodo"] == "E10"
                for row in output_rows
            ),
            "esperado": 1,
            "cumple": sum(
                row["familia_analitica"] == "actualizacion_normativa_2026"
                and row["producto"] == "gasolina_regular"
                and row["mezcla_en_periodo"] == "E10"
                for row in output_rows
            )
            == 1,
        },
        {
            "control": "intensidades_finitas_no_negativas",
            "valor": len(modeled_shares),
            "esperado": len(modeled_shares),
            "cumple": all(
                row["co2_evitado_t_por_tj_actividad_anual_producto"] == ""
                or (
                    math.isfinite(
                        float(row["co2_evitado_t_por_tj_actividad_anual_producto"])
                    )
                    and float(row["co2_evitado_t_por_tj_actividad_anual_producto"])
                    >= 0
                )
                for row in output_rows
            ),
        },
    ]
    if not all(bool(row["cumple"]) for row in controls):
        failed = ", ".join(row["control"] for row in controls if not row["cumple"])
        raise AssertionError(f"Fallaron controles de transición: {failed}")

    if escribir_resultados:
        _write_csv(
            repo_root
            / "06_resultados"
            / "escenarios"
            / "transiciones_emisiones_normalizadas.csv",
            output_rows,
        )
        _write_csv(
            repo_root / "07_verificacion" / "controles_transiciones.csv",
            controls,
        )

    return {"escenarios": output_rows, "controles": controls}


__all__ = ["ejecutar_transiciones"]
