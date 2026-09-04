# Estado de reproducibilidad

Fecha de corte: 2026-09-04.

Este documento separa tres afirmaciones que no son equivalentes:

- **Reproducir**: regenerar un resultado desde los mismos insumos y la misma
  lógica, con controles numéricos.
- **Recalcular**: aplicar de forma transparente una lógica recuperada a otro
  escenario.
- **Conciliar**: comprobar una identidad usando como insumo un total ya
  publicado; esto no reconstruye la serie que originó ese total.
- **Reconstruir desde una salida**: recuperar una serie desde los valores
  embebidos en un artefacto ejecutado. Permite verificar el resultado numérico.
  En este caso, además, la reconstrucción fue contrastada posteriormente contra
  una copia recuperada del insumo primario.

La cadena completa resultado → insumos → parámetros → ecuaciones → funciones →
salidas → controles está en
[`cadena_calculos.csv`](cadena_calculos.csv).

## Estado por bloque

| Bloque | Estado verificable | Qué permiten afirmar los controles | Qué no permiten afirmar |
|---|---|---|---|
| Economía `E5_original` | Reproducción forense exacta | La MIP fijada, el ajuste P105 y la lógica recuperada regeneran los valores dorados E5; 37/37 controles del bloque económico del artículo pasan. | Que los precios, `α=0.45`, el contenido doméstico `s=0.70` o la asignación completa a P010 tengan validez empírica independiente. |
| Economía `E10_misma_metodologia` | Recálculo comparable corregido | Cambiar solo la mezcla de 5% a 10% regenera el resultado E10 documentado contra E0. | Que exista una corrida E10 histórica detrás de las cifras económicas del manuscrito. |
| Economía `E10_penalizacion_lhv` | Sensibilidad separada | El canal *cost-push* se recalcula con `32/((1-m)·32+m·21.2)`; el *demand-pull* permanece igual al E10 comparable. | Que sea la metodología original o una corrección física integral. |
| Economía E10/E15/E20 actual | Reconstrucción contemporánea | 28/28 controles verifican huellas, identidades, cobertura y rotulado de la malla. | Que estas cifras reproduzcan el artículo; son un linaje distinto. |
| Emisiones del artículo E10 | Reproducción computacional verificada contra una copia del insumo primario | El cuaderno original conserva la serie 1986–2023, los parámetros y las salidas Plotly. La copia recuperada del libro primario reproduce 38/38 observaciones y todos los agregados publicados al redondear. | Que el Excel tenga procedencia estadística y licencia verificadas: no contiene URL, nota metodológica ni licencia, y por ello no se redistribuye. |
| Emisiones EIA | Reconstrucción anual abierta distinta | La serie EIA 1986–2024, la proyección log-lineal 2025–2030 y las identidades TTW generan tablas anuales auditables. | Que la actualización EIA sea el linaje OLADE/sieLAC usado por el artículo o que deba coincidir con sus agregados. |

El total ambiental presentado como “1986–2030” no es una serie continua en la
evidencia publicada: suma dos intervalos disjuntos, 1986–2023 y 2026–2030. Los
años 2024 y 2025 no están incluidos en ese total.

## Evidencia ambiental recuperada

El artefacto principal es un cuaderno limpio recuperado de Drive; una segunda
copia corrobora sus primeras celdas relevantes. Sus nombres, IDs de Drive,
huellas y otros identificadores se omiten en esta rama pública sanitizada. Los
identificadores completos permanecen únicamente en el registro local de
auditoría no publicable. El cuaderno principal conserva las celdas 0–15 con el
cálculo original.

En la copia, la celda 0 y las celdas 3–17 contienen la carga de la serie, los
parámetros y las salidas útiles. La celda 1 intenta mostrar un objeto todavía no
definido y la celda 2 es texto; las celdas posteriores incluyen un refactor con
datos ficticios que falló. Ninguno de esos segmentos se usa como evidencia. El
cuaderno limpio es la fuente principal; la copia solo es corroborante.

El bloque recuperado documenta:

- la conversión `BTU × 0.001055056 = MJ`;
- `PCI_gasolina=32.0 MJ/L`, `PCI_etanol=21.1 MJ/L`, mezcla `m=0.10` y
  `FE=69.3 tCO2/TJ`;
- la fracción energética del etanol
  `f_e=m·PCI_etanol/((1-m)·PCI_gasolina+m·PCI_etanol)`;
- el contrafactual TTW anual de 1986–2023; y
- una regresión `ln(litros)=b0+b1·año` ajustada con los diez años 2014–2023,
  proyectada para 2024–2030.

Los arreglos numéricos embebidos en las salidas Plotly permiten recuperar la
serie anual sin digitalizar píxeles. El CSV versionado que conserva esa
extracción es
`01_datos/insumos_publicables/contrafactual_articulo_recuperado_1986_2023.csv`.
Se mantiene rotulado como `recovered_output` porque el CSV se extrajo de las
salidas embebidas; su equivalencia con el Excel se documenta por separado y no
convierte el derivado en el archivo original.

La utilidad
`e10_gt.recuperacion_cuaderno.recover_counterfactual_from_notebook` regenera la
extracción desde una copia local autorizada y verifica las cuatro huellas
semánticas Plotly. El pipeline público la carga con
`e10_gt.emisiones_ttw.load_recovered_article_history`, reconstruye el escenario
con `e10_gt.emisiones_ttw.build_recovered_article_counterfactual` y escribe:

- `06_resultados/emisiones/serie_articulo_anual.csv`;
- `06_resultados/emisiones/contrafactual_articulo_anual.csv`; y
- `06_resultados/emisiones/contrafactual_articulo_resumen.csv`.

Los agregados publicados se conservan como controles dorados, no como fuente
de cálculo de la trayectoria anual.

## Verificación contra el libro primario y brecha documental

Se recuperó una copia del libro primario, hoja `1.CONSUMO FINAL`. Su nombre y
huella se omiten en esta rama pública. Contiene 38 filas continuas, 1986–2023,
con columnas `No`, `año` y `BTU`, sin fórmulas, vínculos externos ni vacíos. La
limpieza original no elimina ni reordena ninguna observación.

A 15 cifras significativas coinciden 38/38 BTU, 38/38 valores de CO2 de
referencia y 38/38 valores de millones de galones. Sin redondear, el residuo
máximo es `0.05078125 BTU` (`3.95e-15` en términos relativos),
`4.66e-9 tCO2` y `5.68e-13` millones de galones. Los agregados históricos y
prospectivos reproducen los valores publicados al redondear a toneladas.

Esto permite afirmar una **reproducción computacional verificada contra una
copia del insumo primario**. No permite afirmar que se haya demostrado la
procedencia estadística del libro ni su licencia. El archivo no incorpora URL,
nota metodológica o licencia. Por ello no se redistribuye ni se atribuye
automáticamente a OLADE/sieLAC; sus metadatos identificables se omiten.

El total publicado como “1986–2030” sigue siendo la suma de 1986–2023 y
2026–2030. Las proyecciones recuperadas incluyen 2024 y 2025, pero el total
reportado no las contabiliza. La actualización EIA se mantiene como una
**reconstrucción anual abierta de distinto linaje** y no se calibra para ocultar
las diferencias.

## Verificación local

Con Python 3.11 o superior:

```bash
python -m pip install -e '.[test]'
python 04_reproduccion_python/reproducir_todo.py \
  --mip-dir ../mip-guatemala-2013-reproducible
pytest -q
```

Si se dispone de la copia autorizada del libro primario, su escalón adicional
se verifica con:

```bash
python 04_reproduccion_python/verificar_series_ccse.py \
  --workbook "/ruta/libro_primario.xlsx"
```

La ejecución debe regenerar las tablas de `06_resultados/`, los controles de
`07_verificacion/controles_*.csv`, el resumen
`06_resultados/resumen_ejecucion.json` y el manifiesto de huellas
`07_verificacion/manifiesto_resultados.csv`. Un `PASS` acredita consistencia
interna y reproducción computacional del alcance declarado; no convierte un
supuesto en una observación ni elimina las limitaciones anteriores.

## Cuadernos: recuperación y ejecución

La versión canónica y revisable del cuaderno se conserva en
`05_cuaderno_colab/reproducir_resultados_e10.ipynb`. Se versiona en Git y puede
abrirse directamente en Google Colab. En esta tarea no se sube una copia nueva
a Drive: las ecuaciones y sustituciones quedan visibles antes de los resultados,
el código de preparación se pliega y las gráficas se presentan de forma
interactiva.

Drive fue únicamente la ubicación donde se localizaron los dos cuadernos
originales descritos arriba; no es el alojamiento del cuaderno nuevo. Esta rama
pública omite sus IDs, huellas y metadatos privados sin alterar los resultados
derivados ni los controles numéricos.
