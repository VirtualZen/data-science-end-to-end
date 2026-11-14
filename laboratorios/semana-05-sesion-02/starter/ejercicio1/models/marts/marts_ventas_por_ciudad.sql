select
    ciudad,
    count(*) as numero_pedidos,
    sum(monto_total) as monto_total
from {{ ref('int_pedidos_con_cliente') }}
group by ciudad
