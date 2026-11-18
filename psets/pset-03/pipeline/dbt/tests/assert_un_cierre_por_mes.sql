-- Regla de negocio: el rebalanceo es mensual, asi que cada mes cerrado tiene
-- exactamente un dia de cierre (el ultimo dia bursatil) y el mes en curso ninguno.
select anio_mes, mes_cerrado, sum(case when es_cierre_de_mes then 1 else 0 end) as cierres
from {{ ref('dim_fecha') }}
group by anio_mes, mes_cerrado
having (mes_cerrado and sum(case when es_cierre_de_mes then 1 else 0 end) <> 1)
    or (not mes_cerrado and sum(case when es_cierre_de_mes then 1 else 0 end) <> 0)
