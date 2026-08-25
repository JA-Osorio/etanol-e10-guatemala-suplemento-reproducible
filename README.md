# E10 Guatemala: material suplementario reproducible

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/JA-Osorio/etanol-e10-guatemala-suplemento-reproducible/blob/main/05_cuaderno_colab/reproducir_resultados_e10.ipynb)
[![MIP Guatemala 2013](https://img.shields.io/badge/MIP_Guatemala_2013-v1.0.0-2f6f4e)](https://doi.org/10.5281/zenodo.22086008)

Código, datos publicables y controles para reproducir y actualizar un análisis cuantitativo de mezclas de gasolina con alcohol carburante en Guatemala. El escenario mínimo es E10; las comparaciones adicionales consideran E15 y E20.

Este repositorio es material suplementario en línea. No contiene el manuscrito, no sustituye su argumentación y no reconstruye la matriz insumo-producto. La MIP se consume como dependencia pública, fijada en la versión 1.0.0.

Autores: Juan Alejandro Osorio, Silvia Patricia Villatoro y Noé Salguero.

## Qué reproduce

- El método de emisiones de escape del artículo: límite *Tank-to-Wheel*, servicio energético constante, factor de 69.3 tCO2/TJ y tratamiento del CO2 biogénico como partida informativa.
- Los controles agregados publicados para E10, sin alterar esas cifras.
- Una actualización normativa separada, con el alcance vigente y una serie pública documentada.
- Volúmenes físicos, costo de la mezcla por unidad de servicio energético e importación de alcohol carburante para E10, E15 y E20.
- Un modelo de transmisión de costos sobre la MIP 2013.
- Contrafactuales normalizados de producción nacional. No se interpretan como pronóstico de producción guatemalteca.
- Escenarios de procedencia importada, incluida la referencia de procurar compras de al menos 50 millones de galones anuales desde Estados Unidos; no se trata como contrato ejecutado.

## Uso rápido

Requisitos: Python 3.11 o superior.

```bash
python -m pip install -e .
python 04_reproduccion_python/reproducir_todo.py
```

El script descarga automáticamente los archivos necesarios de la MIP v1.0.0. Para trabajar sin conexión:

```bash
python 04_reproduccion_python/reproducir_todo.py \
  --mip-dir ../mip-guatemala-2013-reproducible
```

Las tablas se escriben en `06_resultados/` y los controles en `07_verificacion/`.

También puede ejecutar el punto de entrada instalado:

```bash
e10-gt-reproducir --mip-dir ../mip-guatemala-2013-reproducible
```

## Resultados de control de esta versión

- Emisiones E10 publicadas, 1986–2023: 104,318,087 tCO2 de referencia, 97,197,053 tCO2 con E10 y 7,121,034 tCO2 evitadas.
- Emisiones E10 publicadas, 2026–2030: 41,728,481 tCO2 de referencia, 38,879,982 tCO2 con E10 y 2,848,499 tCO2 evitadas.
- Requerimiento físico E10 con el volumen base configurado: 74.527 millones de galones de alcohol carburante; la referencia bilateral de 50 millones representa 67.09%.
- Cambio del costo por servicio E10: entre -0.474531% y +1.430991% al variar el recargo ilustrativo sobre la referencia FOB de 0% a 30%.
- Efecto sectorial máximo E10 con participación de gasolina en P068 de 45%: entre -0.045055% y +0.135866% en la misma sensibilidad.
- Promedio agregado E10 de transporte y logística: entre -0.032813% y +0.098952%; química y farmacéutica: entre -0.004673% y +0.014091%.
- Controles automáticos: 9/9 en emisiones, 27/27 en economía y 5/5 en transiciones.

El bloque económico no fuerza una cifra puntual: todavía falta un precio entregado comparable para Guatemala. La reconciliación está documentada en [`00_fuentes_y_trazabilidad/reconciliacion_economia.md`](00_fuentes_y_trazabilidad/reconciliacion_economia.md).

## Lectura correcta de los resultados

El repositorio separa tres objetos que no deben confundirse:

1. `reproduccion_publicada`: verifica los agregados E10 ya publicados.
2. `actualizacion_normativa_2026`: aplica a la gasolina regular desde el 22 de agosto de 2026; la gasolina superior permanece fuera hasta contar con dictamen, disposición y datos verificables.
3. `comparacion_economica`: calcula costos, importaciones y efectos IO con parámetros trazables y sensibilidades.

El escenario central de abastecimiento es importado. En consecuencia, no se aplica automáticamente un choque positivo de demanda final a la producción nacional. Los contrafactuales domésticos se reportan por Q1 millón de demanda final adicional y con tres concordancias alternativas de la MIP; esto hace visible la incertidumbre de clasificación.

## Actualización de datos

1. Descargue la versión más reciente del archivo internacional de EIA.
2. Ejecute `actualizar_serie_eia.py` para extraer la serie de Guatemala.
3. Registre fecha, URL, identificador de serie y huella SHA-256.
4. Actualice precios únicamente con observaciones comparables en fecha, mercado y condición de entrega.
5. Ejecute el flujo completo y revise todos los controles antes de reemplazar resultados.
6. Si BANGUAT publica una MIP nueva, no sobrescriba la dependencia: cree una configuración versionada y documente una concordancia entre clasificaciones.

La guía detallada está en [`00_fuentes_y_trazabilidad/guia_actualizacion.md`](00_fuentes_y_trazabilidad/guia_actualizacion.md).

## Estructura

```text
00_fuentes_y_trazabilidad/  registro de evidencia y guía de actualización
01_datos/                   insumos publicables, caché y datos procesados
02_concordancias/           productos MIP y agregaciones analíticas
03_configuracion/           parámetros y escenarios versionados
04_reproduccion_python/     script maestro y módulos
05_cuaderno_colab/          interfaz didáctica de ejecución
06_resultados/              tablas, figuras y salidas generadas
07_verificacion/            pruebas, manifiestos y controles
```

## Límites

- Las emisiones corresponden a CO2 de escape. No son un análisis de ciclo de vida.
- Los resultados económicos son estáticos, lineales y dependen de una MIP de 2013.
- P068 agrupa gasolina, diésel y fuel oil; la participación de gasolina se trata como parámetro y sensibilidad.
- La MIP no identifica un producto único de alcohol carburante. Los contrafactuales domésticos son aproximaciones explícitas, no una atribución observada.
- Un compromiso de procurar compras no equivale a un contrato de adquisición ejecutado.
- No se calculan efectos sobre seguridad alimentaria sin datos de uso de suelo, oferta agrícola y sustitución; el registro de evidencia indica qué sería necesario para hacerlo.

## Dependencia principal

- MIP Guatemala 2013 reproducible, versión 1.0.0: <https://doi.org/10.5281/zenodo.22086008>
- Repositorio: <https://github.com/JA-Osorio/mip-guatemala-2013-reproducible>

## Cómo citar y archivar

Los metadatos de autoría y versión están en [`CITATION.cff`](CITATION.cff) y [`.zenodo.json`](.zenodo.json). Antes de la primera versión estable:

1. conecte el repositorio público con Zenodo;
2. cree una versión en GitHub únicamente después de que todos los controles pasen;
3. archive esa versión en Zenodo;
4. añada el DOI asignado a ambos archivos de metadatos y al distintivo del README.

No se ha inventado un DOI para esta preparación local.

## Licencias

El código se distribuye bajo MIT. Las tablas creadas para este suplemento se ofrecen bajo CC BY 4.0, salvo que una fuente externa indique otra condición.
