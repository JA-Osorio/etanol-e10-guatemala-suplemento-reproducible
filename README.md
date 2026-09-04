# Etanol en Guatemala: reproducción E5 y corrección E10

[![Abrir revisión en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible/blob/revision-e5-e10-trazabilidad/05_cuaderno_colab/reproducir_resultados_e10.ipynb)
[![MIP Guatemala 2013](https://img.shields.io/badge/MIP_Guatemala_2013-v1.0.0-2f6f4e)](https://doi.org/10.5281/zenodo.22086008)

Código, datos publicables y controles para auditar y actualizar el análisis de
mezclas de gasolina con alcohol carburante en Guatemala. Este repositorio hace
explícita una corrección importante del manuscrito: **el bloque de emisiones sí
corresponde a E10, pero el cálculo económico que alimentó el texto fue ejecutado
con E5**.

La trazabilidad no se resume en una etiqueta de escenario. Cada resultado se
vincula con sus insumos, parámetros, ecuaciones, funciones, archivos de salida
y controles en
[`00_fuentes_y_trazabilidad/cadena_calculos.csv`](00_fuentes_y_trazabilidad/cadena_calculos.csv).
El alcance probado y las brechas pendientes se explican en
[`00_fuentes_y_trazabilidad/estado_reproducibilidad.md`](00_fuentes_y_trazabilidad/estado_reproducibilidad.md).

La sección metodológica del manuscrito sí llama a E5 el escenario de referencia;
la inconsistencia está en que el resumen, los resultados y las conclusiones
presentan luego esas cifras económicas dentro del encuadre del mandato E10 sin
mostrar una corrida económica E10 ejecutada.

El suplemento conserva la trazabilidad metodológica de la evidencia E5
original, reconstruye su cálculo, identifica qué cifras fueron rotuladas o
interpretadas de forma incorrecta, calcula un E10 comparable con la misma
metodología histórica y mantiene, como objeto separado, una reconstrucción
económica contemporánea para E10, E15 y E20.

Esta rama pública de revisión está sanitizada: los nombres, rutas, IDs de
Drive, huellas y metadatos identificables de los artefactos privados se omiten.
La omisión no cambia datos derivados, ecuaciones, resultados ni controles
numéricos. Los identificadores completos se conservan únicamente en el registro
local de auditoría no publicable.

Este repositorio no contiene el manuscrito ni reconstruye la matriz
insumo-producto. Consume la MIP Guatemala 2013 como dependencia pública fijada
en la versión 1.0.0.

Autores: Juan Alejandro Osorio, Silvia Patricia Villatoro y Noé Salguero.

## Resultado principal de la auditoría

| Magnitud | E5 histórico reproducido | E10 con la misma metodología |
|---|---:|---:|
| Choque inicial de costo, `r` | +1.528571% | +0.057143% |
| `Δp` propagado en transporte P104–P105 | +0.001974% | +0.0000738% |
| Demanda final adicional, `ΣΔy` | Q1.877204 millones | Q3.754407 millones |
| Producción inducida total, `ΣΔx` | Q3.166772 millones | Q6.333543 millones |
| Producción inducida de P010 | Q1.879071 millones | Q3.758143 millones |
| Multiplicador `ΣΔx/ΣΔy` | 1.686962 | 1.686962 |

Los valores monetarios están expresados a precios de 2013. En el manuscrito,
`1.53%` fue presentado como efecto sobre transporte, pero es el choque inicial
`r` del escenario E5. Asimismo, `Q3.17 millones` fue atribuido a caña, aunque es
la producción inducida total de los 152 productos; el resultado de caña y otras
plantas azucareras (P010) es Q1.879071 millones.

Las cifras sectoriales `0.80`, `0.50` y `0.30`, el total `Q4.77 millones` y el
multiplicador `1.13` **no se reproducen** con el cuaderno y los datos históricos
auditados. Se mantienen únicamente como afirmaciones del manuscrito para su
reconciliación; no se usan como objetivos de calibración. El detalle está en
[`00_fuentes_y_trazabilidad/reconciliacion_economia.md`](00_fuentes_y_trazabilidad/reconciliacion_economia.md).
La discusión del manuscrito dice además `Q4.75 millones`, en contradicción con
el abstract, el resumen y la tabla *demand-pull* que dicen `Q4.77 millones`;
ninguna variante se reproduce.

## Qué se reproduce y qué se reconstruye

| Objeto | Escenario | Tratamiento en el repositorio |
|---|---|---|
| Emisiones de escape del manuscrito | E10 | Reconstrucción anual desde las salidas Plotly embebidas y verificación contra una copia recuperada del Excel primario. Coinciden 38/38 observaciones a 15 cifras significativas. El Excel no se redistribuye porque su procedencia estadística y licencia siguen pendientes de documentación. |
| Economía que alimentó el manuscrito | E5 | Reconstrucción forense desde la MIP pública, el *offset* histórico P105 y valores dorados del cuaderno privado. |
| Corrección mínima del error de mezcla | E10 | Recalcula el modelo histórico cambiando únicamente la fracción de etanol de 5% a 10%. |
| Sensibilidad energética | E10 | Sustituye la penalización fija histórica por un ajuste derivado de los poderes caloríficos configurados; modifica solo el canal *cost-push* y deja el *demand-pull* igual al E10 comparable. |
| Comparación económica actualizable | E10, E15 y E20 | Reconstrucción contemporánea de costos, importaciones y efectos insumo-producto; no se presenta como origen de las cifras del manuscrito. |
| Actualización normativa y de emisiones | Marco vigente | Linaje separado de la reproducción de las cifras reportadas, con fuentes y fecha de corte documentadas. |

Los artefactos originales no se redistribuyen porque el paquete contenía una
nota de licencia pendiente. Sus identificadores se omiten en esta rama pública.
En su lugar, el cálculo reconstruye la instantánea desde la MIP pública v1.0.0 y
un *offset* de reconstrucción P105 explícito; la receta está en
[`01_datos/insumos_publicables/economia_articulo_original/`](01_datos/insumos_publicables/economia_articulo_original/).

## Uso rápido

Requisitos: Python 3.11 o superior.

```bash
python -m pip install -e '.[test]'
python 04_reproduccion_python/reproducir_todo.py
```

El script descarga automáticamente los archivos necesarios de la MIP v1.0.0.
Para trabajar sin conexión:

```bash
python 04_reproduccion_python/reproducir_todo.py \
  --mip-dir ../mip-guatemala-2013-reproducible
```

Las tablas se escriben en `06_resultados/` y los controles en
`07_verificacion/`. La suite también puede ejecutarse de forma independiente:

```bash
pytest -q
```

El punto de entrada instalado es equivalente:

```bash
e10-gt-reproducir --mip-dir ../mip-guatemala-2013-reproducible
```

## Cuaderno versionado y ejecución en Colab

El cuaderno canónico se versiona en
[`05_cuaderno_colab/reproducir_resultados_e10.ipynb`](05_cuaderno_colab/reproducir_resultados_e10.ipynb).
Puede abrirse directamente en Google Colab con el distintivo al inicio de este
README. Muestra la matemática y las sustituciones antes de cada resultado,
mantiene plegado el código de preparación y presenta las gráficas como objetos
interactivos. No es necesario subir este cuaderno nuevo a Drive: Git conserva
la versión auditable, el historial y las pruebas.

Durante la revisión, el enlace abre y ejecuta la rama
`revision-e5-e10-trazabilidad`, sin modificar `main`. El cuaderno clona esa
misma rama automáticamente, por lo que la interfaz que se ve y el código que se
ejecuta corresponden a la misma revisión.

Drive se utilizó para **recuperar el cuaderno original del artículo**, no como
destino del cuaderno nuevo. Los roles de los dos artefactos recuperados y el
alcance de la verificación están documentados —sin publicar sus
identificadores— en
[`00_fuentes_y_trazabilidad/estado_reproducibilidad.md`](00_fuentes_y_trazabilidad/estado_reproducibilidad.md).

## Agregados E10 de emisiones reportados en el manuscrito

- 1986–2023: 104,318,087 tCO2 de referencia, 97,197,053 tCO2 con E10 y
  7,121,034 tCO2 evitadas.
- 2026–2030: 41,728,481 tCO2 de referencia, 38,879,982 tCO2 con E10 y
  2,848,499 tCO2 evitadas.

Estos agregados pertenecen al bloque ambiental E10 y no deben mezclarse con el
escenario económico E5 recuperado. El cuaderno original hallado en Drive
conserva en sus salidas Plotly las series anuales de 1986–2023 y de la
proyección, además de sus parámetros y del ajuste log-lineal sobre 2014–2023.
Esas salidas permiten reconstruir y comprobar los valores anuales y sus sumas.

Una copia externa del libro primario, hoja `1.CONSUMO FINAL`, fue recuperada y
verificada. Contiene 38 filas continuas de 1986–2023 y sus columnas son `No`,
`año` y `BTU`. Los 38 valores BTU, CO2 de referencia y millones de galones
coinciden con la reconstrucción pública al serializarlos con 15 cifras
significativas. El nombre y la huella de esa copia se omiten en esta rama
pública sanitizada.

El Excel se conserva fuera del repositorio y no incluye URL, nota metodológica
ni licencia que permitan atribuir o autorizar su redistribución. Por eso el CSV
público mantiene la etiqueta `recovered_output`, ahora acompañada por una
verificación contra la copia primaria. La actualización EIA sigue siendo un
linaje abierto distinto y no se calibra para forzar coincidencia.

Quien tenga acceso a una copia local del cuaderno original puede regenerar y
verificar el CSV recuperado —incluidas las cuatro huellas semánticas Plotly— con:

```bash
python 04_reproduccion_python/extraer_contrafactual_cuaderno.py \
  --cuaderno /ruta/cuaderno_original.ipynb
```

Una copia autorizada del Excel puede verificarse sin copiarla al repositorio:

```bash
python 04_reproduccion_python/verificar_series_ccse.py \
  --workbook "/ruta/libro_primario.xlsx"
```

El verificador público comprueba estructura, las 38 observaciones,
conversiones, el ajuste `np.polyfit` original, proyecciones y totales
publicados. La identidad privada del archivo solo puede cotejarse en una
auditoría local autorizada.

El pipeline y las pruebas públicas no requieren ni redistribuyen ese cuaderno
privado.

Aunque las salidas recuperadas contienen proyecciones para 2024 y 2025, el
total publicado como “1986–2030” une únicamente 1986–2023 con 2026–2030. Esos
dos años no entran en el total reportado y, por tanto, la etiqueta no representa
un intervalo acumulado continuo.

## Lectura de la reconstrucción contemporánea

La malla E10/E15/E20 calcula volúmenes físicos, costo por unidad de servicio
energético, importación de alcohol carburante y transmisión de costos sobre la
MIP 2013. Su escenario central supone abastecimiento importado; por ello no
aplica automáticamente un choque positivo a la producción nacional.

Los contrafactuales domésticos se expresan por Q1 millón de demanda final
adicional y usan concordancias alternativas de la MIP para hacer visible la
incertidumbre de clasificación. La referencia a procurar al menos 50 millones
de galones anuales desde Estados Unidos se trata como referencia de procedencia,
no como un contrato ejecutado.

## Limitaciones y advertencias

- Los parámetros históricos `Pg=Q10.50/L`, `Pe=Q7.50/L`, participación de
  gasolina `α=0.45` y abastecimiento doméstico `s=0.70` no tienen una fuente
  primaria incorporada en el cuaderno recuperado.
- El archivo histórico rotulado como valor agregado total está mal rotulado: es el residual
  `x − ΣZ_doméstica`, que incluye componentes distintos del valor agregado
  bruto. La igualdad histórica `ΣΔVA = ΣΔy` es una identidad contable y no debe
  publicarse como efecto sobre el VAB.
- La ecuación histórica de demanda aplica una proporción volumétrica a un
  agregado monetario sin precio relativo ni conversión física.
- P068 agrupa gasolina, diésel y fuel oil; la participación de gasolina es un
  parámetro, no una observación separada de la MIP.
- La clasificación no identifica un producto único de etanol. La reproducción
  histórica asigna la demanda doméstica a P010; los contrafactuales actuales son
  aproximaciones explícitas, no una atribución observada.
- Las emisiones corresponden a CO2 de escape y no constituyen un análisis de
  ciclo de vida.
- Las salidas embebidas del cuaderno original permiten reconstruir el
  contrafactual anual y la proyección, pero no sustituyen al Excel primario
  ausente. La razón energética `0.659375` aparece en el código como
  `21.1/32`; esos poderes caloríficos son parámetros del cuaderno, no una
  medición independiente incorporada al repositorio.
- La serie anual EIA y su proyección log-lineal son una reconstrucción abierta
  separada; no sustituyen ni completan la procedencia primaria del cálculo
  original OLADE/sieLAC.
- Los resultados económicos son estáticos, lineales y dependen de una MIP de
  2013.
- No se estiman efectos sobre seguridad alimentaria sin datos de uso de suelo,
  oferta agrícola y sustitución.

## Actualización de datos

1. Descargue la versión más reciente del archivo internacional de EIA.
2. Ejecute `04_reproduccion_python/actualizar_serie_eia.py` para extraer la
   serie de Guatemala.
3. Registre fecha, URL, identificador de serie y huella SHA-256.
4. Actualice precios únicamente con observaciones comparables en fecha, mercado
   y condición de entrega.
5. Ejecute el flujo completo y revise todos los controles antes de reemplazar
   resultados.
6. Si BANGUAT publica una MIP nueva, cree una configuración versionada y una
   concordancia entre clasificaciones; no sobrescriba la dependencia fijada.

La guía detallada está en
[`00_fuentes_y_trazabilidad/guia_actualizacion.md`](00_fuentes_y_trazabilidad/guia_actualizacion.md).

## Estructura

```text
00_fuentes_y_trazabilidad/  cadena de cálculos, estado, evidencia y fuentes
01_datos/                   insumos históricos, publicables, caché y procesados
02_concordancias/           productos MIP y agregaciones analíticas
03_configuracion/           parámetros y escenarios versionados
04_reproduccion_python/     script maestro y módulos
05_cuaderno_colab/          interfaz didáctica de ejecución
06_resultados/              tablas, figuras y salidas generadas
07_verificacion/            pruebas, manifiestos y controles
```

## Dependencia principal

- MIP Guatemala 2013 reproducible, versión 1.0.0: <https://doi.org/10.5281/zenodo.22086008>
- Repositorio: <https://github.com/JA-Osorio/mip-guatemala-2013-reproducible>

## Cómo citar y archivar

Los metadatos de autoría y versión están en [`CITATION.cff`](CITATION.cff) y
[`.zenodo.json`](.zenodo.json). Antes de la primera versión estable:

1. conecte el repositorio público con Zenodo;
2. cree una versión en GitHub únicamente después de que todos los controles
   pasen;
3. archive esa versión en Zenodo;
4. añada el DOI asignado a ambos archivos de metadatos y al distintivo del
   README.

Esta versión pública de desarrollo todavía no cuenta con DOI propio; no se ha
inventado uno.

## Licencias

El código se distribuye bajo MIT. Las tablas creadas para este suplemento se
ofrecen bajo CC BY 4.0, salvo que una fuente externa indique otra condición.
Los artefactos históricos E5 no se redistribuyen. Esta rama registra sus roles
y transformaciones, pero omite sus identificadores privados.
