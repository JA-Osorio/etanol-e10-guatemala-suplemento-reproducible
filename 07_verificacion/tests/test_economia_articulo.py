"""Pruebas golden del calculo economico historico recuperado."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from e10_gt.economia_articulo import ejecutar_economia_articulo


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_MIP = REPO_ROOT.parent / "mip-guatemala-2013-reproducible"
MIP_ROOT = LOCAL_MIP if LOCAL_MIP.is_dir() else None
GOLDEN = {
    "E5_original": {
        "r_fraccion": 0.015285714285714347,
        "delta_y_total_millones_q_2013": 1.8772035273857974,
        "delta_x_total_millones_q_2013": 3.16677166970337,
        "delta_residual_no_intermedio_domestico_total_millones_q_2013": 1.8772035273857952,
        "delta_precio_total_promedio_fraccion": 1.926442334455293e-06,
        "delta_precio_transporte_p104_p105_promedio_fraccion": 1.974047358012278e-05,
        "delta_x_p010_millones_q_2013": 1.879071380916647,
        "multiplicador_produccion": 1.6869623477180609,
    },
    "E10_misma_metodologia": {
        "r_fraccion": 0.0005714285714286671,
        "delta_y_total_millones_q_2013": 3.754407054771595,
        "delta_x_total_millones_q_2013": 6.33354333940674,
        "delta_residual_no_intermedio_domestico_total_millones_q_2013": 3.7544070547715904,
        "delta_precio_total_promedio_fraccion": 7.201653586749935e-08,
        "delta_precio_transporte_p104_p105_promedio_fraccion": 7.37961629163589e-07,
        "delta_x_p010_millones_q_2013": 3.758142761833294,
        "multiplicador_produccion": 1.6869623477180609,
    },
}

E5_DEMAND_BY_CATEGORY = {
    "Cana de azucar": 1.879071380916647,
    "Agricultura, silvicultura y pesca (sin P010)": 0.0072849495410824226,
    "Combustibles y refinacion": 0.0009210693811487127,
    "Industria quimica ampliada": 0.1554487793180743,
    "Transporte y logistica": 0.0601498488091671,
    "Servicios (sin transporte y logistica)": 0.9344844870466592,
    "Otros": 0.12941115469059813,
}

E5_PRICE_BY_CATEGORY = {
    "Cana de azucar": 2.9336920308423904e-06,
    "Agricultura, silvicultura y pesca (sin P010)": 2.181076992357037e-06,
    "Combustibles y refinacion": 3.138607939497041e-06,
    "Industria quimica ampliada": 8.999990781861144e-07,
    "Transporte y logistica": 8.557658682739578e-06,
    "Servicios (sin transporte y logistica)": 9.185137407675114e-07,
    "Otros": 1.9056815087332231e-06,
}


def _run() -> dict:
    return ejecutar_economia_articulo(
        REPO_ROOT, escribir_resultados=False, raiz_mip=MIP_ROOT
    )


def test_reproduce_resultados_golden_del_cuaderno() -> None:
    result = _run()
    assert result["fuente_manuscrito"]["sha256"] == "omitido_en_rama_publica"
    assert (
        result["fuente_manuscrito"]["publicacion_identificadores"]
        == "sanitizada"
    )
    assert result["fuente_manuscrito"]["redistribuido"] is False
    by_id = {row["id_escenario"]: row for row in result["escenarios"]}
    for scenario_id, expected_metrics in GOLDEN.items():
        for field, expected in expected_metrics.items():
            assert np.isclose(
                by_id[scenario_id][field], expected, atol=5e-13, rtol=0.0
            ), (scenario_id, field, by_id[scenario_id][field], expected)


def test_reconciliacion_identifica_las_dos_cifras_reetiquetadas() -> None:
    result = _run()
    by_id = {row["id_escenario"]: row for row in result["escenarios"]}
    reconciliation = {
        row["id_afirmacion_manuscrito"]: row
        for row in result["reconciliacion_articulo"]
    }
    assert round(by_id["E5_original"]["r_porcentaje"], 2) == 1.53
    assert not reconciliation["cost_push_transporte"][
        "coincide_e5_con_manuscrito"
    ]
    assert np.isclose(
        reconciliation["cost_push_transporte"]["valor_e5_recalculado"],
        100.0
        * GOLDEN["E5_original"][
            "delta_precio_transporte_p104_p105_promedio_fraccion"
        ],
        atol=5e-13,
        rtol=0.0,
    )
    assert round(
        by_id["E5_original"]["delta_x_total_millones_q_2013"], 2
    ) == 3.17
    assert not reconciliation["demand_pull_cana_de_azucar"][
        "coincide_e5_con_manuscrito"
    ]


def test_otras_afirmaciones_del_manuscrito_no_se_reproducen() -> None:
    result = _run()
    reconciliation = {
        row["id_afirmacion_manuscrito"]: row
        for row in result["reconciliacion_articulo"]
    }
    for result_id in (
        "cost_push_industria_quimica",
        "cost_push_servicios",
        "cost_push_agricultura",
        "demand_pull_industria_quimica",
        "demand_pull_servicios",
        "demand_pull_transporte",
        "demand_pull_total",
        "demand_pull_total_discusion",
        "multiplicador_produccion",
    ):
        assert not reconciliation[result_id]["coincide_e5_con_manuscrito"]
        assert not reconciliation[result_id]["coincide_e10_con_manuscrito"]
    assert result["todos_los_controles_cumplen"]


def test_lhv_es_sensibilidad_separada_y_usa_factor_fisico() -> None:
    result = _run()
    by_id = {row["id_escenario"]: row for row in result["escenarios"]}
    lhv = by_id["E10_penalizacion_lhv"]
    expected_factor = 32.0 / ((1.0 - 0.10) * 32.0 + 0.10 * 21.2)
    assert lhv["naturaleza"] == "sensibilidad_fisica_separada"
    assert np.isclose(
        lhv["factor_energetico_aplicado"], expected_factor, atol=1e-15, rtol=0.0
    )
    assert not np.isclose(
        lhv["r_fraccion"], by_id["E10_misma_metodologia"]["r_fraccion"]
    )
    for field in (
        "delta_y_total_millones_q_2013",
        "delta_x_total_millones_q_2013",
        "delta_x_p010_millones_q_2013",
    ):
        assert np.isclose(
            lhv[field],
            by_id["E10_misma_metodologia"][field],
            atol=5e-13,
            rtol=0.0,
        )


def test_agregados_sectoriales_quedan_fijados() -> None:
    result = _run()
    demand = {
        row["categoria"]: row["delta_x_millones_q_2013"]
        for row in result["categorias_demanda"]
        if row["id_escenario"] == "E5_original"
    }
    prices = {
        row["categoria"]: row["delta_precio_total_promedio_fraccion"]
        for row in result["categorias_precios"]
        if row["id_escenario"] == "E5_original"
    }
    assert demand.keys() == E5_DEMAND_BY_CATEGORY.keys()
    assert prices.keys() == E5_PRICE_BY_CATEGORY.keys()
    for category, expected in E5_DEMAND_BY_CATEGORY.items():
        assert np.isclose(demand[category], expected, atol=5e-13, rtol=0.0)
    for category, expected in E5_PRICE_BY_CATEGORY.items():
        assert np.isclose(prices[category], expected, atol=5e-13, rtol=0.0)


def test_resultados_por_producto_cubren_tres_veces_p001_p152() -> None:
    result = _run()
    rows = result["resultados_por_producto"]
    assert len(rows) == 3 * 152
    for scenario_id in (
        "E5_original",
        "E10_misma_metodologia",
        "E10_penalizacion_lhv",
    ):
        codes = [row["codigo"] for row in rows if row["id_escenario"] == scenario_id]
        assert codes == [f"P{number:03d}" for number in range(1, 153)]


def test_escritura_produce_todos_los_archivos_declarados(tmp_path: Path) -> None:
    (tmp_path / "03_configuracion").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT / "03_configuracion" / "economia_articulo.json",
        tmp_path / "03_configuracion" / "economia_articulo.json",
    )
    shutil.copy2(
        REPO_ROOT / "03_configuracion" / "dependencia_mip.json",
        tmp_path / "03_configuracion" / "dependencia_mip.json",
    )
    (tmp_path / "02_concordancias").mkdir(parents=True)
    shutil.copy2(
        REPO_ROOT
        / "02_concordancias"
        / "agregaciones_economia_articulo.csv",
        tmp_path
        / "02_concordancias"
        / "agregaciones_economia_articulo.csv",
    )
    result = ejecutar_economia_articulo(
        tmp_path,
        escribir_resultados=True,
        raiz_mip=MIP_ROOT,
    )
    expected_names = {
        "resumen_escenarios.csv",
        "resultados_por_producto.csv",
        "categorias_demanda.csv",
        "categorias_precios.csv",
        "reconciliacion_articulo.csv",
        "resumen_economia_articulo.json",
        "informe_reconciliacion.md",
    }
    output_dir = tmp_path / "06_resultados" / "economia_articulo"
    assert {path.name for path in output_dir.iterdir()} == expected_names
    assert (tmp_path / "07_verificacion/controles_economia_articulo.csv").is_file()

    with (output_dir / "resumen_escenarios.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        assert len(list(csv.DictReader(handle))) == 3
    with (output_dir / "resumen_economia_articulo.json").open(
        encoding="utf-8"
    ) as handle:
        written_summary = json.load(handle)
    assert written_summary["todos_los_controles_cumplen"] is True
    assert len(result["archivos_escritos"]) == 8


def test_un_golden_incorrecto_hace_fallar_la_ejecucion(tmp_path: Path) -> None:
    (tmp_path / "03_configuracion").mkdir(parents=True)
    (tmp_path / "02_concordancias").mkdir(parents=True)
    for relative_path in (
        Path("03_configuracion/economia_articulo.json"),
        Path("03_configuracion/dependencia_mip.json"),
        Path("02_concordancias/agregaciones_economia_articulo.csv"),
    ):
        shutil.copy2(REPO_ROOT / relative_path, tmp_path / relative_path)

    config_path = tmp_path / "03_configuracion/economia_articulo.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["golden_e5_cuaderno_recuperado"]["r_fraccion"] = 123.0
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        AssertionError,
        match="Fallaron controles de la economía del manuscrito",
    ):
        ejecutar_economia_articulo(
            tmp_path,
            escribir_resultados=True,
            raiz_mip=MIP_ROOT,
        )
    assert not (tmp_path / "06_resultados").exists()
