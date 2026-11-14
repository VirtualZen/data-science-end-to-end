-- DONE 3: une las ventas con su producto y calcula el monto de cada venta
-- (unidades * precio), leyendo los modelos de staging.
select
    v.id_venta,
    v.id_producto,
    v.fecha,
    v.unidades,
    p.nombre,
    p.categoria,
    p.precio,
    v.unidades * p.precio as monto
from {{ ref('stg_ventas') }} as v
inner join {{ ref('stg_productos') }} as p
    on v.id_producto = p.id_producto
