# Historial de cambios

## 0.2.0 · 2026-09-03

- Recupera y audita privadamente el cuaderno, el informe y los insumos que
  generaron el cálculo E5; esta rama pública registra sus roles sin
  redistribuirlos ni revelar sus identificadores.
- Reconstruye públicamente la instantánea histórica desde la MIP v1.0.0
  licenciada y un *offset* de reconstrucción P105 explícito.
- Reproduce el escenario histórico E5 e identifica dos errores de
  interpretación: `1.53%` es el choque inicial `r`, no el efecto en transporte,
  y `Q3.17 millones` es la producción inducida total, no la producción de caña.
- Documenta que `0.80`, `0.50`, `0.30`, `Q4.77 millones` y el multiplicador
  `1.13` no son salidas del modelo preservado.
- Añade el escenario E10 comparable, que cambia únicamente la fracción de
  etanol, y una sensibilidad E10 basada en poderes caloríficos.
- Separa explícitamente la reproducción económica histórica de la
  reconstrucción contemporánea E10/E15/E20.
- Corrige la interpretación del archivo histórico rotulado como valor agregado
  total: es un residual contable. Renombra las salidas para impedir que se lean
  como VAB y registra los parámetros históricos sin fuente primaria.
- Ancla las cifras reconciliadas a una versión auditada del manuscrito, cuyo
  identificador se conserva fuera de esta rama pública, y registra su
  discrepancia interna entre Q4.77 y Q4.75 millones.
- Convierte la concordancia sectorial en un insumo computacional verificable y
  cobertura exhaustiva P001–P152.
- Actualiza la verificación automática y el flujo continuo para aceptar y
  comprobar el linaje E5 junto con los escenarios E10.
- Recupera las series anuales 1986–2023 del contrafactual de emisiones desde
  arrays Plotly embebidos en el cuaderno principal y verifica su igualdad
  exacta contra una copia corroborante, sin redistribuir ninguno de los dos
  cuadernos ni revelar sus identificadores.
- Recupera y verifica una copia externa del libro primario, hoja
  `1.CONSUMO FINAL`, y comprueba 38/38 valores BTU, CO2 y volumen contra la
  reconstrucción a 15 cifras significativas. El libro no se redistribuye y su
  identificador se omite porque su procedencia estadística y licencia siguen
  pendientes.
- Publica el CSV anual recuperado como tabla derivada CC BY 4.0, con estado de
  procedencia por fila y un control de integridad reproducible, sin presentarlo como
  una copia del libro primario.
- Sustituye en el cuaderno reproducible las figuras estáticas del análisis por
  gráficas Plotly interactivas, con leyendas conmutables y trazabilidad visible
  de escenario, unidad y linaje.

## 0.1.0 · 2026-08-24

- Reproduce exactamente los controles E10 de emisiones TTW reportados en el manuscrito.
- Separa la actualización EIA del linaje de cifras reportadas.
- Reconstruye el canal económico con MIP Guatemala 2013 v1.0.0.
- Establece abastecimiento central importado y contrafactuales domésticos
  normalizados.
- Añade sensibilidades E10, E15 y E20, calendario normativo, gobernanza y
  procedencia.
- Incorpora cuaderno Colab, pruebas automáticas, figuras y manifiesto de
  resultados.
