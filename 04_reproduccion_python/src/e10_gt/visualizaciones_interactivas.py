"""Visualizaciones interactivas construidas desde las salidas reproducibles.

Las funciones de este módulo no escriben archivos ni recalculan resultados. Cada
figura recibe una tabla en memoria o la ruta de un CSV generado por el pipeline,
valida su esquema y conserva el origen de los datos en ``figure.layout.meta``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Sequence, TypeAlias

import pandas as pd
import plotly.graph_objects as go


TablaEntrada: TypeAlias = pd.DataFrame | str | Path

_COLORES_ESCENARIO: Final[dict[str, str]] = {
    "E5_original": "#7A5195",
    "E10_misma_metodologia": "#2F6F4E",
    "E10_penalizacion_lhv": "#D17A22",
    "E0": "#4C566A",
    "E10": "#2F6F4E",
}
_ETIQUETAS_ESCENARIO: Final[dict[str, str]] = {
    "E5_original": "E5 original",
    "E10_misma_metodologia": "E10 comparable",
    "E10_penalizacion_lhv": "E10 (sensibilidad LHV)",
}
_ETIQUETAS_ESTADO: Final[dict[str, str]] = {
    "observed": "Observado",
    "projected_log_linear": "Proyectado (tendencia log-lineal)",
    "recovered_notebook_output": "Observado",
    "projected_log_linear_2014_2023": (
        "Proyectado (tendencia log-lineal 2014–2023)"
    ),
}
_COLORES_ESTADO: Final[dict[str, str]] = {
    "observed": "rgba(76, 86, 106, 0.08)",
    "projected_log_linear": "rgba(209, 122, 34, 0.12)",
    "recovered_notebook_output": "rgba(76, 86, 106, 0.08)",
    "projected_log_linear_2014_2023": "rgba(209, 122, 34, 0.12)",
}
_CONTEXTOS_ARTICULO: Final[dict[str, str]] = {
    "historical_counterfactual_1986_2023": "Histórico 1986–2023",
    "prospective_policy_2024_2030": "Prospectivo 2024–2030",
    "integrated_figure_1986_2030": "Integrado 1986–2030",
}


def _cargar_tabla(datos: TablaEntrada) -> tuple[pd.DataFrame, str]:
    """Devuelve una copia de la tabla y una descripción auditable de su origen."""

    if isinstance(datos, pd.DataFrame):
        tabla = datos.copy(deep=True)
        origen = "DataFrame en memoria"
    else:
        ruta = Path(datos)
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe el CSV de resultados: {ruta}")
        tabla = pd.read_csv(ruta)
        origen = str(ruta.resolve())
    if tabla.empty:
        raise ValueError("La tabla de resultados está vacía")
    return tabla, origen


def _validar_columnas(tabla: pd.DataFrame, requeridas: Sequence[str]) -> None:
    faltantes = sorted(set(requeridas) - set(tabla.columns))
    if faltantes:
        raise ValueError(
            "Faltan columnas requeridas para la figura: " + ", ".join(faltantes)
        )


def _validar_numerica(tabla: pd.DataFrame, columna: str) -> None:
    convertida = pd.to_numeric(tabla[columna], errors="coerce")
    if convertida.isna().any():
        raise ValueError(f"La columna {columna!r} contiene valores no numéricos")
    tabla[columna] = convertida


def _etiqueta_escenario(identificador: str) -> str:
    return _ETIQUETAS_ESCENARIO.get(identificador, identificador)


def _configurar_figura_categorias(
    figura: go.Figure,
    *,
    titulo: str,
    titulo_eje_x: str,
    origen: str,
    columnas_usadas: Sequence[str],
    unidad: str,
) -> go.Figure:
    figura.update_layout(
        title={"text": titulo, "x": 0.01, "xanchor": "left"},
        barmode="group",
        template="plotly_white",
        height=510,
        margin={"l": 28, "r": 25, "t": 75, "b": 55},
        legend={
            "title": {"text": "Escenario"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={"title": titulo_eje_x, "showgrid": True, "zeroline": True},
        yaxis={"title": None, "autorange": "reversed"},
        hovermode="closest",
        uirevision="resultados-reproducibles",
        meta={
            "origen_datos": origen,
            "columnas_usadas": list(columnas_usadas),
            "unidad": unidad,
        },
    )
    return figura


def _figura_categorias(
    datos: TablaEntrada,
    *,
    escenarios: Sequence[str],
    columna_valor: str,
    factor_visualizacion: float,
    unidad: str,
    etiqueta_valor: str,
    titulo: str,
    titulo_eje_x: str,
) -> go.Figure:
    tabla, origen = _cargar_tabla(datos)
    columnas = (
        "id_escenario",
        "naturaleza",
        "categoria",
        columna_valor,
    )
    _validar_columnas(tabla, columnas)
    _validar_numerica(tabla, columna_valor)
    seleccion = tabla.loc[tabla["id_escenario"].isin(escenarios)].copy()
    ausentes = [
        escenario
        for escenario in escenarios
        if escenario not in set(seleccion["id_escenario"])
    ]
    if ausentes:
        raise ValueError(
            "Faltan escenarios requeridos para la figura: " + ", ".join(ausentes)
        )
    if seleccion.duplicated(["id_escenario", "categoria"]).any():
        raise ValueError("Hay categorías duplicadas dentro de un escenario")

    categorias = list(dict.fromkeys(seleccion["categoria"].astype(str)))
    figura = go.Figure()
    for escenario in escenarios:
        bloque = seleccion.loc[seleccion["id_escenario"] == escenario].set_index(
            "categoria"
        )
        faltantes = [categoria for categoria in categorias if categoria not in bloque.index]
        if faltantes:
            raise ValueError(
                f"El escenario {escenario} no cubre todas las categorías: "
                + ", ".join(faltantes)
            )
        bloque = bloque.loc[categorias]
        valores = bloque[columna_valor].astype(float) * factor_visualizacion
        etiqueta = _etiqueta_escenario(escenario)
        datos_hover = [[etiqueta, unidad] for _ in bloque.index]
        figura.add_trace(
            go.Bar(
                name=etiqueta,
                x=valores.tolist(),
                y=categorias,
                orientation="h",
                marker_color=_COLORES_ESCENARIO.get(escenario, "#467599"),
                customdata=datos_hover,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Escenario: %{customdata[0]}<br>"
                    f"{etiqueta_valor}: %{{x:,.6f}} {unidad}"
                    "<extra></extra>"
                ),
            )
        )

    return _configurar_figura_categorias(
        figura,
        titulo=titulo,
        titulo_eje_x=titulo_eje_x,
        origen=origen,
        columnas_usadas=columnas,
        unidad=unidad,
    )


def crear_figura_demand_pull(datos: TablaEntrada) -> go.Figure:
    """Compara la producción inducida por categoría para E5 y E10 comparable."""

    return _figura_categorias(
        datos,
        escenarios=("E5_original", "E10_misma_metodologia"),
        columna_valor="delta_x_millones_q_2013",
        factor_visualizacion=1.0,
        unidad="millones de Q de 2013",
        etiqueta_valor="Producción inducida",
        titulo="Gráfica 5. Producción inducida por categoría: E5 y E10",
        titulo_eje_x="Producción inducida (millones de Q de 2013)",
    )


def crear_figura_cost_push(datos: TablaEntrada) -> go.Figure:
    """Compara la propagación de precios para E5 y E10 comparable."""

    return _figura_categorias(
        datos,
        escenarios=(
            "E5_original",
            "E10_misma_metodologia",
        ),
        columna_valor="delta_precio_total_promedio_fraccion",
        factor_visualizacion=100.0,
        unidad="%",
        etiqueta_valor="Cambio propagado",
        titulo="Gráfica 4. Propagación de precios por categoría: E5 y E10",
        titulo_eje_x="Cambio promedio propagado (%)",
    )


def _seleccionar_emisiones(
    datos: TablaEntrada,
    *,
    escenario: str,
    columnas_adicionales: Sequence[str],
) -> tuple[pd.DataFrame, str, tuple[str, ...]]:
    tabla, origen = _cargar_tabla(datos)
    columnas = (
        "year",
        "data_status",
        "source_series_id",
        "scenario_id",
        *columnas_adicionales,
    )
    _validar_columnas(tabla, columnas)
    for columna in ("year", *columnas_adicionales):
        _validar_numerica(tabla, columna)
    seleccion = tabla.loc[tabla["scenario_id"] == escenario].copy()
    if seleccion.empty:
        raise ValueError(f"No hay filas para el escenario de emisiones {escenario!r}")
    if seleccion["year"].duplicated().any():
        raise ValueError(f"Hay años duplicados para el escenario {escenario!r}")
    seleccion = seleccion.sort_values("year", kind="stable").reset_index(drop=True)
    seleccion["year"] = seleccion["year"].astype(int)
    seleccion["estado_etiqueta"] = seleccion["data_status"].map(
        lambda estado: _ETIQUETAS_ESTADO.get(str(estado), str(estado))
    )
    return seleccion, origen, columnas


def _agregar_sombreado_estado(figura: go.Figure, tabla: pd.DataFrame) -> None:
    """Sombrea intervalos contiguos derivados de ``data_status``."""

    estados = tabla[["year", "data_status"]].drop_duplicates().sort_values("year")
    inicio: int | None = None
    final: int | None = None
    estado_actual: str | None = None
    intervalos: list[tuple[int, int, str]] = []
    for year, estado in estados.itertuples(index=False, name=None):
        year = int(year)
        estado = str(estado)
        if estado_actual is None:
            inicio = final = year
            estado_actual = estado
            continue
        if estado == estado_actual and final is not None and year == final + 1:
            final = year
            continue
        assert inicio is not None and final is not None
        intervalos.append((inicio, final, estado_actual))
        inicio = final = year
        estado_actual = estado
    if estado_actual is not None:
        assert inicio is not None and final is not None
        intervalos.append((inicio, final, estado_actual))

    for inicio, final, estado in intervalos:
        figura.add_vrect(
            x0=inicio - 0.5,
            x1=final + 0.5,
            fillcolor=_COLORES_ESTADO.get(estado, "rgba(70, 117, 153, 0.08)"),
            opacity=1.0,
            line_width=0,
            layer="below",
            annotation_text=_ETIQUETAS_ESTADO.get(estado, estado),
            annotation_position="top left",
        )


def _configurar_figura_emisiones(
    figura: go.Figure,
    *,
    titulo: str,
    origen: str,
    columnas_usadas: Sequence[str],
    escenario: str,
) -> go.Figure:
    figura.update_layout(
        title={"text": titulo, "x": 0.01, "xanchor": "left"},
        template="plotly_white",
        height=500,
        margin={"l": 65, "r": 45, "t": 80, "b": 55},
        legend={
            "title": {"text": "Serie / estado"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "groupclick": "togglegroup",
        },
        xaxis={"title": "Año", "dtick": 5, "showgrid": False},
        yaxis={"title": "Emisiones de escape (t CO₂ TTW)", "rangemode": "tozero"},
        hovermode="x unified",
        uirevision="resultados-reproducibles",
        meta={
            "origen_datos": origen,
            "columnas_usadas": list(columnas_usadas),
            "escenario": escenario,
            "unidad": "t CO₂ TTW",
        },
    )
    return figura


def crear_figura_emisiones_eia(
    datos: TablaEntrada, escenario: str = "E10"
) -> go.Figure:
    """Grafica E0 frente al escenario elegido en la actualización abierta EIA."""

    tabla, origen, columnas = _seleccionar_emisiones(
        datos,
        escenario=escenario,
        columnas_adicionales=("reference_co2_tonnes", "scenario_co2_tonnes"),
    )
    figura = go.Figure()
    especificaciones = (
        ("E0", "reference_co2_tonnes", "Gasolina de referencia (E0)"),
        (escenario, "scenario_co2_tonnes", escenario),
    )
    estados = list(dict.fromkeys(tabla["data_status"].astype(str)))
    for identificador, columna, etiqueta in especificaciones:
        for estado in estados:
            bloque = tabla.loc[tabla["data_status"] == estado]
            estado_etiqueta = _ETIQUETAS_ESTADO.get(estado, estado)
            customdata = [
                [etiqueta, estado_etiqueta, str(fuente), "t CO₂ TTW"]
                for fuente in bloque["source_series_id"]
            ]
            figura.add_trace(
                go.Scatter(
                    name=f"{etiqueta} · {estado_etiqueta}",
                    legendgroup=identificador,
                    legendgrouptitle_text=etiqueta,
                    x=bloque["year"].tolist(),
                    y=bloque[columna].astype(float).tolist(),
                    mode="lines+markers",
                    line={
                        "color": _COLORES_ESCENARIO.get(identificador, "#467599"),
                        "dash": "solid" if estado == "observed" else "dash",
                        "width": 2.2,
                    },
                    marker={"size": 5},
                    customdata=customdata,
                    hovertemplate=(
                        "Año: %{x}<br>"
                        "Escenario: %{customdata[0]}<br>"
                        "Emisiones: %{y:,.0f} t CO₂ TTW<br>"
                        "Estado: %{customdata[1]}<br>"
                        "Linaje: %{customdata[2]}<extra></extra>"
                    ),
                )
            )

    _agregar_sombreado_estado(figura, tabla)
    return _configurar_figura_emisiones(
        figura,
        titulo=f"Actualización abierta: E0 frente a {escenario}",
        origen=origen,
        columnas_usadas=columnas,
        escenario=escenario,
    )


def crear_figura_emisiones_evitadas(
    datos: TablaEntrada, escenario: str = "E10"
) -> go.Figure:
    """Grafica las emisiones evitadas anuales y su acumulado temporal."""

    tabla, origen, columnas = _seleccionar_emisiones(
        datos,
        escenario=escenario,
        columnas_adicionales=("avoided_co2_tonnes",),
    )
    tabla["evitadas_acumuladas_tonnes"] = tabla["avoided_co2_tonnes"].cumsum()
    customdata = [
        [
            escenario,
            estado,
            str(fuente),
            "t CO₂ TTW",
        ]
        for estado, fuente in zip(
            tabla["estado_etiqueta"], tabla["source_series_id"]
        )
    ]
    colores_barras = [
        "#78909C" if estado == "observed" else "#D79A55"
        for estado in tabla["data_status"]
    ]

    figura = go.Figure()
    figura.add_trace(
        go.Bar(
            name="Evitadas anuales",
            x=tabla["year"].tolist(),
            y=tabla["avoided_co2_tonnes"].astype(float).tolist(),
            marker_color=colores_barras,
            customdata=customdata,
            hovertemplate=(
                "Año: %{x}<br>"
                "Escenario: %{customdata[0]}<br>"
                "Evitadas anuales: %{y:,.0f} t CO₂ TTW<br>"
                "Estado: %{customdata[1]}<br>"
                "Linaje: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    figura.add_trace(
        go.Scatter(
            name="Evitadas acumuladas",
            x=tabla["year"].tolist(),
            y=tabla["evitadas_acumuladas_tonnes"].astype(float).tolist(),
            mode="lines+markers",
            line={"color": _COLORES_ESCENARIO.get(escenario, "#2F6F4E"), "width": 2.5},
            marker={"size": 5},
            yaxis="y2",
            customdata=customdata,
            hovertemplate=(
                "Año: %{x}<br>"
                "Escenario: %{customdata[0]}<br>"
                "Evitadas acumuladas: %{y:,.0f} t CO₂ TTW<br>"
                "Estado: %{customdata[1]}<br>"
                "Linaje: %{customdata[2]}<extra></extra>"
            ),
        )
    )
    _agregar_sombreado_estado(figura, tabla)
    figura.update_layout(
        title={
            "text": f"Emisiones evitadas anuales y acumuladas: {escenario}",
            "x": 0.01,
            "xanchor": "left",
        },
        template="plotly_white",
        height=500,
        margin={"l": 65, "r": 75, "t": 80, "b": 55},
        legend={
            "title": {"text": "Medida"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={"title": "Año", "dtick": 5, "showgrid": False},
        yaxis={"title": "Evitadas anuales (t CO₂ TTW)", "rangemode": "tozero"},
        yaxis2={
            "title": "Evitadas acumuladas (t CO₂ TTW)",
            "overlaying": "y",
            "side": "right",
            "rangemode": "tozero",
            "showgrid": False,
        },
        hovermode="x unified",
        uirevision="resultados-reproducibles",
        meta={
            "origen_datos": origen,
            "columnas_usadas": list(columnas),
            "columna_derivada": "cumsum(avoided_co2_tonnes) ordenado por year",
            "escenario": escenario,
            "unidad": "t CO₂ TTW",
        },
    )
    return figura


def _seleccionar_contexto_articulo(
    datos: TablaEntrada, contexto: str
) -> tuple[pd.DataFrame, str, tuple[str, ...]]:
    """Carga y selecciona una trayectoria anual del análisis del artículo."""

    tabla, origen = _cargar_tabla(datos)
    columnas = (
        "year",
        "data_status",
        "source_lineage",
        "value_status",
        "scenario_context",
        "scenario_id",
        "blend_share_applied",
        "reference_co2_tonnes",
        "scenario_co2_tonnes",
        "avoided_co2_tonnes",
    )
    _validar_columnas(tabla, columnas)
    for columna in (
        "year",
        "blend_share_applied",
        "reference_co2_tonnes",
        "scenario_co2_tonnes",
        "avoided_co2_tonnes",
    ):
        _validar_numerica(tabla, columna)
    seleccion = tabla.loc[tabla["scenario_context"] == contexto].copy()
    if seleccion.empty:
        raise ValueError(
            f"No hay filas del análisis para el contexto {contexto!r}"
        )
    if seleccion["year"].duplicated().any():
        raise ValueError(f"Hay años duplicados en el contexto {contexto!r}")
    seleccion = seleccion.sort_values("year", kind="stable").reset_index(drop=True)
    seleccion["year"] = seleccion["year"].astype(int)
    seleccion["estado_etiqueta"] = seleccion["data_status"].map(
        lambda estado: _ETIQUETAS_ESTADO.get(str(estado), str(estado))
    )
    return seleccion, origen, columnas


def _crear_figura_contrafactual_articulo(
    datos: TablaEntrada,
    *,
    contexto: str,
    titulo: str,
    etiqueta_escenario: str,
) -> go.Figure:
    tabla, origen, columnas = _seleccionar_contexto_articulo(datos, contexto)
    contexto_etiqueta = _CONTEXTOS_ARTICULO[contexto]
    customdata = [
        [
            estado,
            contexto_etiqueta,
            str(escenario),
            float(participacion),
            float(ev_avoided),
        ]
        for estado, escenario, participacion, ev_avoided in zip(
            tabla["estado_etiqueta"],
            tabla["scenario_id"],
            tabla["blend_share_applied"],
            tabla["avoided_co2_tonnes"],
        )
    ]

    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            name="Base E0",
            x=tabla["year"].tolist(),
            y=tabla["reference_co2_tonnes"].astype(float).tolist(),
            mode="lines+markers",
            line={"color": _COLORES_ESCENARIO["E0"], "width": 2.4},
            marker={"size": 5},
            customdata=customdata,
            hovertemplate=(
                "Año: %{x}<br>"
                "Serie: Base E0<br>"
                "Emisiones: %{y:,.0f} t CO₂ TTW<br>"
                "Estado: %{customdata[0]}<br>"
                "Contexto: %{customdata[1]}<br>"
                "Política aplicada: %{customdata[2]} "
                "(%{customdata[3]:.0%})<br>"
                "Evitadas frente a E0: %{customdata[4]:,.0f} t CO₂ TTW"
                "<extra></extra>"
            ),
        )
    )
    figura.add_trace(
        go.Scatter(
            name=etiqueta_escenario,
            x=tabla["year"].tolist(),
            y=tabla["scenario_co2_tonnes"].astype(float).tolist(),
            mode="lines+markers",
            line={"color": _COLORES_ESCENARIO["E10"], "width": 2.4},
            marker={"size": 5},
            fill="tonexty",
            fillcolor="rgba(47, 111, 78, 0.20)",
            customdata=customdata,
            hovertemplate=(
                "Año: %{x}<br>"
                "Escenario: %{customdata[2]} "
                "(%{customdata[3]:.0%})<br>"
                "Emisiones: %{y:,.0f} t CO₂ TTW<br>"
                "Evitadas: %{customdata[4]:,.0f} t CO₂ TTW<br>"
                "Estado: %{customdata[0]}<br>"
                "Contexto: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    _agregar_sombreado_estado(figura, tabla)
    figura.update_layout(
        title={
            "text": titulo,
            "x": 0.01,
            "xanchor": "left",
        },
        template="plotly_white",
        height=510,
        margin={"l": 65, "r": 40, "t": 85, "b": 55},
        legend={
            "title": {"text": "Serie"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={"title": "Año", "dtick": 5, "showgrid": False},
        yaxis={"title": "Emisiones de escape (t CO₂ TTW)", "rangemode": "tozero"},
        hovermode="x unified",
        uirevision="resultados-reproducibles",
        meta={
            "origen_datos": origen,
            "columnas_usadas": list(columnas),
            "scenario_context": contexto,
            "contexto": contexto_etiqueta,
            "unidad": "t CO₂ TTW",
        },
    )
    return figura


def crear_figura_emisiones_articulo_historica(datos: TablaEntrada) -> go.Figure:
    """Representa el contrafactual histórico 1986–2023 del artículo."""

    return _crear_figura_contrafactual_articulo(
        datos,
        contexto="historical_counterfactual_1986_2023",
        titulo="Gráfica 1. Emisiones históricas: base E0, E10 y área evitada",
        etiqueta_escenario="E10 + área evitada",
    )


def crear_figura_emisiones_articulo_prospectiva(datos: TablaEntrada) -> go.Figure:
    """Representa la política prospectiva: E0 en 2024–2025 y E10 desde 2026."""

    return _crear_figura_contrafactual_articulo(
        datos,
        contexto="prospective_policy_2024_2030",
        titulo=(
            "Gráfica 3. Emisiones prospectivas: base E0, política E0→E10 "
            "y área evitada"
        ),
        etiqueta_escenario="Política E0→E10 + área evitada",
    )


def crear_figura_emisiones_articulo_integrada(datos: TablaEntrada) -> go.Figure:
    """Representa la trayectoria integrada 1986–2030 con E10 en el periodo."""

    return _crear_figura_contrafactual_articulo(
        datos,
        contexto="integrated_figure_1986_2030",
        titulo="Gráfica 6. Emisiones integradas: base E0, E10 y área evitada",
        etiqueta_escenario="E10 + área evitada",
    )


def crear_figura_consumo_articulo(datos: TablaEntrada) -> go.Figure:
    """Representa el consumo final de gasolina en millones de galones."""

    tabla, origen = _cargar_tabla(datos)
    columnas = (
        "year",
        "data_status",
        "source_lineage",
        "million_us_gallons",
        "value_status",
    )
    _validar_columnas(tabla, columnas)
    for columna in ("year", "million_us_gallons"):
        _validar_numerica(tabla, columna)
    if tabla["year"].duplicated().any():
        raise ValueError("Hay años duplicados en la serie anual del artículo")
    tabla = tabla.sort_values("year", kind="stable").reset_index(drop=True)
    tabla["year"] = tabla["year"].astype(int)
    tabla["estado_etiqueta"] = tabla["data_status"].map(
        lambda estado: _ETIQUETAS_ESTADO.get(str(estado), str(estado))
    )
    contexto = "Serie de consumo final 1986–2030"
    customdata = [[estado, contexto] for estado in tabla["estado_etiqueta"]]

    figura = go.Figure()
    figura.add_trace(
        go.Scatter(
            name="Consumo final de gasolina",
            x=tabla["year"].tolist(),
            y=tabla["million_us_gallons"].astype(float).tolist(),
            mode="lines+markers",
            line={"color": "#356C95", "width": 2.4},
            marker={"size": 5},
            customdata=customdata,
            hovertemplate=(
                "Año: %{x}<br>"
                "Consumo final: %{y:,.3f} millones de galones EE. UU.<br>"
                "Estado: %{customdata[0]}<br>"
                "Contexto: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    _agregar_sombreado_estado(figura, tabla)
    figura.update_layout(
        title={
            "text": "Gráfica 2. Consumo final de gasolina (1986–2030)",
            "x": 0.01,
            "xanchor": "left",
        },
        template="plotly_white",
        height=500,
        margin={"l": 65, "r": 40, "t": 85, "b": 55},
        legend={
            "title": {"text": "Serie"},
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        xaxis={"title": "Año", "dtick": 5, "showgrid": False},
        yaxis={
            "title": "Consumo final (millones de galones EE. UU.)",
            "rangemode": "tozero",
        },
        hovermode="x unified",
        uirevision="resultados-reproducibles",
        meta={
            "origen_datos": origen,
            "columnas_usadas": list(columnas),
            "contexto": contexto,
            "unidad": "millones de galones EE. UU.",
        },
    )
    return figura


__all__ = [
    "crear_figura_cost_push",
    "crear_figura_demand_pull",
    "crear_figura_consumo_articulo",
    "crear_figura_emisiones_articulo_historica",
    "crear_figura_emisiones_articulo_integrada",
    "crear_figura_emisiones_articulo_prospectiva",
    "crear_figura_emisiones_eia",
    "crear_figura_emisiones_evitadas",
]
