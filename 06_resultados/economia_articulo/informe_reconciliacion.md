# Reconciliacion del calculo economico del manuscrito

## Version del manuscrito

Titulo: *Implementación tardía de la Ley del Alcohol Carburante: efectos económico-ambientales en Guatemala (1986–2030)*.

Archivo no redistribuido: `identificador_omitido_en_rama_publica`.

SHA-256: `omitido_en_rama_publica`.

## Resultado principal

El calculo recuperado es un escenario E5. El 1.53% reportado en el manuscrito coincide con el choque inicial `r` de E5, no con el efecto de precios propagado para transporte. De forma analoga, Q3.17 millones coincide con el cambio de produccion total de E5, no con la produccion de cana P010.

## Escenarios calculados

| Escenario | Naturaleza | Mezcla | Penalizacion efectiva | r | Delta y (millones Q 2013) | Delta x (millones Q 2013) | Residual no intermedio domestico (millones Q 2013) | Multiplicador |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| E5_original | reproduccion_forense | 5% | 3.000000% | 1.528571% | 1.877204 | 3.166772 | 1.877204 | 1.686962 |
| E10_misma_metodologia | recalculo_comparable | 10% | 3.000000% | 0.057143% | 3.754407 | 6.333543 | 3.754407 | 1.686962 |
| E10_penalizacion_lhv | sensibilidad_fisica_separada | 10% | 3.492885% | 0.535945% | 3.754407 | 6.333543 | 3.754407 | 1.686962 |

Con la penalizacion fija de 3%, cambiar solo la mezcla de 5% a 10% reduce `r` de 1.528571% a 0.057143%. Esto es una consecuencia aritmetica de los precios heredados (Q10.50 y Q7.50 por litro), no una hipotesis nueva.

La fila `E10_penalizacion_lhv` reemplaza el factor fijo 1.03 por `32 / ((1-mix)*32 + mix*21.2)`. Se reporta como sensibilidad fisica separada y no se usa para afirmar que el cuaderno original calculo E10.

La sensibilidad LHV modifica solo el canal de precios. Conserva sin cambios el choque de demanda del E10 comparable; no ajusta volumen de etanol ni demanda por servicio energetico.

La columna de residual reproduce la variable historica llamada `Delta VA`, pero `VA_2013_total.csv` es `x - suma Z domestica`; no representa valor agregado bruto y no debe interpretarse como VAB.

## Reconciliacion de cifras reportadas en el manuscrito

| Bloque | Cifra/etiqueta | Manuscrito | E5 recalculado | E10 misma metodologia | Diagnostico |
|---|---|---:|---:|---:|---|
| cost_push | Transporte | 1.530000 | 0.001974 | 0.000074 | 1.53% coincide por redondeo con r del E5; no con el efecto propagado de transporte. |
| cost_push | Industria quimica | 0.800000 | 0.000090 | 0.000003 | El porcentaje del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| cost_push | Servicios | 0.400000 | 0.000092 | 0.000003 | El porcentaje del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| cost_push | Agricultura | 0.200000 | 0.000218 | 0.000008 | El porcentaje del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| demand_pull | Cana de azucar | 3.170000 | 1.879071 | 3.758143 | 3.17 coincide por redondeo con delta x total E5; no con la produccion P010. |
| demand_pull | Industria quimica | 0.800000 | 0.155449 | 0.310898 | El valor del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| demand_pull | Servicios | 0.500000 | 0.934484 | 1.868969 | El valor del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| demand_pull | Transporte | 0.300000 | 0.060150 | 0.120300 | El valor del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada. |
| demand_pull | Total | 4.770000 | 3.166772 | 6.333543 | 4.77 no se reproduce ni para E5 ni para E10 con la logica heredada. |
| demand_pull | Total (discusion) | 4.750000 | 3.166772 | 6.333543 | La discusion dice 4.75, mientras el abstract, el resumen y la tabla demand-pull dicen 4.77; ninguno se reproduce con la logica heredada. |
| demand_pull | Multiplicador | 1.130000 | 1.686962 | 1.686962 | 1.13 no se reproduce; la matriz heredada arroja aproximadamente 1.687. |

## Lectura forense

- E5 reproducido: `r=0.015285714285714`, `Delta x=3.166771669703` y `Delta x P010=1.879071380917`.
- Los valores Q0.8 millones (quimica), Q0.5 millones (servicios), Q0.3 millones (transporte), Q4.77 millones (total del abstract, resumen y tabla demand-pull), Q4.75 millones (total de la discusion) y el multiplicador 1.13 no salen de los CSV y formulas recuperados.
- Los resultados por producto permiten rastrear cada agregado hasta P001-P152.

## Verificacion

Controles ejecutados: 37. Fallos: 0.
