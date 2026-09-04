# Método de emisiones TTW

## Alcance

El módulo calcula CO2 de escape (*Tank-to-Wheel*, TTW); no es un análisis de
ciclo de vida. Mantiene tres linajes separados: reconstrucción anual del
artículo, controles agregados publicados y actualización abierta EIA. Ningún
linaje se usa para calibrar otro.

## Matemática común

El cuaderno original fija `LHV_g = 32.0 MJ/L`, `LHV_e = 21.1 MJ/L`, mezcla
`s = 0.10` y `EF = 69.3 tCO2/TJ`. Por tanto, la razón no es una calibración
forense de los resultados publicados, sino un cociente explícito de parámetros:

```text
rho  = LHV_e / LHV_g = 21.1 / 32.0 = 0.659375
r(s) = (1 - s) + s*rho
F(s) = (1 - s) / r(s)
d(s) = 1 - F(s)

C0 = energia_TJ * EF
Cs = C0 * F(s)
A  = C0 - Cs = C0 * d(s)
```

Para E10, `d(0.10) = 0.0682626981559366`, aproximadamente 6.83%. Todos los
resultados verifican las identidades `r`, `F`, `d` y el balance `C0 = Cs + A`.

## Linaje 1: reconstrucción anual del artículo

El artefacto principal y una copia corroborante se recuperaron de Google Drive.
Sus nombres, IDs, huellas y demás identificadores se omiten en esta rama
pública sanitizada; permanecen únicamente en el registro local de auditoría no
publicable. El principal contiene 16 celdas válidas. En la copia, la celda 0 y
las celdas 3–17 conservan la evidencia útil; la celda 1 intenta mostrar un
objeto aún no definido y las posteriores a la 17 pertenecen a un refactor
fallido con datos de demostración.

El libro esperado por ambos cuadernos tiene una hoja `1.CONSUMO FINAL` con
columnas `No`, `año` y `BTU`. Se recuperó una copia externa con 38 observaciones
continuas de 1986–2023, y la limpieza original no elimina ni reordena filas. El
nombre y la huella del archivo se omiten en esta rama pública. No se incorpora
al repositorio porque no documenta su URL, metodología ni licencia.

Antes de disponer de esa copia, se extrajeron los 38 valores anuales 1986–2023
incrustados en las salidas Plotly. El insumo derivado forense es
`01_datos/insumos_publicables/contrafactual_articulo_recuperado_1986_2023.csv`;
su SHA-256 está fijado en la configuración. La comparación posterior confirmó
38/38 coincidencias para BTU, CO2 de referencia y volumen al serializar con 15
cifras significativas. Los residuos binarios máximos son `0.05078125 BTU`,
`4.66e-9 tCO2` y `5.68e-13` millones de galones, sin efecto material sobre los
resultados.

La extracción también es reproducible cuando se dispone de una copia local del
cuaderno privado:

```bash
python 04_reproduccion_python/extraer_contrafactual_cuaderno.py \
  --cuaderno /ruta/cuaderno_original.ipynb
```

La copia externa del libro puede volver a auditarse sin redistribuirla:

```bash
python 04_reproduccion_python/verificar_series_ccse.py \
  --workbook "/ruta/libro_primario.xlsx"
```

Este control público valida hoja, columnas, secuencia, años, dominio de BTU,
conversiones, el `np.polyfit` literal del cuaderno, proyecciones y agregados. La
identidad privada del archivo puede cotejarse únicamente en una auditoría local
autorizada.

La utilidad localiza las trazas por nombre y cobertura, valida las cuatro
figuras y sus reglas E0/E10 y regenera el CSV. Además aplica controles
semánticos sobre los arreglos `{name, x, y}`, independientes de la posición de
las celdas y del estilo de Plotly. El `.ipynb` privado no es necesario para
ejecutar el pipeline público ni sus pruebas.

El *round-trip* usado para recuperar y comprobar los datos es:

```text
energia_MJ = BTU * 0.001055056
energia_TJ = energia_MJ / 1e6
C0         = energia_TJ * 69.3
litros     = energia_MJ / 32.0
millones_gal_US = litros * 0.2641720524 / 1e6
```

La proyección 2024–2030 reproduce el código original: OLS de `ln(litros)`
contra el año sobre 2014–2023 y retransformación `exp()` sin corrección de
*smearing*. La implementación usa la forma centrada equivalente sobre
`ln(energia_TJ)`: litros y energía difieren solo por un factor positivo
constante, por lo que la pendiente y las proyecciones transformadas no cambian.
Las siete proyecciones se contrastan contra las salidas Plotly incrustadas, no
contra la serie EIA.

Hay tres contextos explícitos en `contrafactual_articulo_anual.csv`:

- `historical_counterfactual_1986_2023`: E10 hipotético en los 38 años;
- `prospective_policy_2024_2030`: E0 en 2024–2025 y E10 desde 2026;
- `integrated_figure_1986_2030`: E10 en los 45 años, tal como se dibujó la
  figura integrada original.

El resumen publicado es la unión disjunta `1986–2023 + 2026–2030`; no es una
suma continua 1986–2030. Los años 2024–2025 quedan fuera del total y esta
diferencia frente a la figura integrada se controla de manera explícita. La
figura integrada evita `10,899,357.621421 tCO2`; son `929,824.828322 tCO2` más
que la suma disjunta publicada porque allí también se aplica E10 en 2024–2025.

## Linaje 2: agregados publicados como controles golden

`06_resultados/emisiones/reproduccion_publicada.csv` conserva por compatibilidad
los totales enteros del manuscrito, pero ya no son la fuente del cálculo. Su
papel es comprobar la coherencia aritmética interna del agregado: parte del
`C0` entero publicado, recalcula `C10` y `A` con `ROUND_HALF_UP` y los contrasta
con las otras dos filas publicadas. De forma independiente, los controles
`article_annual_*` redondean las sumas de la reconstrucción anual y cotejan sus
tres valores `C0`, `C10` y `A` contra el manuscrito. Así, los agregados no son
fuente de la reconstrucción anual ni la reconstrucción altera los controles
publicados. E15 y E20 en
`extensiones_mezclas_superiores.csv` son extensiones derivadas no publicadas.

## Linaje 3: actualización EIA independiente

`eia_motor_gasolina_gtm_1986_2024.csv` conserva la serie abierta
`INTL.62-2-GTM-TJ.A`. Las observaciones cubren 1986–2024 y la proyección
2025–2030 ajusta OLS log-lineal en 2015–2024. El archivo, sus metadatos y su
SHA-256 se validan antes de calcular. Esta actualización no sustituye la serie
del artículo; `comparacion_linajes.csv` informa sus diferencias.

## Salidas y controles

- `06_resultados/emisiones/serie_articulo_anual.csv`: 38 observaciones
  recuperadas y siete proyecciones.
- `06_resultados/emisiones/contrafactual_articulo_anual.csv`: 90 filas para los
  tres contextos de las cuatro gráficas originales.
- `06_resultados/emisiones/contrafactual_articulo_resumen.csv`: períodos
  histórico, prospectivo y su unión disjunta.
- `06_resultados/emisiones/actualizacion_eia_anual.csv` y
  `actualizacion_eia_resumen.csv`: linaje EIA separado.
- `07_verificacion/controles_emisiones_ttw.csv`: controles de integridad
  pública, cobertura, unicidad, *round-trips*, OLS, proyecciones golden,
  identidades, sumas y redondeo.
- `07_verificacion/diagnostico_proyeccion_emisiones.json`: procedencia,
  coeficientes y reglas de ambos modelos log-lineales.

Solo deben publicarse resultados cuando todos los controles terminen en
`PASS`.
