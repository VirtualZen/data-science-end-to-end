-- Dias bursatiles de la NYSE (seed calendario_nyse, de pandas_market_calendars) desde
-- fecha_inicio hasta el ultimo dia con precios cargados. Un fin de semana o un feriado no
-- es un dato faltante; un dia de este calendario sin precio, si.
with limite as (
    select max(fecha) as ultima_fecha from {{ ref('brz_precios_diarios') }}
)

select
    c.fecha,
    c.media_jornada,
    row_number() over (order by c.fecha) as orden_bursatil
from {{ ref('calendario_nyse') }} as c
cross join limite as l
where c.fecha >= cast('{{ var("fecha_inicio") }}' as date)
  and c.fecha <= l.ultima_fecha
