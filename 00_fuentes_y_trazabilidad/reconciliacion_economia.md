# Reconciliación del bloque económico

Esta nota documenta la reconstrucción cuantitativa; no reproduce ni redacta el manuscrito.

## Resultado de la auditoría

Los cuadernos heredados no permitían reconstruir de punta a punta los resultados económicos con la MIP canónica: no conservaban salidas ejecutadas, usaban construcciones parciales o no documentaban el vector de choque. Por ello, los valores sectoriales anteriores no se trasladan a este suplemento.

La reconstrucción usa exclusivamente la MIP Guatemala 2013 reproducible v1.0.0 y separa dos canales:

1. **Costo importado.** El cambio del costo por servicio energético se transmite por la fila P068 de la matriz total y por la inversa de Leontief doméstica transpuesta.
2. **Producción nacional.** No se activa en el escenario central importado. Solo se presentan sensibilidades normalizadas, por separado, para P010, P052 y P055.

## Identidades

Para una fracción volumétrica `a`, una razón de poderes caloríficos `q`, precio de gasolina `Pg`, referencia FOB de alcohol `Pe` y recargo ilustrativo `m`:

```text
energia_relativa(a) = (1 - a) + a*q
precio_mezcla(a,m) = (1 - a)*Pg + a*Pe*(1 + m)
cambio_costo_servicio(a,m) = precio_mezcla(a,m) / [Pg*energia_relativa(a)] - 1
choque_directo_j = A_total[P068,j] * participacion_gasolina_P068 * cambio_costo_servicio
efecto_precio = Leontief_domestica_transpuesta * choque_directo
```

Con actividad energética constante, el volumen total de mezcla aumenta por el menor poder calorífico del alcohol. Para E10 y el volumen base configurado, se requieren 74.527 millones de galones anuales. La referencia comercial de 50 millones equivale a 67.09% de ese requerimiento; no es una compra observada ni un contrato de adquisición.

## Resultado E10 de la malla

| Recargo ilustrativo sobre FOB | Cambio costo por servicio | Mayor efecto IO con participación P068 de 45% |
|---:|---:|---:|
| 0% | -0.474531% | -0.045055% |
| 15% | +0.478230% | +0.045406% |
| 30% | +1.430991% | +0.135866% |

El signo cambia dentro del intervalo porque no existe todavía un precio entregado comparable para Guatemala. Los tres recargos tienen el mismo estatus de sensibilidad; ninguno se presenta como dato observado.

Para facilitar la sustitución de afirmaciones sectoriales amplias, `efectos_precios_mip_agregados.csv` calcula promedios ponderados por producción básica de 2013. Con una participación de gasolina en P068 de 45%, las bandas E10 son:

| Grupo analítico | Recargo 0% | Recargo 15% | Recargo 30% |
|---|---:|---:|---:|
| Agricultura, pesca y silvicultura | -0.005246% | +0.005287% | +0.015819% |
| Química y farmacéutica | -0.004673% | +0.004709% | +0.014091% |
| Transporte y logística | -0.032813% | +0.033069% | +0.098952% |
| Servicios privados | -0.002616% | +0.002637% | +0.007890% |

La concordancia de rangos está versionada en `02_concordancias/agregaciones_economia.csv`; por ello, estos agregados son auditables y no categorías implícitas.

## Contrafactuales domésticos normalizados

Por cada Q1 millón de demanda final adicional a precios de 2013:

| Proxy MIP | Multiplicador de producción | Valor agregado (Q millones de 2013) |
|---|---:|---:|
| P010 | 1.686939 | 0.791235 |
| P052 | 2.023400 | 0.830111 |
| P055 | 1.817391 | 0.798954 |

Estos tres resultados son alternativas de clasificación. No se suman, no representan producción observada y no se usan para afirmar que Guatemala abastecerá el programa con producción nacional.

## Qué dato falta para cerrar un resultado puntual

Se requiere una pareja de precios comparable en fecha y condición de entrega —idealmente CIF, mayorista o puesto en terminal en Guatemala—, además de una desagregación verificable de la participación de gasolina dentro de P068. Hasta entonces, el resultado correcto es una banda de sensibilidad y no una cifra puntual de traslado sectorial.
