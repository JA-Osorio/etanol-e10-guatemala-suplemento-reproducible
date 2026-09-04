"""Pruebas de las figuras Plotly derivadas de CSV reproducibles."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from e10_gt.visualizaciones_interactivas import (
    crear_figura_cost_push,
    crear_figura_demand_pull,
    crear_figura_consumo_articulo,
    crear_figura_emisiones_articulo_historica,
    crear_figura_emisiones_articulo_integrada,
    crear_figura_emisiones_articulo_prospectiva,
    crear_figura_emisiones_eia,
    crear_figura_emisiones_evitadas,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMANDA_CSV = (
    REPO_ROOT / "06_resultados/economia_articulo/categorias_demanda.csv"
)
PRECIOS_CSV = (
    REPO_ROOT / "06_resultados/economia_articulo/categorias_precios.csv"
)
EMISIONES_CSV = REPO_ROOT / "06_resultados/emisiones/actualizacion_eia_anual.csv"
SERIE_ARTICULO_CSV = (
    REPO_ROOT / "06_resultados/emisiones/serie_articulo_anual.csv"
)
CONTRAFACTUAL_ARTICULO_CSV = (
    REPO_ROOT / "06_resultados/emisiones/contrafactual_articulo_anual.csv"
)


def test_demand_pull_procede_del_csv_y_compara_e5_e10() -> None:
    tabla = pd.read_csv(DEMANDA_CSV)
    figura = crear_figura_demand_pull(DEMANDA_CSV)

    assert isinstance(figura, go.Figure)
    assert [traza.name for traza in figura.data] == [
        "E5 original",
        "E10 comparable",
    ]
    for traza, escenario in zip(
        figura.data, ("E5_original", "E10_misma_metodologia")
    ):
        fuente = tabla.loc[tabla["id_escenario"] == escenario]
        assert list(traza.y) == fuente["categoria"].tolist()
        assert list(traza.x) == pytest.approx(
            fuente["delta_x_millones_q_2013"].tolist()
        )
        assert "millones de Q de 2013" in traza.hovertemplate
    assert figura.layout.meta["origen_datos"] == str(DEMANDA_CSV.resolve())
    assert figura.layout.meta["unidad"] == "millones de Q de 2013"


def test_cost_push_procede_del_csv_convierte_fraccion_a_porcentaje() -> None:
    tabla = pd.read_csv(PRECIOS_CSV)
    figura = crear_figura_cost_push(PRECIOS_CSV)
    escenarios = (
        "E5_original",
        "E10_misma_metodologia",
        "E10_penalizacion_lhv",
    )

    assert isinstance(figura, go.Figure)
    assert len(figura.data) == len(escenarios)
    for traza, escenario in zip(figura.data, escenarios):
        fuente = tabla.loc[tabla["id_escenario"] == escenario]
        esperado = 100.0 * fuente["delta_precio_total_promedio_fraccion"]
        assert list(traza.x) == pytest.approx(esperado.tolist())
        assert "%" in traza.hovertemplate
        assert "Linaje" in traza.hovertemplate
    assert figura.layout.meta["origen_datos"] == str(PRECIOS_CSV.resolve())
    assert figura.layout.meta["unidad"] == "%"


def test_emisiones_eia_usa_e10_y_muestra_estado_y_linaje() -> None:
    tabla = pd.read_csv(EMISIONES_CSV)
    e10 = tabla.loc[tabla["scenario_id"] == "E10"].sort_values("year")
    figura = crear_figura_emisiones_eia(EMISIONES_CSV)

    assert isinstance(figura, go.Figure)
    assert len(figura.data) == 4
    assert len(figura.layout.shapes) == e10["data_status"].nunique()
    observada_e0 = next(
        traza for traza in figura.data if traza.name == "Gasolina de referencia (E0) · Observado"
    )
    fuente_observada = e10.loc[e10["data_status"] == "observed"]
    assert list(observada_e0.x) == fuente_observada["year"].tolist()
    assert list(observada_e0.y) == pytest.approx(
        fuente_observada["reference_co2_tonnes"].tolist()
    )
    for traza in figura.data:
        assert "t CO₂ TTW" in traza.hovertemplate
        assert "Estado" in traza.hovertemplate
        assert "Linaje" in traza.hovertemplate
    assert figura.layout.meta["origen_datos"] == str(EMISIONES_CSV.resolve())


def test_emisiones_evitadas_anuales_y_acumuladas_salen_del_csv() -> None:
    tabla = pd.read_csv(EMISIONES_CSV)
    fuente = (
        tabla.loc[tabla["scenario_id"] == "E10"].sort_values("year").reset_index()
    )
    figura = crear_figura_emisiones_evitadas(EMISIONES_CSV)

    assert isinstance(figura, go.Figure)
    assert [traza.name for traza in figura.data] == [
        "Evitadas anuales",
        "Evitadas acumuladas",
    ]
    assert list(figura.data[0].y) == pytest.approx(
        fuente["avoided_co2_tonnes"].tolist()
    )
    assert list(figura.data[1].y) == pytest.approx(
        fuente["avoided_co2_tonnes"].cumsum().tolist()
    )
    assert figura.data[1].yaxis == "y2"
    assert figura.layout.meta["unidad"] == "t CO₂ TTW"
    assert figura.layout.meta["origen_datos"] == str(EMISIONES_CSV.resolve())


@pytest.mark.parametrize(
    ("constructor", "contexto"),
    (
        (
            crear_figura_emisiones_articulo_historica,
            "historical_counterfactual_1986_2023",
        ),
        (
            crear_figura_emisiones_articulo_prospectiva,
            "prospective_policy_2024_2030",
        ),
        (
            crear_figura_emisiones_articulo_integrada,
            "integrated_figure_1986_2030",
        ),
    ),
)
def test_figuras_contrafactuales_articulo_salen_de_su_contexto_csv(
    constructor, contexto: str
) -> None:
    tabla = pd.read_csv(CONTRAFACTUAL_ARTICULO_CSV)
    fuente = (
        tabla.loc[tabla["scenario_context"] == contexto]
        .sort_values("year")
        .reset_index(drop=True)
    )

    figura = constructor(CONTRAFACTUAL_ARTICULO_CSV)

    assert isinstance(figura, go.Figure)
    assert len(figura.data) == 2
    assert list(figura.data[0].x) == fuente["year"].tolist()
    assert list(figura.data[1].x) == fuente["year"].tolist()
    assert list(figura.data[0].y) == pytest.approx(
        fuente["reference_co2_tonnes"].tolist()
    )
    assert list(figura.data[1].y) == pytest.approx(
        fuente["scenario_co2_tonnes"].tolist()
    )
    assert figura.data[1].fill == "tonexty"
    assert [fila[2] for fila in figura.data[1].customdata] == fuente[
        "scenario_id"
    ].tolist()
    assert [fila[4] for fila in figura.data[1].customdata] == pytest.approx(
        fuente["avoided_co2_tonnes"].tolist()
    )
    assert len(figura.layout.shapes) == fuente["data_status"].nunique()
    for traza in figura.data:
        assert "Cuaderno original recuperado" in traza.hovertemplate
        assert "t CO₂ TTW" in traza.hovertemplate
        assert "Estado temporal" in traza.hovertemplate
        assert "Contexto" in traza.hovertemplate
        assert "Linaje" in traza.hovertemplate
    assert "Cuaderno original recuperado" in figura.layout.title.text
    assert figura.layout.meta["scenario_context"] == contexto
    assert figura.layout.meta["source_lineage"] == ["article_notebook_recovered"]
    assert figura.layout.meta["origen_datos"] == str(
        CONTRAFACTUAL_ARTICULO_CSV.resolve()
    )


def test_consumo_articulo_usa_los_45_valores_del_csv_recuperado() -> None:
    fuente = pd.read_csv(SERIE_ARTICULO_CSV).sort_values("year").reset_index(drop=True)

    figura = crear_figura_consumo_articulo(SERIE_ARTICULO_CSV)

    assert isinstance(figura, go.Figure)
    assert len(figura.data) == 1
    assert list(figura.data[0].x) == fuente["year"].tolist()
    assert list(figura.data[0].y) == pytest.approx(
        fuente["million_us_gallons"].tolist()
    )
    assert len(figura.layout.shapes) == fuente["data_status"].nunique()
    assert "Cuaderno original recuperado" in figura.data[0].hovertemplate
    assert "millones de galones EE. UU." in figura.data[0].hovertemplate
    assert "Estado temporal" in figura.data[0].hovertemplate
    assert "Contexto" in figura.data[0].hovertemplate
    assert "Linaje" in figura.data[0].hovertemplate
    assert figura.layout.meta["source_lineage"] == ["article_notebook_recovered"]
    assert figura.layout.meta["origen_datos"] == str(SERIE_ARTICULO_CSV.resolve())


def test_las_funciones_aceptan_dataframe_y_no_lo_mutan() -> None:
    tabla = pd.read_csv(DEMANDA_CSV)
    columnas_antes = tabla.columns.tolist()
    valores_antes = tabla.copy(deep=True)

    figura = crear_figura_demand_pull(tabla)

    assert isinstance(figura, go.Figure)
    assert figura.layout.meta["origen_datos"] == "DataFrame en memoria"
    assert tabla.columns.tolist() == columnas_antes
    pd.testing.assert_frame_equal(tabla, valores_antes)


def test_esquema_incompleto_falla_con_mensaje_explicito() -> None:
    with pytest.raises(ValueError, match="delta_x_millones_q_2013"):
        crear_figura_demand_pull(
            pd.DataFrame(
                {
                    "id_escenario": ["E5_original"],
                    "naturaleza": ["prueba"],
                    "categoria": ["prueba"],
                }
            )
        )
