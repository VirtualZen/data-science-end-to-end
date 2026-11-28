-- Huecos por accion (promesa del PSet 1, etapa Datos: "porcentaje de huecos por ticker").
-- Grano: un simbolo de la composicion historica (desde fecha_inicio).
--   dias_miembro          dias bursatiles en que la accion era miembro del S&P 500
--   dias_miembro_con_precio  de esos, cuantos tienen precio en Gold
--   pct_huecos_miembro    100 * (1 - con_precio / miembro): lo que falta mientras era miembro
--   dias_vida, dias_vida_con_precio, dias_imputados, dias_excluidos: entre la primera y la
--                         ultima cotizacion (huecos dentro de la vida observada de la accion)
--   sin_precios           la fuente (Yahoo) no devolvio ningun precio (sesgo de supervivencia)
{% set inicio = "cast('" ~ var('fecha_inicio') ~ "' as date)" %}

with cal as (
    select fecha from {{ ref('slv_calendario_nyse') }}
    where fecha >= {{ inicio }}
),
memb as (
    select * from {{ ref('slv_membresia_sp500') }}
),
esperado as (
    select distinct m.ticker, c.fecha
    from memb as m
    inner join cal as c
        on c.fecha >= m.fecha_inicio
       and c.fecha <= coalesce(m.fecha_fin, cast('9999-12-31' as date))
),
observado as (
    select a.ticker, f.fecha
    from {{ ref('fct_precios_diarios') }} as p
    inner join {{ ref('dim_accion') }} as a on p.accion_key = a.accion_key
    inner join {{ ref('dim_fecha') }} as f on p.fecha_key = f.fecha_key
    where p.en_sp500
),
miembro as (
    select e.ticker,
           count(*) as dias_miembro,
           count(o.ticker) as dias_miembro_con_precio,
           min(e.fecha) as primer_dia_miembro,
           max(e.fecha) as ultimo_dia_miembro
    from esperado as e
    left join observado as o on e.ticker = o.ticker and e.fecha = o.fecha
    group by e.ticker
),
slv as (
    select ticker, fecha, imputado from {{ ref('slv_precios_acciones') }}
),
vida as (
    select ticker, min(fecha) as primera_cotizacion, max(fecha) as ultima_cotizacion,
           count(*) as dias_vida_con_precio,
           sum(case when imputado then 1 else 0 end) as dias_imputados
    from slv group by ticker
),
vida_cal as (
    select v.ticker, count(*) as dias_vida
    from vida as v
    inner join {{ ref('slv_calendario_nyse') }} as c
        on c.fecha between v.primera_cotizacion and v.ultima_cotizacion
    group by v.ticker
)
select
    m.ticker,
    m.primer_dia_miembro,
    m.ultimo_dia_miembro,
    m.dias_miembro,
    m.dias_miembro_con_precio,
    round(100.0 * (1 - m.dias_miembro_con_precio * 1.0 / m.dias_miembro), 4) as pct_huecos_miembro,
    v.primera_cotizacion,
    v.ultima_cotizacion,
    coalesce(vc.dias_vida, 0) as dias_vida,
    coalesce(v.dias_vida_con_precio, 0) as dias_vida_con_precio,
    coalesce(v.dias_imputados, 0) as dias_imputados,
    coalesce(vc.dias_vida, 0) - coalesce(v.dias_vida_con_precio, 0) as dias_excluidos,
    v.ticker is null as sin_precios
from miembro as m
left join vida as v on m.ticker = v.ticker
left join vida_cal as vc on m.ticker = vc.ticker
