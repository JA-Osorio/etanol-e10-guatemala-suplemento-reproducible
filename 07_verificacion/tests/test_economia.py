"""Pruebas unitarias del bloque económico."""

from __future__ import annotations

from pathlib import Path
import csv

import numpy as np

from e10_gt.economia import (
    _build_analytical_groups,
    calcular_contrafactuales_normalizados,
    calcular_costo_servicio,
    calcular_fraccion_referencia_comercial,
    transmitir_choque_costos,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_costo_servicio_e10_en_tres_recargos() -> None:
    expected = {
        0.0: -0.004745307478265515,
        0.15: 0.00478230112338518,
        0.30: 0.014309909725036096,
    }
    for surcharge, expected_change in expected.items():
        result = calcular_costo_servicio(
            0.10,
            2.9664,
            1.82,
            0.659375,
            surcharge,
        )
        assert np.isclose(
            result["cambio_costo_servicio_fraccion"],
            expected_change,
            atol=1e-15,
            rtol=0.0,
        )


def test_transmision_usa_fila_combustible_y_leontief_transpuesta() -> None:
    a_total = np.array([[0.0, 0.0], [0.20, 0.40]])
    leontief = np.array([[1.0, 0.10], [0.20, 1.0]])
    direct, propagated = transmitir_choque_costos(
        a_total,
        leontief,
        fuel_index=1,
        participacion_gasolina_p068=0.50,
        cambio_costo_servicio_fraccion=0.02,
    )
    expected_direct = np.array([0.002, 0.004])
    assert np.allclose(direct, expected_direct)
    assert np.allclose(propagated, leontief.T @ expected_direct)


def test_referencia_comercial_e10_es_fraccion_del_requerimiento() -> None:
    fraction = calcular_fraccion_referencia_comercial(
        50_000_000.0, 74_526_560.98350047
    )
    assert np.isclose(fraction, 0.6709017475134745, atol=1e-15, rtol=0.0)


def test_contrafactuales_son_independientes_y_normalizados() -> None:
    codes = ("P010", "P052", "P055", "P068")
    labels = {code: code for code in codes}
    leontief = np.eye(4)
    results = calcular_contrafactuales_normalizados(
        leontief,
        codes,
        labels,
        ("P010", "P052", "P055"),
        1.0,
        np.array([0.5, 0.6, 0.7, 0.8]),
        np.array([10.0, 20.0, 30.0, 40.0]),
    )
    assert len(results) == 3
    assert {row["codigo_proxy"] for row in results} == {"P010", "P052", "P055"}
    assert all(row["componentes_no_cero_choque"] == 1 for row in results)
    assert all(row["multiplicador_produccion"] == 1.0 for row in results)
    assert all(row["es_escenario_central"] is False for row in results)


def test_agregaciones_cubren_152_productos_una_vez() -> None:
    with (
        REPO_ROOT / "02_concordancias" / "agregaciones_economia.csv"
    ).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    codes = tuple(f"P{number:03d}" for number in range(1, 153))
    groups = _build_analytical_groups(codes, rows)
    covered = [code for group in groups for code in group["codigos"]]
    assert len(groups) == 14
    assert covered == list(codes)


def test_repositorio_no_contiene_token_de_mezcla_excluida() -> None:
    repository = Path(__file__).resolve().parents[2]
    excluded = (chr(69) + str(5)).lower()
    text_suffixes = {".csv", ".json", ".md", ".py", ".toml", ".txt", ".yml", ".yaml"}
    matches: list[str] = []
    for path in repository.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        relative_parts = path.relative_to(repository).parts
        if ".git" in relative_parts or "__pycache__" in relative_parts:
            continue
        if excluded in path.read_text(encoding="utf-8", errors="ignore").lower():
            matches.append(str(path.relative_to(repository)))
    assert matches == []
