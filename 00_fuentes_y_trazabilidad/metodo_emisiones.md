# Método de emisiones TTW

## Alcance

El módulo calcula CO2 de escape (*Tank-to-Wheel*, TTW) para E10, E15 y
E20. No es un análisis de ciclo de vida. El CO2 biogénico procedente del
alcohol carburante queda fuera del total del sector Energía, como partida
informativa, y se mantiene constante el servicio energético del vehículo.

## Identidad física

La referencia de gasolina se calcula con un factor de 69.3 tCO2/TJ. Para una
participación volumétrica de alcohol `s` y una razón de poderes caloríficos
inferiores `q = 0.659375`:

```text
r(s) = (1 - s) + s*q
factor_fosil(s) = (1 - s) / r(s)
reduccion_ttw(s) = 1 - factor_fosil(s)
```

Las emisiones del escenario son las emisiones de referencia multiplicadas
por `factor_fosil(s)`. Para E10, la reducción resultante es
0.0682626981559366, aproximadamente 6.83%.

La razón `0.659375` se reconstruyó a partir del porcentaje E10 publicado para
reproducir exactamente sus controles. Los poderes caloríficos impresos en el
texto estaban redondeados y, si se dividieran literalmente, producirían una
diferencia numérica pequeña pero evitable. La configuración registra esta
decisión de trazabilidad.

## Dos linajes separados

### Reproducción publicada

`06_resultados/emisiones/reproduccion_publicada.csv` parte de los totales
agregados de referencia que sustentan los resultados publicados. Aplica la
identidad anterior y reproduce, con redondeo decimal convencional, únicamente
los controles E10 de 1986–2023 y 2026–2030.

Los cálculos E15 y E20 sobre esos mismos agregados se guardan, claramente
separados, en
`06_resultados/emisiones/extensiones_mezclas_superiores.csv`. Son escenarios
derivados y no resultados publicados.

### Actualización EIA

`01_datos/insumos_publicables/eia_motor_gasolina_gtm_1986_2024.csv` conserva
la serie `INTL.62-2-GTM-TJ.A`, consumo anual de gasolina de motor en Guatemala,
extraída del archivo internacional masivo de la U.S. Energy Information
Administration. La fuente oficial y el identificador están declarados en
`03_configuracion/emisiones_ttw.json`.

Las observaciones cubren 1986–2024. La proyección 2025–2030 es una regresión
lineal por mínimos cuadrados de `ln(energia_tj)` contra el año, ajustada en
2015–2024. Se retransforma con la función exponencial sin corrección de
*smearing*: el objetivo es extrapolar la mediana condicional de la tendencia
log-lineal. La ventana puede cambiarse en la configuración sin editar código.

La actualización EIA no se calibra para igualar los agregados publicados. Las
diferencias se informan en
`06_resultados/emisiones/comparacion_linajes.csv`; no constituyen por sí mismas
un error de reproducción porque los insumos de origen son distintos.

## Archivos derivados

- `01_datos/procesados/energia_gasolina_observada_y_proyectada_1986_2030.csv`:
  energía anual observada y proyectada.
- `06_resultados/emisiones/actualizacion_eia_anual.csv`: emisiones anuales por
  mezcla.
- `06_resultados/emisiones/actualizacion_eia_resumen.csv`: agregados por
  período.
- `06_resultados/emisiones/extensiones_mezclas_superiores.csv`: extensiones
  físicas derivadas de los agregados, fuera de la reproducción publicada.
- `07_verificacion/controles_emisiones_ttw.csv`: nueve controles automáticos.
- `07_verificacion/diagnostico_proyeccion_emisiones.json`: ventana, coeficientes
  y bondad de ajuste de la proyección.

## Actualización

Al publicarse una revisión de la serie EIA:

1. Extraer nuevamente solo `INTL.62-2-GTM-TJ.A` del archivo masivo oficial.
2. Sustituir el CSV fuente conservando nombres, unidades y metadatos.
3. Actualizar los años observado, de ajuste y de proyección en la configuración.
4. Ejecutar el flujo completo.
5. Publicar resultados únicamente si los nueve controles terminan en `PASS`.
