# Reconstrucción económica contemporánea E10/E15/E20

## Lectura correcta

Esta malla no reproduce las cifras económicas del manuscrito; es una reconstrucción separada con precios contemporáneos y la MIP canónica.

El abastecimiento central es 100% importado y su choque de demanda final doméstica es cero. Los recargos de 0%, 15% y 30% tienen el mismo estatus: son sensibilidades ilustrativas aplicadas a una referencia FOB y no observaciones de costo entregado en Guatemala.

## Malla de costos

| Mezcla | Recargo ilustrativo | Cambio costo por servicio | Etanol requerido (millones gal) | Referencia comercial / requerimiento | Variación costo total (millones USD) |
|---|---:|---:|---:|---:|---:|
| E10 | 0% | -0.474531% | 74.527 | 67.09% | -10.133 |
| E10 | 15% | 0.478230% | 74.527 | 67.09% | 10.212 |
| E10 | 30% | 1.430991% | 74.527 | 67.09% | 30.558 |
| E15 | 0% | -0.724572% | 113.796 | 43.94% | -15.473 |
| E15 | 15% | 0.730220% | 113.796 | 43.94% | 15.594 |
| E15 | 30% | 2.185012% | 113.796 | 43.94% | 46.660 |
| E20 | 0% | -0.983752% | 154.501 | 32.36% | -21.008 |
| E20 | 15% | 0.991421% | 154.501 | 32.36% | 21.171 |
| E20 | 30% | 2.966595% | 154.501 | 32.36% | 63.350 |

La participación de gasolina dentro de P068 no modifica el costo físico de la mezcla; solo escala la transmisión IO. La tabla completa conserva 45.0% y 50.2% como sensibilidades paralelas.

La referencia comercial de 50 millones de galones anuales se divide entre el requerimiento modelado de cada mezcla. Es una referencia de procedencia y escala: no se codifica como compra observada ni como contrato de adquisición.

## Agregados E10 comparables

Promedio ponderado por producción básica de 2013, con participación de gasolina en P068 de 45%:

| Grupo | Recargo | Cambio propagado ponderado |
|---|---:|---:|
| agricultura_pesca_silvicultura | 0% | -0.005246% |
| quimica_farmaceutica | 0% | -0.004673% |
| transporte_logistica | 0% | -0.032813% |
| servicios_privados | 0% | -0.002616% |
| agricultura_pesca_silvicultura | 15% | 0.005287% |
| quimica_farmaceutica | 15% | 0.004709% |
| transporte_logistica | 15% | 0.033069% |
| servicios_privados | 15% | 0.002637% |
| agricultura_pesca_silvicultura | 30% | 0.015819% |
| quimica_farmaceutica | 30% | 0.014091% |
| transporte_logistica | 30% | 0.098952% |
| servicios_privados | 30% | 0.007890% |

## Contrafactuales domésticos normalizados

| Proxy | Choque (millones Q 2013) | Multiplicador producción | Valor agregado | Puestos modelados |
|---|---:|---:|---:|---:|
| P010 | 1.00 | 1.686939 | 0.791235 | 15.815 |
| P052 | 1.00 | 2.023400 | 0.830111 | 9.518 |
| P055 | 1.00 | 1.817391 | 0.798954 | 11.862 |

## Verificación

Controles ejecutados: 28. Fallos: 0.

## Limitaciones decisivas

- La referencia FOB y los recargos ilustrativos no sustituyen una cotización CIF o mayorista comparable en Guatemala.
- P068 combina gasolina, diésel y fuel oils; 45.0% y 50.2% son sensibilidades de atribución.
- La MIP es de 2013 y no identifica un producto específico de alcohol carburante.
- P010, P052 y P055 son aproximaciones alternativas; sus efectos no deben sumarse.
- Los puestos modelados escalan coeficientes medios de 2013 y no equivalen a empleo neto observado.
