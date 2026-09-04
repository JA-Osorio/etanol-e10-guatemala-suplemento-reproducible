# Guía didáctica de actualización

Esta guía mantiene separadas la reproducción de las cifras del manuscrito y la evidencia normativa nueva. Ninguna actualización debe modificar silenciosamente una corrida anterior.

## 1. Prepare una versión nueva

1. Cree una rama o copia de trabajo.
2. Registre la fecha de corte en `registro_fuentes.csv` y `cronologia_gobernanza.csv`.
3. Descargue cada insumo a una carpeta temporal; conserve nombre original, URL, fecha de consulta y suma SHA-256.
4. No incorpore archivos cuya licencia no permita redistribución. En ese caso, deje instrucciones de descarga y una prueba de integridad.

## 2. Revise primero la normativa

Consulte el índice oficial del MEM, el Diario de Centro América, MINECO, USTR y el Congreso. Verifique al menos:

- porcentaje aplicable y tipo de gasolina cubierto;
- fecha efectiva y cualquier fase de acondicionamiento;
- dictámenes técnicos o económicos pendientes;
- metodología de seguridad de suministro, inventarios y fiscalización;
- estado del acuerdo comercial y de las iniciativas legislativas;
- cambios en definiciones, calidad, trazabilidad o composición del alcohol carburante.

Al corte de esta versión, la actualización factual cubre gasolina regular desde el 22 de agosto de 2026. La gasolina superior permanece fuera hasta que exista una disposición, dictamen y datos verificables. El calendario está en `03_configuracion/calendario_transicion.csv`.

## 3. Actualice procedencia y comercio

1. Descargue de BANGUAT el comercio exterior por inciso SAC, país y mes.
2. Documente los códigos usados y si distinguen el uso carburante de otros usos.
3. Concilie volumen, valor y país con registros del MEM y portuarios.
4. Calcule por separado importación observada, producción nacional observada y residuo no identificado.
5. No convierta la referencia de 50 millones de galones del acuerdo en una compra observada: el texto dice que Guatemala procurará comprar ese volumen y no constituye evidencia de un contrato ejecutado.

El escenario `observado_importado` usa flujos registrados. El escenario `domestico_contrafactual` es una sensibilidad y nunca debe presentarse como pronóstico sin datos de producción y ventas nacionales.

## 4. Actualice emisiones sin mezclar objetivos

- `contrafactual_articulo_anual.csv` conserva la reconstrucción desde las
  salidas ejecutadas del cuaderno original; no la reemplace con la serie EIA.
- `reproduccion_publicada` conserva, por compatibilidad del identificador, los
  agregados reportados y funciona como control dorado, no como fuente anual.
- `actualizacion_normativa_2026` aplica la fecha y el alcance regulatorio vigentes.
- Las nuevas series deben conservar su fuente, unidad, cobertura y transformación.
- Un cambio de calendario no debe reescribir la reproducción de las cifras reportadas.

Si vuelve a obtenerse el cuaderno original, regenere el derivado con
`04_reproduccion_python/extraer_contrafactual_cuaderno.py` y compruebe sus
cuatro controles semánticos Plotly. La copia recuperada del libro primario ya
constituye otro escalón de procedencia: su estructura y comparación 38/38 están
documentadas. Una copia futura debe volver a validarse con
`04_reproduccion_python/verificar_series_ccse.py` contra la reconstrucción
existente; la identidad del archivo puede cotejarse en el registro local
autorizado, pero se omite en esta rama pública. No cambie
silenciosamente el estado `recovered_output` por `original_input`: el CSV sigue
siendo derivado, aunque ya esté validado contra una copia del libro primario.

Si se actualiza la serie energética, ejecute primero controles de unidades, valores ausentes, cobertura anual y suma acumulada. Genere una tabla de diferencias frente a la versión anterior.

## 5. Actualice el análisis económico

1. No modifique `E5_original`: sus parámetros, la receta pública P105 y los
   resultados son una instantánea forense con pruebas doradas. Los archivos
   privados originales se identifican únicamente en el registro local de
   auditoría; esta rama pública omite esos identificadores. Una corrección
   adicional debe crear otro escenario y no reescribir ese linaje.
2. Mantenga `E10_misma_metodologia` como comparación de un solo cambio
   (`mix_e: 0.05 → 0.10`). Las mejoras de método deben publicarse como
   sensibilidades distintas, por ejemplo `E10_penalizacion_lhv`.
3. Mantenga fijada la dependencia de la MIP contemporánea; una MIP nueva
   requiere configuración y concordancia nuevas.
4. Separe efectos domésticos de fugas importadas.
5. Active producción nacional solo con una participación respaldada por datos
   o como contrafactual rotulado.
6. Registre precios comparables en fecha, mercado, condición de entrega,
   impuestos y unidad energética.
7. Ejecute todas las sensibilidades y explique cualquier diferencia material.

## 6. Seguridad alimentaria y gobernanza

La MIP no identifica por sí sola uso de suelo, agua, acceso alimentario, distribución del ingreso o conflictividad. Para ampliar el suplemento se requieren módulos separados con:

- Hoja de Balance de Alimentos y precios de alimentos básicos;
- área, rendimiento y cambio de uso de suelo por cultivo y territorio;
- disponibilidad de melaza, azúcar, agua y otros insumos;
- presupuesto, personal, laboratorio, inspecciones, muestras e inventarios;
- actas de consulta, comentarios recibidos y respuestas oficiales.

Registre las afirmaciones institucionales y críticas como hipótesis contrastables. Plaza Pública se usa solo para identificar preguntas de gobernanza y distribución; no se copia su texto ni se usan sus conclusiones como parámetros.

## 7. Ejecute y verifique

```bash
python -m pip install -e '.[test]'
python 04_reproduccion_python/reproducir_todo.py
python -m pytest 07_verificacion/tests
```

Antes de publicar una versión:

- valide todos los CSV y JSON;
- compruebe enlaces y huellas digitales;
- confirme que no hay rutas privadas, credenciales ni datos restringidos;
- regenere tablas, figuras y manifiesto desde cero;
- compare resultados contra la versión anterior;
- actualice `CITATION.cff`, notas de versión y DOI solo después de aprobar la auditoría.

## 8. Política de versionado

Use versiones mayores para cambios de método, menores para nuevas fuentes o escenarios compatibles y parches para documentación o correcciones que no cambian resultados. Nunca sustituya un archivo publicado sin conservar la versión anterior y explicar la diferencia.
