-- DONE 1: lista las columnas de raw_ventas que el resto del proyecto usa.
-- select distinct *
select distinct
    id_venta,
    id_producto,
    fecha,
    unidades
from raw_ventas
