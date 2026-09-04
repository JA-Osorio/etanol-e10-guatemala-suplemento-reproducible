#!/usr/bin/env python3
"""Genera el cuaderno Colab auditable con estructura e identificadores estables.

El cuaderno versionado no conserva salidas. Su narrativa deja visibles los
supuestos, las ecuaciones y las sustituciones numéricas, mientras que las
celdas técnicas quedan plegadas de forma predeterminada en Google Colab.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    REPO_ROOT / "05_cuaderno_colab" / "reproducir_resultados_e10.ipynb"
)


def _clean(source: str) -> str:
    """Normaliza sangría y deja exactamente un salto final."""

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
        r"""
        # Auditoría matemática reproducible: economía E5/E10 y emisiones TTW E10

        Este cuaderno reconstruye la cadena **fuente → supuesto → ecuación →
        sustitución numérica → resultado → control**. El código operativo se
        mantiene plegado; la matemática y las advertencias de alcance permanecen
        visibles.

        **Corrección central.** El bloque económico heredado se calculó con **E5**,
        aunque el manuscrito lo describió como E10. Por ello se presentan, sin
        mezclarlos: (1) la reproducción forense E5, (2) la corrección comparable
        E10 y (3) una sensibilidad E10 con penalización energética LHV.

        **Recuperación ambiental.** Un cuaderno fuente privado conserva
        las curvas anuales que originaron las cuatro figuras del artículo. El flujo
        reconstruye esos valores, su ajuste 2014–2023 y sus contextos históricos,
        prospectivos e integrados. Una copia externa del libro primario fue
        recuperada y sus 38 observaciones coinciden con la reconstrucción al
        serializarlas con 15 cifras significativas. El libro no se redistribuye:
        su procedencia estadística y licencia aún deben documentarse. Esta rama de
        revisión omite nombres, IDs y huellas de los artefactos privados.

        La actualización EIA se mantiene como un linaje opcional e independiente.
        """,
    ),
    markdown(
        "mapa-auditoria",
        """
        ## 1. Identidad de la ejecución

        La dependencia MIP está fijada a la versión **v1.0.0** y al *commit*
        `5056c15fdeb4527bbee47c9e53d1c3d8dcee3ae3`. La variable `REF_REPO`
        identifica la revisión de este suplemento. En una copia local se usa el
        `HEAD` comprobado; en esta versión de revisión, Colab usa de forma
        predeterminada la rama `revision-e5-e10-trazabilidad`. Se emite una
        advertencia porque sigue siendo una referencia mutable. Para una
        reproducción archivística debe sustituirse por un *commit* completo.

        El flujo cuantitativo se ejecuta antes de leer resultados. Todas las tablas
        y figuras posteriores consumen exclusivamente archivos CSV o JSON
        regenerados en `06_resultados/` y `07_verificacion/`.
        """,
    ),
    code(
        "preparar-entorno",
        "Preparar entorno y fijar revisiones",
        r"""
        from pathlib import Path
        import json
        import math
        import os
        import subprocess
        import sys
        import warnings


        REPO_URL = "https://github.com/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible.git"
        MIP_URL = "https://github.com/JA-Osorio/mip-guatemala-2013-reproducible.git"
        DEFAULT_REF_REPO = "revision-e5-e10-trazabilidad"
        REF_REPO_SOLICITADA = os.environ.get("REF_REPO", "").strip()
        REF_REPO = REF_REPO_SOLICITADA or DEFAULT_REF_REPO
        MIP_VERSION = "v1.0.0"
        MIP_COMMIT = "5056c15fdeb4527bbee47c9e53d1c3d8dcee3ae3"


        def ejecutar(comando: list[str], *, cwd: Path | None = None) -> str:
            resultado = subprocess.run(
                comando,
                cwd=cwd,
                check=True,
                text=True,
                capture_output=True,
            )
            return resultado.stdout.strip()


        def encontrar_raiz_repo(inicio: Path) -> Path:
            for candidata in (inicio, *inicio.parents):
                if (candidata / "04_reproduccion_python" / "reproducir_todo.py").is_file():
                    return candidata
            raise FileNotFoundError("No se encontró la raíz del suplemento.")


        EN_COLAB = "google.colab" in sys.modules
        if EN_COLAB:
            raiz = Path("/content/etanol-e10-guatemala-suplemento-reproducible")
            mip = Path("/content/mip-guatemala-2013-reproducible")
            if not (raiz / ".git").is_dir():
                ejecutar(["git", "clone", "--filter=blob:none", REPO_URL, str(raiz)])
            ejecutar(["git", "fetch", "origin", REF_REPO], cwd=raiz)
            ejecutar(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=raiz)
            REF_REPO = ejecutar(["git", "rev-parse", "HEAD"], cwd=raiz)

            if not (mip / ".git").is_dir():
                ejecutar(["git", "clone", "--filter=blob:none", MIP_URL, str(mip)])
            ejecutar(["git", "fetch", "origin", MIP_COMMIT], cwd=mip)
            ejecutar(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=mip)
            assert ejecutar(["git", "rev-parse", "HEAD"], cwd=mip) == MIP_COMMIT
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-e", f"{raiz}[test]"],
                check=True,
            )
        else:
            raiz = encontrar_raiz_repo(Path.cwd().resolve())
            candidata_mip = Path(
                os.environ.get(
                    "MIP_GT_DIR",
                    str(raiz.parent / "mip-guatemala-2013-reproducible"),
                )
            ).resolve()
            mip = candidata_mip if candidata_mip.is_dir() else None
            if not REF_REPO_SOLICITADA:
                REF_REPO = ejecutar(["git", "rev-parse", "HEAD"], cwd=raiz)

        if REF_REPO in {"main", "master", DEFAULT_REF_REPO}:
            warnings.warn(
                "REF_REPO usa una rama mutable. Fije un commit completo para archivar la ejecución.",
                stacklevel=1,
            )

        CAMBIOS_NO_VERSIONADOS = bool(
            ejecutar(["git", "status", "--porcelain"], cwd=raiz)
        )
        if CAMBIOS_NO_VERSIONADOS:
            warnings.warn(
                "La copia local contiene cambios sin commit; el HEAD impreso no "
                "identifica por sí solo todo el contenido ejecutado.",
                stacklevel=1,
            )

        src = raiz / "04_reproduccion_python" / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))

        print(f"Suplemento: {REF_REPO}")
        print(
            "Estado Git: "
            + ("cambios sin commit" if CAMBIOS_NO_VERSIONADOS else "limpio")
        )
        print(f"MIP: {MIP_VERSION} / {MIP_COMMIT}")
        """,
    ),
    code(
        "ejecutar-pipeline",
        "Regenerar resultados y ejecutar pruebas",
        r"""
        comando = [
            sys.executable,
            str(raiz / "04_reproduccion_python" / "reproducir_todo.py"),
            "--sin-figuras",
        ]
        if mip is not None:
            comando.extend(["--mip-dir", str(mip)])

        subprocess.run(comando, cwd=raiz, check=True)
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "07_verificacion/tests"],
            cwd=raiz,
            check=True,
        )
        print("Flujo y pruebas completados sin errores.")
        """,
    ),
    code(
        "cargar-salidas",
        "Cargar únicamente salidas CSV y JSON regeneradas",
        r"""
        import pandas as pd
        from IPython.display import Markdown, display

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


        SALIDAS = {
            "resumen_economia": "06_resultados/economia_articulo/resumen_economia_articulo.json",
            "escenarios_economia": "06_resultados/economia_articulo/resumen_escenarios.csv",
            "demanda": "06_resultados/economia_articulo/categorias_demanda.csv",
            "precios": "06_resultados/economia_articulo/categorias_precios.csv",
            "reconciliacion": "06_resultados/economia_articulo/reconciliacion_articulo.csv",
            "serie_articulo": "06_resultados/emisiones/serie_articulo_anual.csv",
            "contrafactual_articulo": "06_resultados/emisiones/contrafactual_articulo_anual.csv",
            "resumen_contrafactual": "06_resultados/emisiones/contrafactual_articulo_resumen.csv",
            "publicada_agregada": "06_resultados/emisiones/reproduccion_publicada.csv",
            "eia_anual": "06_resultados/emisiones/actualizacion_eia_anual.csv",
            "eia_resumen": "06_resultados/emisiones/actualizacion_eia_resumen.csv",
            "comparacion_linajes": "06_resultados/emisiones/comparacion_linajes.csv",
            "diagnostico_eia": "07_verificacion/diagnostico_proyeccion_emisiones.json",
            "controles_economia": "07_verificacion/controles_economia_articulo.csv",
            "controles_emisiones": "07_verificacion/controles_emisiones_ttw.csv",
            "manifiesto": "07_verificacion/manifiesto_resultados.csv",
        }


        def ruta_salida(nombre: str) -> Path:
            ruta = raiz / SALIDAS[nombre]
            if not ruta.is_file():
                raise FileNotFoundError(f"Falta la salida regenerada: {ruta}")
            return ruta


        def cargar_csv(nombre: str) -> pd.DataFrame:
            return pd.read_csv(ruta_salida(nombre))


        def cargar_json(nombre: str) -> dict:
            with ruta_salida(nombre).open(encoding="utf-8") as archivo:
                return json.load(archivo)


        resumen_economia = cargar_json("resumen_economia")
        escenarios_economia = cargar_csv("escenarios_economia")
        categorias_demanda = cargar_csv("demanda")
        categorias_precios = cargar_csv("precios")
        reconciliacion = cargar_csv("reconciliacion")
        serie_articulo = cargar_csv("serie_articulo")
        contrafactual_articulo = cargar_csv("contrafactual_articulo")
        resumen_contrafactual = cargar_csv("resumen_contrafactual")
        publicada_agregada = cargar_csv("publicada_agregada")
        eia_anual = cargar_csv("eia_anual").query("scenario_id == 'E10'").copy()
        eia_resumen = cargar_csv("eia_resumen").query("scenario_id == 'E10'").copy()
        comparacion_linajes = cargar_csv("comparacion_linajes")
        diagnostico_eia = cargar_json("diagnostico_eia")
        controles_economia = cargar_csv("controles_economia")
        controles_emisiones = cargar_csv("controles_emisiones")
        manifiesto = cargar_csv("manifiesto")
        """,
    ),
    markdown(
        "linaje-explicacion",
        """
        ## 2. Tabla de linaje

        Cada fila identifica la procedencia que alimenta un bloque. Las huellas de
        los insumos públicos de la MIP salen del JSON regenerado por el propio
        flujo. Los nombres, IDs y huellas del manuscrito y de los cuadernos privados
        se omiten en esta rama de revisión. Las salidas de dos cuadernos coinciden y
        las 38 observaciones históricas se verificaron contra una copia recuperada
        del Excel primario. El Excel no se redistribuye porque su procedencia y
        licencia no están documentadas. La
        serie EIA conserva identificador, fecha y unidad en el diagnóstico. Ambos
        linajes ambientales se comparan, pero nunca se concatenan.
        """,
    ),
    code(
        "mostrar-linaje",
        "Mostrar fuentes, huellas y diferencia entre linajes",
        r"""
        filas_linaje = []
        for insumo in resumen_economia["insumos"]:
            filas_linaje.append(
                {
                    "bloque": "Economía MIP",
                    "artefacto_o_serie": insumo["archivo"],
                    "identificador": insumo["sha256_observado"],
                    "verificado": bool(insumo["coincide"]),
                    "alcance": "Construcción A, L y residual",
                }
            )

        manuscrito = resumen_economia["fuente_manuscrito"]
        filas_linaje.append(
            {
                "bloque": "Economía manuscrito",
                "artefacto_o_serie": "Manuscrito del artículo (archivo privado)",
                "identificador": "omitido en rama pública",
                "verificado": True,
                "alcance": "Afirmaciones económicas por reconciliar",
            }
        )
        articulo_recuperado = diagnostico_eia["article_recovered"]["source_metadata"]
        for rol, cuaderno in (
            ("principal", articulo_recuperado["primary_notebook"]),
            ("corroborante", articulo_recuperado["corroborating_notebook"]),
        ):
            filas_linaje.append(
                {
                    "bloque": "Contrafactual del artículo",
                    "artefacto_o_serie": f"{rol}: cuaderno privado",
                    "identificador": "omitido en rama pública",
                    "verificado": True,
                    "alcance": "Salidas anuales del cuaderno recuperado",
                }
            )
        workbook = articulo_recuperado["expected_workbook"]
        filas_linaje.append(
            {
                "bloque": "Fuente primaria referida",
                "artefacto_o_serie": "Libro primario externo",
                "identificador": (
                    f"hoja {workbook['sheet']} · identificador omitido"
                ),
                "verificado": True,
                "alcance": (
                    "Copia externa verificada; no redistribuida por licencia "
                    "y procedencia pendientes"
                ),
            }
        )

        fuente_eia = diagnostico_eia["source_metadata"]
        filas_linaje.append(
            {
                "bloque": "Actualización ambiental",
                "artefacto_o_serie": fuente_eia["name"],
                "identificador": fuente_eia["series_id"],
                "verificado": True,
                "alcance": f"{fuente_eia['units']}; actualización {fuente_eia['last_updated']}",
            }
        )
        display(pd.DataFrame(filas_linaje))
        display(Markdown("### Diferencia cuantificada: artículo recuperado frente a EIA"))
        display(comparacion_linajes)
        """,
    ),
    markdown(
        "mat-mip",
        r"""
        ## 3. Construcción de la MIP antes de los resultados

        Para cada producto $j$, el coeficiente técnico doméstico divide el flujo
        intermedio por la utilización total reconstruida:

        
        \[
        A_{ij}=\frac{Z_{ij}}{x_j},\qquad
        L=(I-A)^{-1},\qquad
        v^{\mathrm{res}}_j=x_j-\sum_i Z_{ij}.
        \]

        El vector $v^{\mathrm{res}}$ es un **residual no intermedio doméstico**;
        no debe denominarse valor agregado. La identidad numérica controlada es
        $(I-A)L=I$. El ajuste histórico del producto P105 se aplica antes de
        construir $A$.
        """,
    ),
    code(
        "resultado-mip",
        "Sustituir ajuste MIP y mostrar controles algebraicos",
        r'''
        reconstruccion = resumen_economia["reconstruccion_instantanea_historica"]
        display(
            Markdown(
                rf"""
                **Sustitución P105 (millones de Q de 2013)**

                \[
                x_{{P105}}^{{hist}}=
                {reconstruccion['x_canonico_millones_q_2013']:.12f}
                -{reconstruccion['ajuste_restar_millones_q_2013']:.12f}
                ={reconstruccion['x_historico_reconstruido_millones_q_2013']:.12f}.
                \]
                """
            )
        )
        controles_mip = controles_economia.loc[
            controles_economia["control"].isin(
                [
                    "dimension_productos",
                    "ajuste_historico_p105",
                    "definicion_residual_no_intermedio_domestico",
                    "identidad_inversa_leontief",
                ]
            )
        ]
        display(controles_mip)
        ''',
    ),
    markdown(
        "mat-cost-push",
        r"""
        ## 4. Canal *cost-push*: ecuación antes de la figura

        Sea $s$ la fracción volumétrica de etanol, $p_g$ y $p_e$ los precios
        de gasolina y etanol, $k_s$ el factor de penalización energética y
        $\alpha$ la participación de gasolina en P068:

        \[
        p_s=(1-s)p_g+s p_e,\qquad
        r_s=\frac{p_s k_s}{p_g}-1,\qquad
        d_j=r_s\alpha A_{P068,j},\qquad
        \Delta p^{\mathsf T}=d^{\mathsf T}L.
        \]

        Para E5 y el E10 comparable se conserva $k_s=1.03$. La sensibilidad
        energética usa
        $k_{10}^{LHV}=32/[0.9(32)+0.1(21.2)]$. El promedio de transporte se
        calcula después de propagar, sobre P104–P105; no es el choque inicial
        $r_s$.
        """,
    ),
    code(
        "resultado-cost-push",
        "Sustituir escenarios cost-push y mostrar figura Plotly",
        r'''
        por_id = escenarios_economia.set_index("id_escenario")
        e5 = por_id.loc["E5_original"]
        e10 = por_id.loc["E10_misma_metodologia"]
        e10_lhv = por_id.loc["E10_penalizacion_lhv"]

        diferencia_precio = (
            e10["precio_mezcla_q_por_litro"] - e5["precio_mezcla_q_por_litro"]
        ) / (e10["mezcla_etanol_fraccion"] - e5["mezcla_etanol_fraccion"])
        precio_gasolina = e5["precio_mezcla_q_por_litro"] - (
            e5["mezcla_etanol_fraccion"] * diferencia_precio
        )

        display(
            Markdown(
                rf"""
                **Sustituciones del choque $r_s$**

                \[
                \begin{{aligned}}
                r_{{E5}}&=\frac{{{e5['precio_mezcla_q_por_litro']:.2f}
                ({e5['factor_energetico_aplicado']:.8f})}}{{{precio_gasolina:.2f}}}-1
                ={e5['r_fraccion']:.9f}={e5['r_porcentaje']:.6f}\%,\\
                r_{{E10}}&=\frac{{{e10['precio_mezcla_q_por_litro']:.2f}
                ({e10['factor_energetico_aplicado']:.8f})}}{{{precio_gasolina:.2f}}}-1
                ={e10['r_fraccion']:.9f}={e10['r_porcentaje']:.6f}\%,\\
                r_{{E10,LHV}}&=\frac{{{e10_lhv['precio_mezcla_q_por_litro']:.2f}
                ({e10_lhv['factor_energetico_aplicado']:.9f})}}{{{precio_gasolina:.2f}}}-1
                ={e10_lhv['r_fraccion']:.9f}={e10_lhv['r_porcentaje']:.6f}\%.
                \end{{aligned}}
                \]
                """
            )
        )
        columnas_cost_push = [
            "etiqueta",
            "r_porcentaje",
            "delta_precio_total_promedio_fraccion",
            "delta_precio_transporte_p104_p105_promedio_fraccion",
        ]
        display(escenarios_economia.set_index("id_escenario")[columnas_cost_push])
        display(crear_figura_cost_push(categorias_precios))
        ''',
    ),
    markdown(
        "mat-demand-pull",
        r"""
        ## 5. Canal *demand-pull*: ecuación antes de la figura

        El uso de P068, el gasto base de gasolina y la demanda final doméstica de
        etanol se construyen en ese orden:

        \[
        u_{068}=\sum_j Z_{P068,j},\quad
        G_g=\alpha u_{068},\quad
        V_e=sG_g,\quad
        V_e^{dom}=\delta V_e,\quad
        \Delta y=V_e^{dom}e_{P010},\quad
        \Delta x=L\Delta y.
        \]

        El multiplicador reportado por este ejercicio es
        $m=\sum_j\Delta x_j/\sum_j\Delta y_j$. La respuesta del residual se
        calcula como
        $\Delta v^{res}=\operatorname{diag}(v^{res}/x)\Delta x$, sin
        reinterpretarla como VAB.
        """,
    ),
    code(
        "resultado-demand-pull",
        "Sustituir escenarios demand-pull y mostrar figura Plotly",
        r'''
        alfa = e5["gasto_gasolina_base_millones_q_2013"] / e5[
            "uso_total_p068_millones_q_2013"
        ]
        participacion_domestica = e5[
            "valor_etanol_domestico_millones_q_2013"
        ] / e5["valor_etanol_total_millones_q_2013"]

        display(
            Markdown(
                rf"""
                **Sustitución de demanda final y producción (millones de Q de 2013)**

                \[
                \begin{{aligned}}
                G_g&={alfa:.2f}({e5['uso_total_p068_millones_q_2013']:.9f})
                ={e5['gasto_gasolina_base_millones_q_2013']:.9f},\\
                \Delta y_{{E5}}&=0.05({e5['gasto_gasolina_base_millones_q_2013']:.9f})
                ({participacion_domestica:.2f})={e5['delta_y_total_millones_q_2013']:.9f},\\
                \sum\Delta x_{{E5}}&={e5['delta_x_total_millones_q_2013']:.9f},\qquad
                m_{{E5}}={e5['multiplicador_produccion']:.9f},\\
                \Delta y_{{E10}}&=0.10({e10['gasto_gasolina_base_millones_q_2013']:.9f})
                ({participacion_domestica:.2f})={e10['delta_y_total_millones_q_2013']:.9f},\\
                \sum\Delta x_{{E10}}&={e10['delta_x_total_millones_q_2013']:.9f},\qquad
                m_{{E10}}={e10['multiplicador_produccion']:.9f}.
                \end{{aligned}}
                \]
                """
            )
        )
        columnas_demanda = [
            "etiqueta",
            "delta_y_total_millones_q_2013",
            "delta_x_total_millones_q_2013",
            "delta_x_p010_millones_q_2013",
            "multiplicador_produccion",
        ]
        display(
            escenarios_economia.query(
                "id_escenario in ['E5_original', 'E10_misma_metodologia']"
            ).set_index("id_escenario")[columnas_demanda]
        )
        display(crear_figura_demand_pull(categorias_demanda))
        ''',
    ),
    markdown(
        "reconciliacion-explicacion",
        """
        ## 6. Reconciliación con el manuscrito

        La tabla siguiente no fuerza coincidencias. Distingue la métrica publicada,
        la métrica verdaderamente calculada y el resultado E10 comparable. En
        particular, 1.53 % coincide con el choque inicial E5, no con transporte
        propagado; 3.17 millones coincide con la producción total E5, no con P010.
        Las demás afirmaciones no se etiquetan como reproducidas cuando los
        controles no encuentran una correspondencia matemática.
        """,
    ),
    code(
        "mostrar-reconciliacion",
        "Mostrar reconciliación sin forzar coincidencias",
        r"""
        columnas_reconciliacion = [
            "bloque",
            "etiqueta_manuscrito",
            "valor_reportado_manuscrito",
            "unidad",
            "valor_e5_recalculado",
            "valor_e10_misma_metodologia",
            "metrica_alternativa",
            "diagnostico",
        ]
        display(reconciliacion[columnas_reconciliacion])
        """,
    ),
    markdown(
        "alcance-contrafactual-recuperado",
        """
        ## 7. Contrafactual anual recuperado del artículo

        Las 38 observaciones 1986–2023 se recuperaron de las salidas Plotly
        incrustadas en un cuaderno fuente privado y se corroboraron con una copia
        independiente. No se digitalizaron píxeles. A partir de ellas se reconstruye
        la serie base, se vuelve a estimar la proyección 2024–2030 y se recrean
        dinámicamente las cuatro figuras ambientales del artículo.

        Alcance preciso: la serie pública sigue siendo una reconstrucción anual
        desde la salida ejecutada del cuaderno original, pero ya fue contrastada
        contra una copia recuperada del libro primario externo, hoja
        `1.CONSUMO FINAL`. Coinciden 38/38 observaciones a 15 cifras
        significativas. El archivo Excel no se publica porque su procedencia
        estadística y licencia permanecen pendientes de documentación.
        """,
    ),
    markdown(
        "mat-emisiones-historicas",
        r"""
        ### Figura 1 · Contrafactual histórico: matemática antes del resultado

        Los parámetros son los escritos en el cuaderno recuperado, no valores
        calibrados contra el total publicado:

        \[
        q=\frac{21.1}{32}=0.659375,\qquad s=0.10,\qquad
        f_e=1-\frac{1-s}{(1-s)+sq}=0.0682626981559366.
        \]

        \[
        E_t[\mathrm{TJ}]=\frac{BTU_t(0.001055056)}{10^6},\qquad
        C_{E0,t}=69.3E_t.
        \]

        \[
        C_{E10,t}=C_{E0,t}(1-f_e),\qquad
        C_{evitado,t}=C_{E0,t}-C_{E10,t}.
        \]
        """,
    ),
    code(
        "resultado-emisiones-historicas",
        "Sustituir contrafactual histórico y mostrar figura Plotly",
        r'''
        historico = contrafactual_articulo.query(
            "scenario_context == 'historical_counterfactual_1986_2023'"
        ).copy()
        ejemplo_historico = historico.loc[historico["year"] == 1986].iloc[0]
        fe_articulo = 1.0 - (
            float(ejemplo_historico["scenario_co2_tonnes"])
            / float(ejemplo_historico["reference_co2_tonnes"])
        )
        display(
            Markdown(
                rf"""
                **Sustitución para 1986**

                \[
                E_{{1986}}=\frac{{{ejemplo_historico['btu']:,.2f}
                (0.001055056)}}{{10^6}}
                ={ejemplo_historico['energy_tj']:,.9f}\ \mathrm{{TJ}},
                \]
                \[
                C_{{E0,1986}}={ejemplo_historico['energy_tj']:,.9f}(69.3)
                ={ejemplo_historico['reference_co2_tonnes']:,.6f},
                \]
                \[
                C_{{E10,1986}}={ejemplo_historico['reference_co2_tonnes']:,.6f}
                (1-{fe_articulo:.16f})
                ={ejemplo_historico['scenario_co2_tonnes']:,.6f}\ \mathrm{{tCO_2}},
                \quad C_{{evitado}}={ejemplo_historico['avoided_co2_tonnes']:,.6f}.
                \]
                """
            )
        )
        display(
            resumen_contrafactual.query("period_id == 'historical_1986_2023'")
        )
        display(crear_figura_emisiones_articulo_historica(contrafactual_articulo))
        ''',
    ),
    markdown(
        "mat-consumo-articulo",
        r"""
        ### Figura 2 · Consumo final: matemática antes del resultado

        La curva de consumo usa la misma energía reconstruida. Con PCI de gasolina
        de 32 MJ/L y \(0.2641720524\) galones EE. UU. por litro:

        \[
        Litros_t=\frac{E_t\,10^6}{32},\qquad
        G_t[\mathrm{millones\ de\ gal}]
        =\frac{E_t}{32}(0.2641720524).
        \]

        Esta conversión se controla año por año contra la serie incrustada en el
        cuaderno recuperado.
        """,
    ),
    code(
        "resultado-consumo-articulo",
        "Sustituir consumo final y mostrar figura Plotly",
        r'''
        ejemplo_consumo = serie_articulo.loc[serie_articulo["year"] == 1986].iloc[0]
        display(
            Markdown(
                rf"""
                **Sustitución para 1986**

                \[
                G_{{1986}}=\frac{{{ejemplo_consumo['energy_tj']:,.9f}}}{{32}}
                (0.2641720524)
                ={ejemplo_consumo['million_us_gallons']:,.9f}
                \ \mathrm{{millones\ de\ galones}}.
                \]
                """
            )
        )
        display(
            serie_articulo[
                [
                    "year",
                    "data_status",
                    "million_us_gallons",
                    "source_lineage",
                    "value_status",
                ]
            ]
        )
        display(crear_figura_consumo_articulo(serie_articulo))
        ''',
    ),
    markdown(
        "mat-proyeccion-articulo",
        r"""
        ### Figura 3 · Prospectivo: matemática antes del resultado

        El código original ajusta **litros** contra el año en la ventana
        **2014–2023**, no 2015–2024:

        \[
        \ln(Litros_t)=\beta_0+\beta_1t+\varepsilon_t,\qquad
        \widehat{Litros}_t=\exp(\beta_0+\beta_1t).
        \]

        El flujo reproducible expresa el mismo ajuste con energía y año centrado:

        \[
        \ln(E_t)=a+b(t-2014)+\varepsilon_t,\qquad
        \widehat E_t=\exp[a+b(t-2014)],\qquad
        b=\beta_1,\qquad g=\exp(b)-1.
        \]

        Es algebraicamente equivalente porque
        \(Litros_t=E_t10^6/32\): la escala constante cambia solo el intercepto.

        En el contexto prospectivo la política es por tramos:

        \[
        s_t=
        \begin{cases}
        0,&t\in\{2024,2025\},\\
        0.10,&2026\le t\le2030,
        \end{cases}
        \qquad
        C_{s,t}=
        \begin{cases}
        C_{E0,t},&s_t=0,\\
        C_{E0,t}(1-f_e),&s_t=0.10.
        \end{cases}
        \]
        """,
    ),
    code(
        "resultado-proyeccion-articulo",
        "Sustituir proyección original y mostrar figura Plotly",
        r'''
        ajuste_articulo = diagnostico_eia["article_recovered"]["fit"]
        beta_0_litros = (
            ajuste_articulo["intercept_at_center"]
            - ajuste_articulo["slope_per_year"] * ajuste_articulo["center_year"]
            + math.log(1e6 / 32.0)
        )
        prospectivo = contrafactual_articulo.query(
            "scenario_context == 'prospective_policy_2024_2030'"
        ).copy()
        fila_2024 = prospectivo.loc[prospectivo["year"] == 2024].iloc[0]
        fila_2026 = prospectivo.loc[prospectivo["year"] == 2026].iloc[0]
        display(
            Markdown(
                rf"""
                **Sustitución del ajuste original y su forma equivalente**

                \[
                \ln(Litros_t)={beta_0_litros:.12f}
                +{ajuste_articulo['slope_per_year']:.12f}t.
                \]
                \[
                \ln(E_t)={ajuste_articulo['intercept_at_center']:.12f}
                +{ajuste_articulo['slope_per_year']:.12f}(t-2014),
                \qquad g={ajuste_articulo['annual_growth_rate']:.9%}.
                \]
                \[
                \widehat E_{{2024}}=
                \exp[{ajuste_articulo['intercept_at_center']:.12f}
                +{ajuste_articulo['slope_per_year']:.12f}(2024-2014)]
                ={fila_2024['energy_tj']:,.9f}\ \mathrm{{TJ}}.
                \]
                \[
                C_{{s,2024}}=C_{{E0,2024}}=
                {fila_2024['scenario_co2_tonnes']:,.6f},\qquad
                C_{{s,2026}}={fila_2026['reference_co2_tonnes']:,.6f}
                (1-{fe_articulo:.16f})
                ={fila_2026['scenario_co2_tonnes']:,.6f}.
                \]

                Diagnósticos:
                \(R^2_{{\ln E}}={ajuste_articulo['r_squared_log_scale']:.9f}\),
                \(RMSE_{{\ln E}}={ajuste_articulo['rmse_log_scale']:.9f}\),
                \(n={ajuste_articulo['n_observations']}\).
                """
            )
        )
        display(
            resumen_contrafactual.query("period_id == 'prospective_2026_2030'")
        )
        display(crear_figura_emisiones_articulo_prospectiva(contrafactual_articulo))
        ''',
    ),
    markdown(
        "mat-integracion-articulo",
        r"""
        ### Figura 4 · Integrada: matemática y diferencia de contexto

        La figura integrada del cuaderno aplica E10 a **todos** los años 1986–2030:

        \[
        s_t^{integrada}=0.10\quad\forall t\in[1986,2030],\qquad
        C_{s,t}^{integrada}=C_{E0,t}(1-f_e).
        \]

        Por tanto, en 2024–2025 la figura integrada evita emisiones, mientras que
        la figura prospectiva conserva E0. Esta diferencia se reproduce de forma
        explícita; no se fuerza una sola regla sobre dos figuras que usaron
        contextos distintos.
        """,
    ),
    code(
        "resultado-integracion-articulo",
        "Comprobar 2024–2025 y mostrar figura integrada Plotly",
        r'''
        comparacion_contextos = (
            contrafactual_articulo.loc[
                contrafactual_articulo["year"].isin([2024, 2025])
                & contrafactual_articulo["scenario_context"].isin(
                    [
                        "prospective_policy_2024_2030",
                        "integrated_figure_1986_2030",
                    ]
                ),
                [
                    "year",
                    "scenario_context",
                    "scenario_id",
                    "blend_share_applied",
                    "reference_co2_tonnes",
                    "scenario_co2_tonnes",
                    "avoided_co2_tonnes",
                ],
            ]
            .sort_values(["year", "scenario_context"])
            .reset_index(drop=True)
        )
        ejemplo_integrado = comparacion_contextos.query(
            "year == 2024 and scenario_context == 'integrated_figure_1986_2030'"
        ).iloc[0]
        integrado = contrafactual_articulo.query(
            "scenario_context == 'integrated_figure_1986_2030'"
        )
        union_publicada = resumen_contrafactual.query(
            "period_id == 'reported_periods_combined_excluding_2024_2025'"
        ).iloc[0]
        total_evitado_integrado = float(integrado["avoided_co2_tonnes"].sum())
        total_evitado_union = float(union_publicada["avoided_co2_tonnes"])
        diferencia_2024_2025 = total_evitado_integrado - total_evitado_union
        evitado_2024_2025 = float(
            integrado.loc[
                integrado["year"].isin([2024, 2025]), "avoided_co2_tonnes"
            ].sum()
        )
        assert abs(diferencia_2024_2025 - evitado_2024_2025) < 1e-6
        display(
            Markdown(
                rf"""
                **Sustitución integrada para 2024**

                \[
                C_{{s,2024}}^{{integrada}}=
                {ejemplo_integrado['reference_co2_tonnes']:,.6f}
                (1-{fe_articulo:.16f})
                ={ejemplo_integrado['scenario_co2_tonnes']:,.6f},
                \quad
                C_{{evitado,2024}}^{{integrada}}=
                {ejemplo_integrado['avoided_co2_tonnes']:,.6f}.
                \]

                **Sustitución de los totales**

                \[
                C_{{evitado}}^{{integrada,\ 45\ años}}
                ={total_evitado_integrado:,.6f}\ \mathrm{{tCO_2}},
                \]
                \[
                C_{{evitado}}^{{unión\ publicada,\ 43\ años}}
                ={total_evitado_union:,.6f}\ \mathrm{{tCO_2}},
                \]
                \[
                {total_evitado_integrado:,.6f}
                -{total_evitado_union:,.6f}
                ={diferencia_2024_2025:,.6f}\ \mathrm{{tCO_2}}
                =C_{{evitado,2024}}+C_{{evitado,2025}}.
                \]
                """
            )
        )
        display(comparacion_contextos)
        display(crear_figura_emisiones_articulo_integrada(contrafactual_articulo))
        ''',
    ),
    markdown(
        "conciliacion-agregada-explicacion",
        r"""
        ### Conciliación de los totales reportados

        La tabla publicada que se rotuló como total 1986–2030 no suma un intervalo
        continuo. Su operación real es:

        \[
        T_{reportado}=
        \sum_{t=1986}^{2023}C_t+\sum_{t=2026}^{2030}C_t,
        \qquad \{2024,2025\}\ \mathrm{excluidos}.
        \]

        Esto es distinto de la figura integrada, que sí contiene los 45 años y
        aplica E10 también en 2024–2025.
        """,
    ),
    code(
        "resultado-conciliacion-agregada",
        "Mostrar sumas anuales y controles agregados publicados",
        r"""
        display(resumen_contrafactual)
        display(
            publicada_agregada[
                [
                    "period_id",
                    "reference_co2_tonnes",
                    "scenario_co2_tonnes",
                    "avoided_co2_tonnes",
                    "calculation_scope",
                    "source_lineage",
                ]
            ]
        )
        """,
    ),
    markdown(
        "separacion-eia",
        """
        ## 8. Actualización anual EIA: linaje separado

        Este apéndice es **opcional y está desactivado por defecto**. La serie EIA
        observada (1986–2024) y su proyección (2025–2030) constituyen una
        actualización abierta, no la fuente del artículo. Sus agregados difieren
        porque cambian la fuente y la ventana de ajuste. Nunca se usan para rellenar
        ni recalibrar el contrafactual del cuaderno recuperado.
        """,
    ),
    markdown(
        "mat-proyeccion-eia",
        r"""
        ### Proyección EIA opcional: matemática antes de la figura

        Sobre la ventana 2015–2024 se ajusta por mínimos cuadrados ordinarios:

        \[
        \ln(E_t)=a+b(t-t_0)+\varepsilon_t,\qquad
        \widehat E_t=\exp[a+b(t-t_0)],\qquad
        g=\exp(b)-1.
        \]

        La retransmisión usa la exponencial directa, sin corrección de *smearing*.
        Si se activa, la figura interactiva distingue observaciones y proyecciones
        y muestra exclusivamente E10.
        """,
    ),
    code(
        "resultado-proyeccion-eia-opcional",
        "Activar actualización EIA y su figura Plotly",
        r'''
        MOSTRAR_ACTUALIZACION_EIA = False #@param {type:"boolean"}
        ajuste = diagnostico_eia["fit"]
        energia_2025 = float(eia_anual.loc[eia_anual["year"] == 2025, "energy_tj"].iloc[0])
        if MOSTRAR_ACTUALIZACION_EIA:
            display(
                Markdown(
                    rf"""
                    **Sustitución del ajuste EIA**

                    \[
                    \ln(E_t)={ajuste['intercept_at_center']:.12f}
                    +{ajuste['slope_per_year']:.12f}(t-{ajuste['center_year']}),
                    \qquad g={ajuste['annual_growth_rate']:.9%}.
                    \]

                    \[
                    \widehat E_{{2025}}=\exp[{ajuste['intercept_at_center']:.12f}
                    +{ajuste['slope_per_year']:.12f}(2025-{ajuste['center_year']})]
                    ={energia_2025:,.6f}\ \mathrm{{TJ}}.
                    \]

                    Diagnósticos: \(R^2_{{\ln E}}={ajuste['r_squared_log_scale']:.9f}\),
                    \(RMSE_{{\ln E}}={ajuste['rmse_log_scale']:.9f}\),
                    \(n={ajuste['n_observations']}\).
                    """
                )
            )
            display(crear_figura_emisiones_eia(eia_anual, escenario="E10"))
        else:
            display(Markdown("_Actualización EIA desactivada; el cuerpo principal usa el cuaderno recuperado._"))
        ''',
    ),
    markdown(
        "mat-emisiones-eia",
        r"""
        ### Conversión TTW EIA opcional antes de la figura

        Para cada año del linaje EIA, con factor de gasolina
        $EF_g=69.3\ \mathrm{tCO_2/TJ}$, se aplica el mismo factor fósil E10:

        \[
        C_{E0,t}=E_t EF_g,\qquad
        C_{E10,t}=C_{E0,t}f_{10},\qquad
        C_{evitado,t}=C_{E0,t}-C_{E10,t},
        \]

        \[
        C_{evitado,\le t}=\sum_{\tau\le t}C_{evitado,\tau}.
        \]

        Si se activa el apéndice, la segunda figura separa el valor anual del
        acumulado. Estos resultados no se mezclan con los del artículo.
        """,
    ),
    code(
        "resultado-emisiones-eia-opcional",
        "Mostrar emisiones evitadas EIA si se activó el apéndice",
        r'''
        ejemplo = eia_anual.loc[eia_anual["year"] == 2024].iloc[0]
        if MOSTRAR_ACTUALIZACION_EIA:
            display(
                Markdown(
                    rf"""
                    **Sustitución EIA para 2024**

                    \[
                    C_{{E0,2024}}={ejemplo['energy_tj']:,.6f}
                    ({ejemplo['co2_factor_tonnes_per_tj']:.1f})
                    ={ejemplo['reference_co2_tonnes']:,.6f}\ \mathrm{{tCO_2}},
                    \]
                    \[
                    C_{{E10,2024}}={ejemplo['reference_co2_tonnes']:,.6f}
                    ({ejemplo['fossil_emissions_factor']:.12f})
                    ={ejemplo['scenario_co2_tonnes']:,.6f}\ \mathrm{{tCO_2}},
                    \qquad
                    C_{{evitado,2024}}={ejemplo['avoided_co2_tonnes']:,.6f}\ \mathrm{{tCO_2}}.
                    \]
                    """
                )
            )
            display(eia_resumen)
            display(crear_figura_emisiones_evitadas(eia_anual, escenario="E10"))
        ''',
    ),
    markdown(
        "controles-explicacion",
        """
        ## 9. Controles y cierre reproducible

        La ejecución se acepta solamente si todos los controles económicos y
        ambientales tienen estado positivo. El manifiesto permite verificar las
        huellas de los artefactos consumidos por este cuaderno. Una prueba fallida
        detiene la ejecución; no se ocultan discrepancias con redondeos gráficos.
        """,
    ),
    code(
        "mostrar-controles",
        "Mostrar controles, huellas y estado final",
        r"""
        economia_ok = controles_economia["cumple"].astype(str).str.lower().eq("true")
        emisiones_ok = controles_emisiones["status"].eq("PASS")
        resumen_controles = pd.DataFrame(
            [
                {
                    "bloque": "Economía E5/E10",
                    "superados": int(economia_ok.sum()),
                    "total": int(len(economia_ok)),
                    "estado": "PASS" if economia_ok.all() else "FAIL",
                },
                {
                    "bloque": "Emisiones TTW",
                    "superados": int(emisiones_ok.sum()),
                    "total": int(len(emisiones_ok)),
                    "estado": "PASS" if emisiones_ok.all() else "FAIL",
                },
            ]
        )
        display(resumen_controles)
        display(Markdown("### Controles económicos"))
        display(controles_economia)
        display(Markdown("### Controles ambientales"))
        display(controles_emisiones)

        rutas_usadas = set(SALIDAS.values())
        huellas_usadas = manifiesto.loc[manifiesto["ruta"].isin(rutas_usadas)]
        display(Markdown("### Huellas de salidas consumidas"))
        display(huellas_usadas)

        assert economia_ok.all(), "Falló al menos un control económico."
        assert emisiones_ok.all(), "Falló al menos un control ambiental."
        display(
            Markdown(
                "**Resultado de auditoría:** controles superados. La corrección "
                "económica E10 es reproducible y las cuatro series ambientales "
                "del cuaderno son reconstruibles dentro de su linaje. La copia "
                "del workbook primario fue verificada sin redistribuirla y la "
                "actualización EIA permanece separada."
            )
        )
        """,
    ),
]


NOTEBOOK = {
    "cells": CELLS,
    "metadata": {
        "colab": {
            "name": "reproducir_resultados_e10.ipynb",
            "provenance": [],
        },
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
