-- DONE 1: lista las columnas de raw_productos que el resto del proyecto usa.
select
    id_producto,
    nombre,
    categoria,
    precio
from raw_productos
