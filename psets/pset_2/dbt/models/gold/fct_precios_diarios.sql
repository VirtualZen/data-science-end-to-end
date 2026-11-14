-- Hecho principal. Grano: una accion en un dia bursatil de la NYSE.
-- en_sp500 indica si ese dia la accion pertenecia al indice (composicion historica),
-- para que el modelo solo elija entre las acciones que el asesor podia comprar.
select
    a.accion_key,
    f.fecha_key,
    p.precio_apertura,
    p.precio_maximo,
    p.precio_minimo,
    p.precio_cierre,
    p.precio_cierre_ajustado,
    p.volumen,
    p.ret_log_diario,
    m.periodo_key is not null      as en_sp500,
    m.periodo_key                  as periodo_sp500_key,
    p.hay_hueco_previo,
    p.dias_bursatiles_desde_anterior,
    p.es_retorno_extremo,
    p.cierre_fuera_de_rango,
    p.volumen_cero
from {{ ref('slv_precios_acciones') }} as p
inner join {{ ref('dim_accion') }} as a
    on p.ticker = a.ticker
inner join {{ ref('dim_fecha') }} as f
    on p.fecha = f.fecha
left join {{ ref('slv_membresia_sp500') }} as m
    on p.ticker = m.ticker
   and p.fecha >= m.fecha_inicio
   and p.fecha <= coalesce(m.fecha_fin, cast('9999-12-31' as date))
