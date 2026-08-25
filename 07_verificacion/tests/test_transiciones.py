"""Pruebas del calendario normativo y de transiciones superiores."""

from pathlib import Path

import numpy as np

from e10_gt.transiciones import ejecutar_transiciones


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_actualizacion_normativa_no_inventa_cobertura_superior() -> None:
    result = ejecutar_transiciones(REPO_ROOT, escribir_resultados=False)
    factual = [
        row
        for row in result["escenarios"]
        if row["familia_analitica"] == "actualizacion_normativa_2026"
    ]
    regular = next(row for row in factual if row["producto"] == "gasolina_regular")
    superior = next(row for row in factual if row["producto"] == "gasolina_superior")
    assert regular["mezcla_en_periodo"] == "E10"
    assert np.isclose(regular["fraccion_anio_en_vigencia"], 132 / 365)
    assert superior["fraccion_alcohol"] == ""
    assert superior["co2_evitado_t_por_tj_actividad_anual_producto"] == ""


def test_transiciones_solo_contienen_mezclas_admitidas() -> None:
    result = ejecutar_transiciones(REPO_ROOT, escribir_resultados=False)
    modeled = {
        row["mezcla_en_periodo"]
        for row in result["escenarios"]
        if row["fraccion_alcohol"] != ""
    }
    assert modeled == {"E10", "E15", "E20"}
    assert all(row["cumple"] for row in result["controles"])
