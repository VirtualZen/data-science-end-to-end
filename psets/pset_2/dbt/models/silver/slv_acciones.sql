-- Universo de acciones: todo ticker que estuvo en el S&P 500 o que tiene precios, con
-- su bolsa segun los listados actuales. Las acciones que ya no cotizan (fusiones,
-- quiebras) no aparecen en los listados: su bolsa queda nula y se reporta en CALIDAD.
with tickers as (
    select ticker from {{ ref('slv_membresia_sp500') }}
    union
    select ticker from {{ ref('slv_precios_acciones') }}
),

membresia as (
    select
        ticker,
        min(fecha_inicio) as primera_fecha_sp500,
        max(coalesce(fecha_fin, cast('9999-12-31' as date))) as ultima_fecha_sp500,
        max(case when vigente then 1 else 0 end) = 1 as sigue_en_sp500,
        count(*) as periodos_en_sp500
    from {{ ref('slv_membresia_sp500') }}
    group by ticker
),

precios as (
    select ticker, min(fecha) as primera_fecha_precio, max(fecha) as ultima_fecha_precio, count(*) as dias_con_precio
    from {{ ref('slv_precios_acciones') }}
    group by ticker
)

select
    t.ticker,
    l.nombre,
    l.codigo_bolsa,
    l.bolsa,
    coalesce(l.codigo_bolsa = 'N', false) as es_nyse,
    l.ticker is not null                  as en_listado_actual,
    m.primera_fecha_sp500,
    case when m.ultima_fecha_sp500 = cast('9999-12-31' as date) then null else m.ultima_fecha_sp500 end as ultima_fecha_sp500,
    coalesce(m.sigue_en_sp500, false)     as sigue_en_sp500,
    coalesce(m.periodos_en_sp500, 0)      as periodos_en_sp500,
    p.primera_fecha_precio,
    p.ultima_fecha_precio,
    coalesce(p.dias_con_precio, 0)        as dias_con_precio
from tickers as t
left join {{ ref('brz_listados_bolsa') }} as l
    on t.ticker = l.ticker
   and not l.es_prueba
left join membresia as m
    on t.ticker = m.ticker
left join precios as p
    on t.ticker = p.ticker
