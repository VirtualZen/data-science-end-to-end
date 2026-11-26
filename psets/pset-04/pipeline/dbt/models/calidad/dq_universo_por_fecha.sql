-- Universo de cada fecha frente a la composicion historica (promesa del PSet 1, etapa Datos).
-- Grano: un dia bursatil desde fecha_inicio.
--   miembros_composicion  acciones que la composicion historica pone en el indice ese dia
--   miembros_con_precio   de esas, cuantas tienen precio en Gold (universo realmente usable)
--   miembros_nyse         de las que tienen precio, cuantas estan hoy listadas en la NYSE
--   miembros_bolsa_desconocida  con precio pero sin bolsa conocida (ya no cotizan hoy)
--   pct_cobertura         100 * con_precio / composicion
{% set inicio = "cast('" ~ var('fecha_inicio') ~ "' as date)" %}

with cal as (
    select fecha from {{ ref('slv_calendario_nyse') }}
    where fecha >= {{ inicio }}
),
memb as (
    select * from {{ ref('slv_membresia_sp500') }}
),
esperado as (
    select c.fecha, count(distinct m.ticker) as miembros_composicion
    from cal as c
    inner join memb as m
        on c.fecha >= m.fecha_inicio
       and c.fecha <= coalesce(m.fecha_fin, cast('9999-12-31' as date))
    group by c.fecha
),
observado as (
    select f.fecha,
           count(*) as miembros_con_precio,
           sum(case when a.es_nyse then 1 else 0 end) as miembros_nyse,
           sum(case when a.codigo_bolsa is null then 1 else 0 end) as miembros_bolsa_desconocida
    from {{ ref('fct_precios_diarios') }} as p
    inner join {{ ref('dim_accion') }} as a on p.accion_key = a.accion_key
    inner join {{ ref('dim_fecha') }} as f on p.fecha_key = f.fecha_key
    where p.en_sp500
    group by f.fecha
)
select
    e.fecha,
    e.miembros_composicion,
    coalesce(o.miembros_con_precio, 0) as miembros_con_precio,
    e.miembros_composicion - coalesce(o.miembros_con_precio, 0) as miembros_sin_precio,
    coalesce(o.miembros_nyse, 0) as miembros_nyse,
    coalesce(o.miembros_bolsa_desconocida, 0) as miembros_bolsa_desconocida,
    round(100.0 * coalesce(o.miembros_con_precio, 0) / e.miembros_composicion, 4) as pct_cobertura
from esperado as e
left join observado as o on e.fecha = o.fecha
