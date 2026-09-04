# Insumos históricos no redistribuidos

Los siete CSV exactos del paquete E5 no se incluyen porque la licencia del
paquete quedó pendiente. Sus huellas se registran en
`03_configuracion/economia_articulo.json` y en el manifiesto externo.

La reproducción pública no depende de esas copias. El módulo parte de la MIP
Guatemala 2013 v1.0.0 fijada y licenciada, lee `Z_domestica_2013.csv`,
`productos_2013.csv` y `produccion_y_utilizacion_2013.csv`, y reconstruye la
variante histórica así:

1. toma `total_utilizacion_precios_basicos` como vector `x`;
2. resta un *offset* de Q23.987995654604674 millones a P105 para recuperar el
   vector histórico; el ajuste CIF/FOB serializado en la MIP pública es
   Q23.9879956546108 millones y la diferencia de aproximadamente
   Q0.0000000000061 millones corresponde al redondeo;
3. calcula `A = Z / x`, `L = (I-A)⁻¹` y el residual
   `x - ΣZ_doméstica`;
4. comprueba las salidas contra los valores dorados del cuaderno privado.

Esta reconstrucción reproduce las cifras históricas dentro de una tolerancia
absoluta de `5e-13` sin redistribuir el material de licencia incierta.
