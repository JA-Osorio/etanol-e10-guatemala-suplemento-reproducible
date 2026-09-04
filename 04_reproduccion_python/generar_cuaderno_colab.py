#!/usr/bin/env python3
"""Genera el cuaderno Colab del material suplementario reproducible."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "05_cuaderno_colab/reproducir_resultados_e10.ipynb"


def _clean(source: str) -> str:
    return dedent(source).strip() + "\n"


def markdown(cell_id: str, source: str) -> dict[str, Any]:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": _clean(source),
    }


def code(cell_id: str, title: str, source: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {
            "cellView": "form",
            "jupyter": {"source_hidden": True},
            "tags": ["hide-input"],
        },
        "outputs": [],
        "source": _clean(
            f'#@title {title} {{ display-mode: "form" }}\n' + dedent(source)
        ),
    }


CELLS = [
    markdown(
        "portada",
        r'''
        # Material suplementario reproducible

        ## Implementación tardía de la Ley del Alcohol Carburante: efectos económico-ambientales en Guatemala (1986–2030)

        Este cuaderno reconstruye los cálculos ambientales y económicos del
        artículo desde sus datos y parámetros. La exposición sigue el mismo
        recorrido científico: datos, construcción matemática, contrafactual de
        emisiones, proyección, modelo insumo-producto y resultados.

        Para reproducir todo en Google Colab, seleccione **Entorno de ejecución →
        Ejecutar todas**. El código está plegado para mantener la lectura centrada
        en el método; puede desplegarse en cualquier sección.
        ''',
    ),
    code(
        "preparar-entorno",
        "Preparar el entorno reproducible",
        r"""
        from pathlib import Path
        import os
        import subprocess
        import sys


        REPO_URL = "https://github.com/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible.git"
        MIP_URL = "https://github.com/JA-Osorio/mip-guatemala-2013-reproducible.git"
        DEFAULT_REF_REPO = "48bc80699d3aa2b44f942fdfe77febde75febf36"
        REF_REPO = os.environ.get("REF_REPO", DEFAULT_REF_REPO).strip()
        MIP_COMMIT = "5056c15fdeb4527bbee47c9e53d1c3d8dcee3ae3"


        def ejecutar(comando: list[str], *, cwd: Path | None = None) -> str:
            resultado = subprocess.run(
                comando, cwd=cwd, check=True, text=True, capture_output=True
            )
            return resultado.stdout.strip()


        def encontrar_raiz(inicio: Path) -> Path:
            for candidata in (inicio, *inicio.parents):
                if (candidata / "03_configuracion/emisiones_ttw.json").is_file():
                    return candidata
            raise FileNotFoundError("No se encontró el repositorio del suplemento.")


        EN_COLAB = "google.colab" in sys.modules
        if EN_COLAB:
            raiz = Path("/content/etanol-e10-guatemala-suplemento-reproducible")
            mip = Path("/content/mip-guatemala-2013-reproducible")
            if not (raiz / ".git").is_dir():
                ejecutar(["git", "clone", "--filter=blob:none", REPO_URL, str(raiz)])
            ejecutar(["git", "fetch", "origin", REF_REPO], cwd=raiz)
            ejecutar(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=raiz)

            if not (mip / ".git").is_dir():
                ejecutar(["git", "clone", "--filter=blob:none", MIP_URL, str(mip)])
            ejecutar(["git", "fetch", "origin", MIP_COMMIT], cwd=mip)
            ejecutar(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=mip)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-e", str(raiz)],
                check=True,
            )
        else:
            raiz = encontrar_raiz(Path.cwd().resolve())
            candidata_mip = Path(
                os.environ.get(
                    "MIP_GT_DIR",
                    str(raiz.parent / "mip-guatemala-2013-reproducible"),
                )
            ).resolve()
            mip = candidata_mip if candidata_mip.is_dir() else None

        src = raiz / "04_reproduccion_python/src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        print("Entorno preparado. Los cálculos se ejecutarán desde los insumos versionados.")
        """,
    ),
    markdown(
        "datos-parametros",
        r"""
        ## 1. Datos, unidades y parámetros

        | Componente | Contenido utilizado | Cobertura o unidad |
        |---|---|---|
        | Consumo final de gasolina | Serie anual del archivo tabular del proyecto; fuente declarada en el artículo: OLADE/sieLAC | 1986–2023, BTU por año |
        | Proyección | Tendencia log-lineal estimada sobre las diez observaciones más recientes | 2014–2023; predicción 2024–2030 |
        | Emisiones de escape | Factor de emisión de gasolina y poderes caloríficos usados por el cálculo fuente | t CO₂ por TJ y MJ por litro |
        | Economía | Matriz insumo-producto de Guatemala, versión 2013 | 152 productos; millones de quetzales a precios de 2013 |

        Los parámetros ambientales se mantienen iguales a los del cálculo del
        artículo:

        | Símbolo | Valor | Unidad | Papel en el cálculo |
        |---|---:|---|---|
        | $\kappa$ | 0.001055056 | MJ/BTU | Conversión energética |
        | $h_g$ | 32.0 | MJ/L | Poder calorífico inferior de la gasolina |
        | $h_e$ | 21.1 | MJ/L | Poder calorífico inferior del etanol |
        | $EF_g$ | 69.3 | t CO₂/TJ | Factor de emisión de la gasolina |
        | $s$ | 0.10 | L etanol/L mezcla | Mezcla E10 |

        Los datos y parámetros permanecen separados: la serie anual aporta
        cantidades, mientras que la configuración fija conversiones, escenarios
        y ventanas temporales.
        """,
    ),
    code(
        "calcular-emisiones",
        "Calcular las series ambientales desde los insumos",
        r"""
        import pandas as pd
        from IPython.display import Markdown, display

        from e10_gt.emisiones_ttw import (
            build_recovered_article_counterfactual,
            load_config,
            load_recovered_article_history,
        )
        from e10_gt.visualizaciones_interactivas import (
            crear_figura_consumo_articulo,
            crear_figura_cost_push,
            crear_figura_demand_pull,
            crear_figura_emisiones_articulo_historica,
            crear_figura_emisiones_articulo_integrada,
            crear_figura_emisiones_articulo_prospectiva,
        )


        configuracion_emisiones = load_config(raiz)
        ruta_serie_anual = (
            raiz
            / "01_datos/insumos_publicables/contrafactual_articulo_recuperado_1986_2023.csv"
        )
        assert ruta_serie_anual.is_file()
        historia, _ = load_recovered_article_history(raiz, configuracion_emisiones)
        filas_serie, filas_contrafactual, filas_resumen, ajuste = (
            build_recovered_article_counterfactual(historia, configuracion_emisiones)
        )

        serie = pd.DataFrame(filas_serie)
        contrafactual = pd.DataFrame(filas_contrafactual)
        resumen_periodos = pd.DataFrame(filas_resumen)

        parametros_amb = configuracion_emisiones["article_recovered_lineage"]
        kappa = float(parametros_amb["btu_to_mj"])
        h_g = float(parametros_amb["gasoline_lhv_mj_per_liter"])
        h_e = float(parametros_amb["ethanol_lhv_mj_per_liter"])
        s_e10 = float(parametros_amb["e10_volumetric_share"])
        ef_g = float(parametros_amb["co2_factor_tonnes_per_tj"])
        h_e10 = (1.0 - s_e10) * h_g + s_e10 * h_e
        r_e10 = h_e10 / h_g
        fraccion_evitada = 1.0 - (1.0 - s_e10) / r_e10

        historico = contrafactual.query(
            "scenario_context == 'historical_counterfactual_1986_2023'"
        ).copy()
        prospectivo = contrafactual.query(
            "scenario_context == 'prospective_policy_2024_2030'"
        ).copy()
        integrado = contrafactual.query(
            "scenario_context == 'integrated_figure_1986_2030'"
        ).copy()

        # Si cambia un insumo o una ecuación, la ejecución se detiene antes de
        # presentar resultados.
        assert len(historia) == 38
        assert serie["year"].tolist() == list(range(1986, 2031))
        assert abs(fraccion_evitada - 0.0682626981559366) < 1e-14
        assert abs(historico["avoided_co2_tonnes"].sum() - 7_121_034.096930633) < 1e-6
        assert abs(
            prospectivo.query("2026 <= year <= 2030")["avoided_co2_tonnes"].sum()
            - 2_848_498.696168207
        ) < 1e-6
        """,
    ),
    markdown(
        "mat-emisiones",
        r"""
        ## 2. Contrafactual de emisiones de escape

        Sea $B_t$ el consumo anual en BTU. Primero se convierte a terajulios:

        $$
        \kappa=0.001055056\ \mathrm{MJ/BTU},
        \qquad E_t=\frac{\kappa B_t}{10^6}
        \qquad [\mathrm{TJ/año}].
        $$

        Para una fracción volumétrica de etanol $s$, el poder calorífico de la
        mezcla y su contenido energético relativo son

        $$
        \bar h_s=(1-s)h_g+sh_e,
        \qquad R_s=\frac{\bar h_s}{h_g}.
        $$

        Si se mantiene constante el servicio energético, el volumen de mezcla es
        $V_{s,t}=E_t\times10^6/\bar h_s$. La gasolina fósil aporta
        $(1-s)V_{s,t}h_g$ MJ. De ahí se obtiene la trayectoria completa:

        $$
        EF_g=69.3\ \mathrm{t\ CO_2/TJ},
        \qquad C_{E0,t}=E_tEF_g,
        \qquad f_{g,s}=\frac{1-s}{R_s},
        \qquad C_{s,t}=C_{E0,t}f_{g,s},
        \qquad \Delta C_t=C_{E0,t}-C_{s,t}.
        $$

        Para E10:

        $$
        \bar h_{10}=0.9(32)+0.1(21.1)=30.91\ \mathrm{MJ/L},
        $$

        $$
        R_{10}=0.9659375,
        \qquad f_e=1-f_{g,10}=1-\frac{0.9}{0.9659375}
        =0.0682626982,
        \qquad C_{E10,t}=C_{E0,t}(1-f_e).
        $$

        Por tanto, el E10 reduce 6.8263 % de las emisiones TTW frente al E0 en
        cada año bajo este supuesto de servicio energético constante.
        """,
    ),
    code(
        "resultado-historico",
        "Gráfica 1 y resultado histórico 1986–2023",
        r'''
        fila_1986 = historico.loc[historico["year"] == 1986].iloc[0]
        resumen_historico = pd.DataFrame(
            [{
                "Periodo": "1986–2023",
                "E0 (t CO₂)": round(historico["reference_co2_tonnes"].sum()),
                "E10 (t CO₂)": round(historico["scenario_co2_tonnes"].sum()),
                "Evitadas (t CO₂)": round(historico["avoided_co2_tonnes"].sum()),
                "Reducción": f"{fraccion_evitada:.4%}",
            }]
        )
        display(
            Markdown(
                rf"""
                **Sustitución para 1986**

                $$
                E_{{1986}}=\frac{{{fila_1986['btu']:,.2f}(0.001055056)}}{{10^6}}
                ={fila_1986['energy_tj']:,.3f}\ \mathrm{{TJ}},
                $$

                $$
                C_{{0,1986}}={fila_1986['energy_tj']:,.3f}(69.3)
                ={fila_1986['reference_co2_tonnes']:,.0f}\ \mathrm{{t\ CO_2}},
                \qquad
                \Delta C_{{1986}}={fila_1986['avoided_co2_tonnes']:,.0f}\ \mathrm{{t\ CO_2}}.
                $$
                """
            )
        )
        display(resumen_historico.set_index("Periodo"))
        display(crear_figura_emisiones_articulo_historica(contrafactual))
        ''',
    ),
    markdown(
        "mat-consumo",
        r"""
        ### Conversión de energía a volumen

        La segunda gráfica expresa la misma serie en millones de galones de
        gasolina. Con $1\ \mathrm{gal}=3.785411784\ \mathrm{L}$ y, por tanto,
        $1\ \mathrm{L}=0.2641720524$ galones EE. UU.:

        $$
        L_t=\frac{E_t\times10^6}{h_g},
        \qquad
        G_t=\frac{E_t}{h_g}(0.2641720524)
        \quad[\text{millones de galones}].
        $$

        No se introduce una segunda serie: es una transformación de unidades de
        $E_t$.
        """,
    ),
    code(
        "resultado-consumo",
        "Gráfica 2 y conversión a millones de galones",
        r"""
        muestra_consumo = (
            serie.loc[
                serie["year"].isin([1986, 2023, 2030]),
                ["year", "energy_tj", "million_us_gallons"],
            ]
            .rename(columns={
                "year": "Año",
                "energy_tj": "Energía (TJ)",
                "million_us_gallons": "Consumo (millones de galones)",
            })
            .round({"Energía (TJ)": 3, "Consumo (millones de galones)": 3})
        )
        display(muestra_consumo.set_index("Año"))
        display(crear_figura_consumo_articulo(serie))
        """,
    ),
    markdown(
        "mat-proyeccion",
        r"""
        ## 3. Proyección 2024–2030

        Sobre la ventana 2014–2023 se estima por mínimos cuadrados ordinarios:

        $$
        \ln(E_t)=\beta_0+\beta_1(t-2014)+\varepsilon_t,
        \qquad
        \widehat E_t=\exp\!\left[\widehat\beta_0+
        \widehat\beta_1(t-2014)\right].
        $$

        La exponencial se retransmite directamente, sin corrección de *smearing*.
        La gráfica prospectiva conserva E0 en 2024–2025 y aplica E10 desde 2026:

        $$
        s_t=
        \begin{cases}
        0, & t\in\{2024,2025\},\\
        0.10, & 2026\leq t\leq 2030.
        \end{cases}
        $$

        Los agregados prospectivos se reportan para 2026–2030.
        """,
    ),
    code(
        "resultado-proyeccion",
        "Gráfica 3 y resultados prospectivos",
        r"""
        parametros_ajuste = pd.DataFrame([
            {"Parámetro": "Intercepto en 2014", "Valor": ajuste.intercept_at_center},
            {"Parámetro": "Pendiente anual", "Valor": ajuste.slope_per_year},
            {"Parámetro": "Crecimiento anual equivalente", "Valor": ajuste.annual_growth_rate},
            {"Parámetro": "R² en escala logarítmica", "Valor": ajuste.r_squared_log_scale},
            {"Parámetro": "RMSE en escala logarítmica", "Valor": ajuste.rmse_log_scale},
        ])
        parametros_ajuste["Valor"] = parametros_ajuste["Valor"].round(6)
        display(parametros_ajuste.set_index("Parámetro"))

        tabla_proyeccion = (
            prospectivo.query("2026 <= year <= 2030")
            [["year", "reference_co2_tonnes", "scenario_co2_tonnes", "avoided_co2_tonnes"]]
            .rename(columns={
                "year": "Año",
                "reference_co2_tonnes": "E0 (t CO₂)",
                "scenario_co2_tonnes": "E10 (t CO₂)",
                "avoided_co2_tonnes": "Evitadas (t CO₂)",
            })
            .round()
        )
        display(tabla_proyeccion.set_index("Año"))
        display(crear_figura_emisiones_articulo_prospectiva(contrafactual))
        """,
    ),
    markdown(
        "mat-economia",
        r"""
        ## 4. Modelo económico insumo-producto

        La matriz $Z\in\mathbb{R}^{152\times152}$ contiene los usos intermedios
        domésticos: $Z_{ij}$ es el insumo del producto $i$ utilizado por el
        producto $j$, en millones de quetzales a precios de 2013. Con el vector de
        utilización $x$:

        $$
        A=Z\operatorname{diag}(x)^{-1},
        \qquad L=(I-A)^{-1}.
        $$

        La especificación del archivo de cálculo resta 23.987996 millones de
        quetzales al valor canónico de $x_{P105}$ antes de construir $A$, de modo
        que $x_{P105}=11{,}393.680408$ millones. El residual
        $x_j-\sum_iZ_{ij}$ no se interpreta como valor agregado bruto.

        ### Escenarios económicos

        El archivo de cálculo que sustenta el bloque económico del artículo usa
        **E5** ($s=0.05$). Para conservar ese punto de referencia y corregir el
        escenario, este cuaderno presenta:

        1. la ejecución E5 con sus parámetros originales; y
        2. un E10 comparable, que cambia únicamente $s$ de 0.05 a 0.10.

        Ambos escenarios se comparan con E0. Los demás supuestos permanecen
        constantes:

        | Parámetro | Valor | Interpretación |
        |---|---:|---|
        | $P_g$ | Q10.50/L | Precio de gasolina |
        | $P_e$ | Q7.50/L | Precio de etanol |
        | $\alpha$ | 0.45 | Participación atribuida a gasolina dentro de P068 |
        | $\pi$ | 0.03 | Penalización energética fija del archivo de cálculo |
        | $\delta$ | 0.70 | Participación doméstica atribuida al etanol |
        | P010 | — | Producto usado como aproximación de la demanda de caña |

        Estos valores son supuestos de la especificación económica; no son
        observaciones adicionales de la MIP. Las cifras Q4.77 millones y el
        multiplicador 1.13 impresos en el artículo no son producidos por esta
        especificación y no se usan como metas de calibración.
        """,
    ),
    code(
        "calcular-economia",
        "Calcular E5 y E10 desde la MIP 2013",
        r"""
        from e10_gt.economia_articulo import ejecutar_economia_articulo


        calculo_economico = ejecutar_economia_articulo(
            raiz, escribir_resultados=False, raiz_mip=mip
        )
        ids_principales = ["E5_original", "E10_misma_metodologia"]
        escenarios = pd.DataFrame(calculo_economico["escenarios"])
        escenarios = escenarios.loc[
            escenarios["id_escenario"].isin(ids_principales)
        ].copy()
        productos = pd.DataFrame(calculo_economico["resultados_por_producto"])
        productos = productos.loc[
            productos["id_escenario"].isin(ids_principales)
        ].copy()
        categorias_demanda = pd.DataFrame(calculo_economico["categorias_demanda"])
        categorias_demanda = categorias_demanda.loc[
            categorias_demanda["id_escenario"].isin(ids_principales)
        ].copy()

        etiquetas_escenario = {
            "E5_original": "E5 (cálculo del artículo)",
            "E10_misma_metodologia": "E10 comparable",
        }
        categorias_demanda["categoria"] = categorias_demanda["categoria"].replace({
            "Cana de azucar": "Caña de azúcar",
            "Industria quimica ampliada": "Industria química",
            "Transporte y logistica": "Transporte y logística",
            "Combustibles y refinacion": "Combustibles y refinación",
        })

        conjuntos_cost_push = {
            "Transporte (P104–P105)": {"P104", "P105"},
            "Industria química (P071–P076)": {
                f"P{numero:03d}" for numero in range(71, 77)
            },
            "Servicios (sin P104–P109)": {
                f"P{numero:03d}" for numero in range(101, 151)
            } - {f"P{numero:03d}" for numero in range(104, 110)},
            "Agricultura (sin P010)": {
                f"P{numero:03d}" for numero in range(1, 31)
            } - {"P010"},
        }
        filas_cost_push = []
        for escenario_id in ids_principales:
            bloque = productos.loc[productos["id_escenario"] == escenario_id]
            for categoria, codigos in conjuntos_cost_push.items():
                seleccion = bloque.loc[bloque["codigo"].isin(codigos)]
                assert len(seleccion) == len(codigos)
                filas_cost_push.append({
                    "id_escenario": escenario_id,
                    "naturaleza": etiquetas_escenario[escenario_id],
                    "categoria": categoria,
                    "delta_precio_total_promedio_fraccion": seleccion[
                        "delta_precio_total_fraccion"
                    ].mean(),
                })
        precios_figura = pd.DataFrame(filas_cost_push)

        por_escenario = escenarios.set_index("id_escenario")
        e5 = por_escenario.loc["E5_original"]
        e10 = por_escenario.loc["E10_misma_metodologia"]
        assert len(productos) == 304
        assert abs(e5["delta_x_total_millones_q_2013"] - 3.166771669703373) < 1e-12
        assert abs(e10["delta_x_total_millones_q_2013"] - 6.333543339406746) < 1e-12
        """,
    ),
    markdown(
        "mat-cost-push",
        r"""
        ### Canal de costos (*cost-push*)

        Sea $s$ la fracción de etanol, $P_s$ el precio de la mezcla y $r_s$ el
        choque inicial frente a gasolina E0:

        $$
        P_s=(1-s)P_g+sP_e,
        \qquad r_s=\frac{P_s(1+\pi)}{P_g}-1.
        $$

        El choque que entra al producto $j$ y su propagación son

        $$
        d_j=r_s\alpha A_{P068,j},
        \qquad \Delta p^{\mathsf T}=d^{\mathsf T}L.
        $$

        La sustitución de los parámetros muestra por qué 1.53 % es el choque
        inicial E5, no el resultado propagado del transporte:

        $$
        P_5=0.95(10.50)+0.05(7.50)=10.35,
        \qquad r_5=\frac{10.35(1.03)}{10.50}-1=1.528571\%,
        $$

        $$
        P_{10}=0.90(10.50)+0.10(7.50)=10.20,
        \qquad r_{10}=\frac{10.20(1.03)}{10.50}-1=0.057143\%.
        $$

        Con estos precios y la penalización fija de 3 %, el choque E10 resulta
        menor que el E5. Es una consecuencia de esos supuestos, no una regla
        general sobre mezclas de etanol.
        """,
    ),
    code(
        "resultado-cost-push",
        "Gráfica 4 y resultados de propagación de precios",
        r"""
        filas_resumen_precios = []
        for escenario_id in ids_principales:
            fila = por_escenario.loc[escenario_id]
            por_categoria = precios_figura.loc[
                precios_figura["id_escenario"] == escenario_id
            ].set_index("categoria")
            filas_resumen_precios.append({
                "Escenario": etiquetas_escenario[escenario_id],
                "Choque inicial (%)": 100.0 * fila["r_fraccion"],
                "Transporte P104–P105 (%)": 100.0 * por_categoria.loc[
                    "Transporte (P104–P105)", "delta_precio_total_promedio_fraccion"
                ],
                "Industria química (%)": 100.0 * por_categoria.loc[
                    "Industria química (P071–P076)", "delta_precio_total_promedio_fraccion"
                ],
                "Servicios (%)": 100.0 * por_categoria.loc[
                    "Servicios (sin P104–P109)", "delta_precio_total_promedio_fraccion"
                ],
                "Agricultura (%)": 100.0 * por_categoria.loc[
                    "Agricultura (sin P010)", "delta_precio_total_promedio_fraccion"
                ],
            })
        resumen_precios = pd.DataFrame(filas_resumen_precios)
        display(resumen_precios.set_index("Escenario").round(6))
        display(crear_figura_cost_push(precios_figura))
        """,
    ),
    markdown(
        "mat-demand-pull",
        r"""
        ### Canal de demanda (*demand-pull*)

        $U_{068}=\sum_jZ_{P068,j}$ es la utilización intermedia doméstica de
        P068; no representa el consumo físico nacional de gasolina. El archivo de
        cálculo construye una aproximación monetaria de demanda doméstica de
        etanol:

        $$
        G_g=\alpha U_{068},
        \qquad D_s=\delta sG_g,
        \qquad \Delta y=D_se_{P010}.
        $$

        La respuesta productiva y el multiplicador $m$ son

        $$
        \Delta x=L\Delta y,
        \qquad
        m=\frac{\mathbf 1^{\mathsf T}\Delta x}
        {\mathbf 1^{\mathsf T}\Delta y}.
        $$

        Con $U_{068}=119.187526$ y $G_g=0.45U_{068}=53.634386$ millones de
        quetzales de 2013:

        $$
        D_5=0.70(0.05)(53.634386)=1.877204,
        \qquad D_{10}=0.70(0.10)(53.634386)=3.754407.
        $$

        Esta ecuación aplica la participación volumétrica como proporción de un
        agregado monetario. La penalización energética no entra en este canal;
        esa es una limitación de la especificación que se conserva para comparar
        E5 y E10 sin cambiar simultáneamente el método.
        """,
    ),
    code(
        "resultado-demand-pull",
        "Gráfica 5 y resultados de producción inducida",
        r"""
        resumen_demanda = pd.DataFrame([
            {
                "Escenario": etiquetas_escenario[escenario_id],
                "Demanda final adicional (millones Q2013)": por_escenario.loc[
                    escenario_id, "delta_y_total_millones_q_2013"
                ],
                "Producción inducida total (millones Q2013)": por_escenario.loc[
                    escenario_id, "delta_x_total_millones_q_2013"
                ],
                "Producción P010 (millones Q2013)": por_escenario.loc[
                    escenario_id, "delta_x_p010_millones_q_2013"
                ],
                "Multiplicador": por_escenario.loc[
                    escenario_id, "multiplicador_produccion"
                ],
            }
            for escenario_id in ids_principales
        ])
        display(resumen_demanda.set_index("Escenario").round(6))
        display(crear_figura_demand_pull(categorias_demanda))
        """,
    ),
    markdown(
        "mat-integracion",
        r"""
        ## 5. Síntesis ambiental 1986–2030

        La gráfica integrada aplica E10 a los 45 años de 1986–2030:

        $$
        s_t=0.10\quad\forall t\in[1986,2030],
        \qquad \Delta C_{\mathrm{continuo}}
        =\sum_{t=1986}^{2030}\Delta C_t.
        $$

        El total tabulado en el artículo responde a otra suma:

        $$
        \Delta C_{\mathrm{dos\ periodos}}=
        \sum_{t=1986}^{2023}\Delta C_t+
        \sum_{t=2026}^{2030}\Delta C_t.
        $$

        Por tanto, la tabla reúne dos ventanas disjuntas —1986–2023 y 2026–2030—,
        omite 2024–2025 y suma 43 años; la gráfica integrada contiene 45. La
        diferencia corresponde exactamente a los dos años omitidos. El costo de
        inacción coherente con el horizonte 1986–2025 declarado en el artículo añade esos dos años
        proyectados al bloque 1986–2023.
        """,
    ),
    code(
        "resultado-integracion",
        "Gráfica 6 y comparación de las agregaciones",
        r"""
        fila_dos_periodos = resumen_periodos.loc[
            resumen_periodos["period_id"]
            == "reported_periods_combined_excluding_2024_2025"
        ].iloc[0]
        evitadas_continuas = integrado["avoided_co2_tonnes"].sum()
        evitadas_2024_2025 = integrado.loc[
            integrado["year"].isin([2024, 2025]), "avoided_co2_tonnes"
        ].sum()
        inaccion_1986_2025 = integrado.loc[
            integrado["year"] <= 2025, "avoided_co2_tonnes"
        ].sum()
        prospectivo_2026_2030 = integrado.loc[
            integrado["year"] >= 2026, "avoided_co2_tonnes"
        ].sum()
        assert abs(
            evitadas_continuas
            - fila_dos_periodos["avoided_co2_tonnes"]
            - evitadas_2024_2025
        ) < 1e-6
        assert abs(
            inaccion_1986_2025 + prospectivo_2026_2030 - evitadas_continuas
        ) < 1e-6

        tabla_agregaciones = pd.DataFrame([
            {
                "Agregación": "Dos periodos del cuadro",
                "Años incluidos": "1986–2023 y 2026–2030",
                "Número de años": 43,
                "Evitadas (t CO₂)": fila_dos_periodos["avoided_co2_tonnes"],
            },
            {
                "Agregación": "Costo de inacción hasta 2025",
                "Años incluidos": "1986–2025",
                "Número de años": 40,
                "Evitadas (t CO₂)": inaccion_1986_2025,
            },
            {
                "Agregación": "Beneficio prospectivo",
                "Años incluidos": "2026–2030",
                "Número de años": 5,
                "Evitadas (t CO₂)": prospectivo_2026_2030,
            },
            {
                "Agregación": "Trayectoria continua de la Gráfica 6",
                "Años incluidos": "1986–2030",
                "Número de años": 45,
                "Evitadas (t CO₂)": evitadas_continuas,
            },
        ])
        tabla_agregaciones["Evitadas (t CO₂)"] = (
            tabla_agregaciones["Evitadas (t CO₂)"].round().astype("int64")
        )
        display(tabla_agregaciones.set_index("Agregación"))
        display(crear_figura_emisiones_articulo_integrada(contrafactual))
        """,
    ),
    markdown(
        "alcance-y-archivos",
        r"""
        ## 6. Alcance y archivos reproducibles

        - Las emisiones son de escape (**TTW**); no representan un análisis de
          ciclo de vida.
        - El bloque económico es un ejercicio lineal y estático con la MIP 2013.
          P068 agrupa combustibles, su base es la utilización intermedia doméstica
          y P010 funciona como aproximación de la demanda de caña.
        - El E10 económico es un recálculo comparable del E5: cambia la fracción
          de mezcla, pero conserva precios, participación doméstica y penalización
          fija. No debe interpretarse como una estimación integral de toda la
          economía nacional.
        - Los valores monetarios están expresados en millones de quetzales a
          precios de 2013.

        La cadena puede revisarse en los siguientes archivos del repositorio:

        | Etapa | Archivo |
        |---|---|
        | Serie anual de entrada | [CSV anual 1986–2023](../01_datos/insumos_publicables/contrafactual_articulo_recuperado_1986_2023.csv) |
        | Parámetros ambientales | [Configuración de emisiones](../03_configuracion/emisiones_ttw.json) |
        | Parámetros económicos | [Configuración económica](../03_configuracion/economia_articulo.json) |
        | Cálculo ambiental | [Módulo de emisiones](../04_reproduccion_python/src/e10_gt/emisiones_ttw.py) |
        | Cálculo económico | [Módulo insumo-producto](../04_reproduccion_python/src/e10_gt/economia_articulo.py) |

        **Cita sugerida:** Osorio, J. A., Villatoro, S. P. y Salguero, N.
        *Material suplementario reproducible para el análisis de la Ley del
        Alcohol Carburante en Guatemala*.
        """,
    ),
]


NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "colab": {"name": "reproducir_resultados_e10.ipynb", "provenance": []},
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_PATH.write_text(
        json.dumps(NOTEBOOK, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(NOTEBOOK_PATH)


if __name__ == "__main__":
    main()
