-- DONE 4: monto total por categoria, a partir del modelo intermedio.
select
    categoria,
    sum(monto) as monto_total
from {{ ref('int_ventas_con_producto') }}
group by categoria
