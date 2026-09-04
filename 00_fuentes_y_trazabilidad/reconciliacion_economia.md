# Reconciliación del bloque económico del manuscrito

## Hallazgo principal

El cálculo económico que alimentó el manuscrito fue ejecutado con una mezcla
E5, no E10. El cuaderno histórico y sus CSV fueron recuperados y auditados en
una copia privada. Sus resultados se reconstruyeron de punta a punta desde la
MIP pública v1.0.0, sin redistribuir el paquete de licencia pendiente. La
auditoría mostró que el problema no se limita al nombre del escenario: dos
resultados fueron trasladados con una interpretación equivocada y otras cifras
del texto no son salidas de la lógica computacional auditada.

La metodología del propio manuscrito sí identifica a E5 como escenario de
referencia y dice que las intensidades para E10 pueden escalarse. La
inconsistencia aparece porque el resumen, los resultados y las conclusiones
presentan después esas cifras económicas dentro del encuadre del mandato E10,
sin mostrar una corrida económica E10 ejecutada.

Los roles de la evidencia primaria se registran en el manifiesto sanitizado de
insumos externos; los identificadores completos permanecen únicamente en la
auditoría local no publicable. La receta pública de reconstrucción está en
`01_datos/insumos_publicables/economia_articulo_original/`.

## Versión del manuscrito auditada

La reconciliación se refiere exclusivamente a una instantánea que no se
redistribuye en el repositorio:

- Título: *Implementación tardía de la Ley del Alcohol Carburante: efectos
  económico-ambientales en Guatemala (1986–2030)*.
- Archivo e identificador de origen: omitidos en esta rama pública sanitizada.
- Registro de fuente: `F026`.

Una revisión posterior del manuscrito debe recibir un identificador nuevo en el
registro local de auditoría y volver a ejecutar esta concordancia de
afirmaciones.

## Qué calculó realmente el cuaderno E5

| Magnitud | Resultado reproducido | Interpretación correcta |
|---|---:|---|
| `r` de E5 frente a E0 | 1.528571% | Choque exógeno del precio efectivo de la mezcla, antes de la MIP. |
| `Δp` propagado medio | 0.000193% | Promedio simple de los 152 productos. |
| `Δp` propagado en P104–P105 | 0.001974% | Promedio de transporte terrestre, no 1.53%. |
| `ΣΔy` | Q1.877204 millones de 2013 | Demanda final adicional asignada a P010. |
| `ΣΔx` | Q3.166772 millones de 2013 | Producción inducida total de los 152 productos. |
| `Δx` de P010 | Q1.879071 millones de 2013 | Producción de caña y otras plantas azucareras. |
| Multiplicador `ΣΔx/ΣΔy` | 1.686962 | Multiplicador de producción de P010 en la instantánea histórica. |

Así se explican dos cifras trasladadas al manuscrito:

1. El `1.53%` atribuido al transporte es el `r` E5 redondeado. El resultado
   propagado de P104–P105 es aproximadamente 775 veces menor.
2. Los `Q3.17 millones` atribuidos a caña son `ΣΔx` E5 redondeado. El resultado
   de P010 es Q1.8791 millones.

El total textual también satisface la identidad aritmética
`3.166772 + 0.80 + 0.50 + 0.30 = 4.766772 ≈ 4.77`. Esto es compatible con un
doble conteo de la producción total como si fuera caña, pero la evidencia
auditada no permite afirmar cómo se obtuvieron originalmente 0.80, 0.50 y
0.30. Por tanto, el repositorio marca esa explicación como inferencia, no como
hecho probado.

## Cifras del manuscrito que no reproduce el modelo

| Afirmación del manuscrito | E5 reproducido | Estado |
|---|---:|---|
| Transporte: +1.53% | +0.001974% en P104–P105 | El texto usa el choque `r` como si fuera efecto sectorial. |
| Industria química: +0.80% | +0.000090% en P071–P076 | Sin respaldo computacional. |
| Servicios: +0.40% | +0.000092% en P101–P150, sin transporte | Sin respaldo computacional. |
| Agricultura: +0.20% | +0.000218% en P001–P030, sin P010 | Sin respaldo computacional. |
| Caña: Q3.17 millones | Q1.879071 millones | El texto usa `ΣΔx` como si fuera P010. |
| Química: Q0.80 millones | Q0.155449 millones | Sin respaldo computacional. |
| Servicios: Q0.50 millones | Q0.934484 millones | Sin respaldo computacional. |
| Transporte: Q0.30 millones | Q0.060150 millones | Sin respaldo computacional. |
| Total: Q4.77 millones | Q3.166772 millones | No es una salida del modelo. |
| Total en la discusión: Q4.75 millones | Q3.166772 millones | Inconsistencia interna: el abstract, el resumen y la tabla *demand-pull* dicen Q4.77; ninguno de los dos totales se reproduce. |
| Multiplicador: 1.13 | 1.686962 | No es el multiplicador de P010. |

Las cifras reportadas se conservan en la salida de reconciliación para mantener
la trazabilidad, pero nunca se usan como objetivos de calibración.

## Corrección E10 comparable

Para aislar el error E5→E10, el escenario `E10_misma_metodologia` modifica
únicamente la fracción de etanol de 0.05 a 0.10. Tanto E5 como E10 se calculan
contra E0 (gasolina sin etanol): E10 no representa el cambio marginal desde
E5. Mantiene los parámetros del cuaderno histórico: `Pg=Q10.50/L`,
`Pe=Q7.50/L`, penalización fija de 3%, 45% de gasolina dentro de P068 y 70% de
abastecimiento doméstico.

| Magnitud | E5 histórico | E10, misma metodología |
|---|---:|---:|
| `r` | 1.528571% | 0.057143% |
| `Δp` P104–P105 | 0.001974% | 0.0000738% |
| `ΣΔy` | Q1.877204 millones | Q3.754407 millones |
| `ΣΔx` | Q3.166772 millones | Q6.333543 millones |
| `Δx` P010 | Q1.879071 millones | Q3.758143 millones |
| Multiplicador | 1.686962 | 1.686962 |

El descenso del canal de precios no es un error de programación: con los
precios del cuaderno, duplicar la participación del etanol barato casi compensa
la penalización fija de 3%. El canal de demanda se duplica porque su ecuación
es lineal en la fracción de mezcla.

La penalización fija fue descrita específicamente para E5. Por eso el
repositorio presenta además `E10_penalizacion_lhv`, una sensibilidad que deriva
el ajuste energético de los poderes caloríficos configurados. Esta sensibilidad
no reemplaza el resultado comparable; modifica únicamente el canal
*cost-push*. Conserva exactamente el mismo *demand-pull* y volumen monetario de
etanol que `E10_misma_metodologia`, por lo que no es una corrección física
integral de la demanda por servicio energético.

## Ecuaciones históricas reproducidas

Para mezcla `e`, precios `Pg` y `Pe`, penalización `π`, participación de
gasolina `α` y contenido doméstico `s`:

```text
r = {[(1-e)Pg + ePe] (1+π) / Pg} - 1
Δp_directo = r · α · A[P068,:]
Δp_propagado = Δp_directo · L
Δy[P010] = s · e · α · Σ_j Z[P068,j]
Δx = L · Δy
```

La reproducción conserva esta lógica para explicar el origen de los valores.
Reconstruye `Z` y `x` desde la MIP v1.0.0 licenciada y resta a P105 un *offset*
de Q23.987995654604674 millones para recuperar el vector histórico. La MIP
pública serializa el ajuste CIF/FOB como Q23.9879956546108 millones; la
diferencia de aproximadamente Q0.0000000000061 millones es de redondeo. Después
vuelve a calcular `A`, `L` y el residual. No implica que todos sus supuestos
sean válidos para política pública.

## Limitaciones descubiertas

- `Pg`, `Pe`, `α=0.45` y `s=0.70` no tienen una fuente primaria incorporada en
  el cuaderno histórico.
- La ecuación de demanda aplica una proporción volumétrica a un agregado
  monetario sin precio relativo ni conversión física.
- Usa solamente la fila de consumo intermedio doméstico de P068 como base.
- La clasificación no contiene un producto específico de etanol; toda la
  demanda doméstica se asigna a P010.
- El archivo histórico rotulado como valor agregado total equivale al residual
  `x - ΣZ_doméstica`, que incluye más
  que valor agregado bruto. Por eso `ΣΔVA = ΣΔy` es una identidad contable y no
  debe publicarse como efecto sobre VAB.
- La instantánea histórica usa un vector `x` anterior que difiere de la MIP
  canónica actualmente fijada, especialmente en P105; el *offset* anterior
  reproduce esa diferencia dentro de la tolerancia declarada.

## Relación con la reconstrucción económica actual

El suplemento conserva cuatro objetos separados:

1. `E5_original`: reproducción forense del cálculo que alimentó el manuscrito.
2. `E10_misma_metodologia`: corrección mínima del error de mezcla.
3. `E10_penalizacion_lhv`: sensibilidad que corrige también el ajuste
   energético.
4. La malla E10/E15/E20 de costos importados: reconstrucción contemporánea con
   precios y MIP canónica, útil para actualización pero no para afirmar que
   reproduce las cifras económicas del manuscrito.

Esta separación evita ocultar el error histórico y evita presentar una nueva
metodología como si fuera la fuente de los resultados reportados.
