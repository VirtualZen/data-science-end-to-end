-- En Gold el maximo del dia nunca es menor que el minimo ni hay precios no positivos.
select accion_key, fecha_key, precio_minimo, precio_maximo, precio_cierre_ajustado
from {{ ref('fct_precios_diarios') }}
where precio_maximo < precio_minimo
   or precio_minimo <= 0
   or precio_cierre_ajustado <= 0
