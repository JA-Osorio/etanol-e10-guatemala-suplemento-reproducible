# Material suplementario reproducible: etanol en Guatemala

[![Abrir en Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible/blob/revision-e5-e10-trazabilidad/05_cuaderno_colab/reproducir_resultados_e10.ipynb)
[![MIP Guatemala 2013](https://img.shields.io/badge/MIP_Guatemala_2013-v1.0.0-2f6f4e)](https://doi.org/10.5281/zenodo.22086008)

Este repositorio acompaña el artículo *Implementación tardía de la Ley del
Alcohol Carburante: efectos económico-ambientales en Guatemala (1986–2030)*.
Permite reconstruir el contrafactual de emisiones, la proyección 2024–2030 y el
ejercicio económico insumo-producto con datos, parámetros y código versionados.

El [cuaderno en Colab](https://colab.research.google.com/github/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible/blob/revision-e5-e10-trazabilidad/05_cuaderno_colab/reproducir_resultados_e10.ipynb)
es la entrada recomendada. Sigue el orden del artículo, mantiene el código
plegado, expone las ecuaciones antes de cada resultado y presenta seis gráficas
Plotly interactivas.

Autores: Juan Alejandro Osorio, Silvia Patricia Villatoro y Noé Salguero.

## Resultados ambientales reproducidos

El cálculo usa una mezcla E10, un poder calorífico de 32.0 MJ/L para gasolina,
21.1 MJ/L para etanol y un factor de emisión de 69.3 tCO₂/TJ. Bajo servicio
energético constante, la reducción TTW anual es 6.82627 %.

| Periodo | E0 (tCO₂) | E10 (tCO₂) | Evitadas (tCO₂) |
|---|---:|---:|---:|
| Histórico observado, 1986–2023 | 104,318,087 | 97,197,053 | 7,121,034 |
| Costo de inacción hasta 2025 | 117,939,360 | 109,888,501 | 8,050,859 |
| Beneficio prospectivo, 2026–2030 | 41,728,481 | 38,879,982 | 2,848,499 |
| Trayectoria continua, 1986–2030 | 159,667,841 | 148,768,483 | 10,899,358 |

El total de 9,969,533 tCO₂ rotulado en el artículo como “1986–2030” suma dos
ventanas —1986–2023 y 2026–2030— y no incluye 2024–2025. El cuaderno conserva
esa suma para explicar su procedencia, pero la distingue de la trayectoria
continua y del horizonte de inacción 1986–2025.

## Corrección del bloque económico

El archivo de cálculo que alimentó el bloque económico del artículo utiliza
E5, aunque esos resultados quedaron integrados en el texto dentro del escenario
E10. La reproducción separa dos objetos:

- **E5 del cálculo original:** conserva la mezcla de 5 % y los demás supuestos.
- **E10 comparable:** cambia únicamente la mezcla de 5 % a 10 %; ambos se
  comparan con E0.

| Magnitud | E5 del cálculo original | E10 comparable |
|---|---:|---:|
| Choque inicial de costo | 1.528571 % | 0.057143 % |
| Precio propagado en P104–P105 | 0.001974 % | 0.0000738 % |
| Demanda final adicional | Q1.877204 millones | Q3.754407 millones |
| Producción inducida total | Q3.166772 millones | Q6.333543 millones |
| Producción inducida en P010 | Q1.879071 millones | Q3.758143 millones |
| Multiplicador de producción | 1.686962 | 1.686962 |

El 1.53 % corresponde al choque inicial E5, no al precio propagado del
transporte. Q3.17 millones corresponde a la producción inducida total en E5,
no únicamente a caña. Las cifras Q4.77 millones y 1.13 impresas en el artículo
no son producidas por esta especificación y no se usan para calibrar el modelo.

El E10 comparable documenta qué ocurre al cambiar solo la fracción de mezcla;
no constituye una estimación integral del efecto nacional del mandato. Los
precios, la participación de gasolina dentro de P068, la participación doméstica
y la penalización energética fija son supuestos del archivo de cálculo, no
observaciones adicionales de la MIP.

## Reproducir localmente

Requisitos: Python 3.11 o superior.

```bash
python -m pip install -e '.[test]'
python 04_reproduccion_python/reproducir_todo.py
```

Para utilizar una copia local de la MIP fijada:

```bash
python 04_reproduccion_python/reproducir_todo.py \
  --mip-dir ../mip-guatemala-2013-reproducible
```

Las tablas se escriben en `06_resultados/`. La validación automatizada puede
ejecutarse de forma independiente:

```bash
pytest -q
```

## Cadena reproducible

| Etapa | Ubicación |
|---|---|
| Fuentes, alcance y decisiones metodológicas | [`00_fuentes_y_trazabilidad/`](00_fuentes_y_trazabilidad/) |
| Insumos versionados | [`01_datos/insumos_publicables/`](01_datos/insumos_publicables/) |
| Concordancias económicas | [`02_concordancias/`](02_concordancias/) |
| Parámetros y escenarios | [`03_configuracion/`](03_configuracion/) |
| Implementación en Python | [`04_reproduccion_python/`](04_reproduccion_python/) |
| Cuaderno Colab | [`05_cuaderno_colab/reproducir_resultados_e10.ipynb`](05_cuaderno_colab/reproducir_resultados_e10.ipynb) |
| Tablas reproducidas | [`06_resultados/`](06_resultados/) |
| Pruebas automatizadas | [`07_verificacion/tests/`](07_verificacion/tests/) |

La dependencia MIP Guatemala 2013 está fijada en la versión 1.0.0. La serie de
consumo contiene 38 observaciones anuales, de 1986 a 2023; la proyección
log-lineal se estima sobre 2014–2023 y se retransmite directamente a 2024–2030.

## Alcance

- Las emisiones son de escape (TTW), no de ciclo de vida.
- Las predicciones 2024–2030 extrapolan una tendencia log-lineal y no incorporan
  intervalos de incertidumbre estructural.
- La economía se representa con una MIP estática de 2013 y valores monetarios a
  precios de ese año.
- P068 agrupa combustibles; la base económica empleada es su utilización
  intermedia doméstica. P010 se utiliza como aproximación de la demanda de caña.
- La ecuación de demanda aplica una participación volumétrica a un agregado
  monetario y no incorpora la penalización energética. El cuaderno conserva esa
  especificación para comparar E5 y E10 sin modificar varios supuestos a la vez.
- No se estiman impactos de ciclo de vida, uso de suelo, seguridad alimentaria o
  equilibrio general.

La documentación detallada de fuentes y limitaciones está en
[`00_fuentes_y_trazabilidad/estado_reproducibilidad.md`](00_fuentes_y_trazabilidad/estado_reproducibilidad.md).
