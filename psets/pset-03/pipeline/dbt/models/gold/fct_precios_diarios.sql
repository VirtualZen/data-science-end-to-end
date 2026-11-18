-- Hecho principal. Grano: una accion (empresa, por su simbolo actual) en un dia bursatil
-- de la NYSE, desde su primera hasta su ultima cotizacion.
-- en_sp500 indica si ese dia la empresa pertenecia al indice (composicion historica),
-- para que el modelo solo elija entre las acciones que el asesor podia comprar.
-- imputado marca los dias rellenados en Silver (huecos de hasta 5 dias).
select
    a.accion_key,
    f.fecha_key,
    p.precio_apertura,
    p.precio_maximo,
    p.precio_minimo,
    p.precio_cierre,
    p.precio_cierre_ajustado,
    p.precio_apertura_ajustado,
    p.precio_maximo_ajustado,
    p.precio_minimo_ajustado,
    p.volumen,
    p.dif_cierre_ajustado,
    p.ret_pct_diario,
    p.ret_log_diario,
    p.dif_apertura_ajustada,
    p.ret_pct_apertura,
    p.ret_log_apertura,
    p.ret_pct_intradia,
    p.ret_log_intradia,
    p.ret_pct_nocturno,
    p.ret_log_nocturno,
    p.rango_pct_hl,
    p.rango_log_hl,
    m.periodo_key is not null      as en_sp500,
    m.periodo_key                  as periodo_sp500_key,
    p.imputado,
    p.largo_hueco_imputado,
    p.despues_de_tramo_excluido,
    p.es_retorno_extremo,
    p.cierre_fuera_de_rango,
    p.volumen_cero
from {{ ref('slv_precios_acciones') }} as p
inner join {{ ref('dim_accion') }} as a
    on p.ticker = a.ticker
inner join {{ ref('dim_fecha') }} as f
    on p.fecha = f.fecha
left join {{ ref('dim_membresia_sp500') }} as m
    on p.ticker = m.ticker
   and p.fecha >= m.fecha_inicio
   and p.fecha <= coalesce(m.fecha_fin, cast('9999-12-31' as date))
