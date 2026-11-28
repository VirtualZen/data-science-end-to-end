-- Silver de precios de acciones: una fila por accion y dia bursatil de la NYSE, desde su
-- primera hasta su ultima cotizacion, con faltantes detectados e imputados.
--
-- 1. Deteccion: la grilla accion x calendario NYSE muestra los dias en que la accion
--    deberia tener precio. Falta un dia si no hay fila o si el precio no es valido (nulo,
--    no positivo o maximo < minimo).
-- 2. Imputacion (huecos de hasta max_hueco_imputable dias): forward-fill del log-precio
--    (cierre ajustado y apertura ajustada) con el ultimo dia observado, como fija el PSet 1
--    ("forward-fill, no usa el futuro"). El retorno del dia imputado es 0 y el movimiento
--    completo cae en el dia en que la accion vuelve a cotizar. El largo del hueco (que decide
--    imputar o excluir) si mira el siguiente dia observado: es una regla de calidad sobre que
--    tramos conservar, no un valor tomado del futuro.
-- 3. Huecos mas largos: no se imputan y esos dias no pasan a Silver; el retorno del dia
--    siguiente queda nulo, para no unir dos dias lejanos en un solo retorno.
-- 4. Banderas: imputado, retorno extremo (se marca, no se borra: puede ser real), cierre
--    fuera del rango del dia, volumen cero.
-- La apertura ajustada = apertura * cierre ajustado / cierre: Yahoo no ajusta la apertura
-- por splits ni dividendos. El maximo y el minimo se ajustan con el mismo factor (solo en
-- dias observados: un dia imputado no tiene rango).
-- 5. Diferencias diarias en tres formas (docs/series_de_tiempo.md):
--    aritmetica   dif_* = P(t) - P(t-1) en dolares ajustados (depende del nivel de precio)
--    porcentual   ret_pct_* = P(t) / P(t-1) - 1 = exp(ret_log_*) - 1 (geometrica, simple)
--    logaritmica  ret_log_* = ln P(t) - ln P(t-1) (aditiva en el tiempo)
--    y dentro del dia: intradia = cierre vs apertura, rango = maximo vs minimo.
with validos as (
    select
        p.ticker,
        p.fecha,
        p.precio_apertura,
        p.precio_maximo,
        p.precio_minimo,
        p.precio_cierre,
        p.precio_cierre_ajustado,
        p.precio_apertura * p.precio_cierre_ajustado / p.precio_cierre as precio_apertura_ajustado,
        p.volumen,
        p.lote_id,
        p.ingesta_ts
    from {{ ref('brz_precios_diarios') }} as p
    where not p.es_indice
      and p.precio_cierre_ajustado > 0
      and p.precio_cierre > 0
      and p.precio_apertura > 0
      and p.precio_maximo > 0
      and p.precio_minimo > 0
      and p.precio_maximo >= p.precio_minimo
),

vida as (
    select ticker, min(fecha) as primera, max(fecha) as ultima
    from validos
    group by ticker
),

grilla as (
    select v.ticker, c.fecha, c.orden_bursatil
    from vida as v
    inner join {{ ref('slv_calendario_nyse') }} as c
        on c.fecha between v.primera and v.ultima
),

con_obs as (
    select
        g.ticker,
        g.fecha,
        g.orden_bursatil,
        o.precio_apertura,
        o.precio_maximo,
        o.precio_minimo,
        o.precio_cierre,
        o.precio_cierre_ajustado,
        o.precio_maximo * o.precio_cierre_ajustado / o.precio_cierre as precio_maximo_ajustado,
        o.precio_minimo * o.precio_cierre_ajustado / o.precio_cierre as precio_minimo_ajustado,
        o.volumen,
        o.lote_id,
        o.ingesta_ts,
        ln(o.precio_cierre_ajustado)    as lp_cierre,
        ln(o.precio_apertura_ajustado)  as lp_apertura,
        case when o.ticker is not null then g.orden_bursatil end as orden_obs
    from grilla as g
    left join validos as o
        on g.ticker = o.ticker and g.fecha = o.fecha
),

grupos as (
    -- grupo_ant: cuantos dias observados hay hasta hoy (incluido); todos los dias de un
    -- hueco comparten el grupo del ultimo dia observado. grupo_sig: lo mismo hacia atras.
    select
        *,
        count(orden_obs) over (partition by ticker order by orden_bursatil
                               rows between unbounded preceding and current row) as grupo_ant,
        count(orden_obs) over (partition by ticker order by orden_bursatil desc
                               rows between unbounded preceding and current row) as grupo_sig
    from con_obs
),

vecinos as (
    select
        *,
        max(orden_obs)   over (partition by ticker, grupo_ant) as orden_ant,
        max(lp_cierre)   over (partition by ticker, grupo_ant) as lp_cierre_ant,
        max(lp_apertura) over (partition by ticker, grupo_ant) as lp_apertura_ant,
        -- Solo la posicion del siguiente dia observado (para medir el largo del hueco);
        -- su precio no se usa.
        min(orden_obs)   over (partition by ticker, grupo_sig) as orden_sig
    from grupos
),

imputada as (
    select
        *,
        orden_obs is null                                          as imputado,
        orden_sig - orden_ant - 1                                  as largo_hueco,
        case
            when orden_obs is not null then lp_cierre
            when orden_sig - orden_ant - 1 <= {{ var('max_hueco_imputable') }}
                then lp_cierre_ant
        end                                                        as lp_cierre_final,
        case
            when orden_obs is not null then lp_apertura
            when orden_sig - orden_ant - 1 <= {{ var('max_hueco_imputable') }}
                then lp_apertura_ant
        end                                                        as lp_apertura_final
    from vecinos
),

con_retornos as (
    select
        *,
        lp_cierre_final - lag(lp_cierre_final) over (partition by ticker order by orden_bursatil)   as ret_log_diario,
        lp_apertura_final - lag(lp_apertura_final) over (partition by ticker order by orden_bursatil) as ret_log_apertura,
        lp_apertura_final - lag(lp_cierre_final) over (partition by ticker order by orden_bursatil)   as ret_log_nocturno,
        lag(lp_cierre_final) over (partition by ticker order by orden_bursatil) is null
            and orden_bursatil > min(orden_bursatil) over (partition by ticker)                       as despues_de_tramo_excluido,
        exp(lp_cierre_final) - exp(lag(lp_cierre_final) over (partition by ticker order by orden_bursatil))     as dif_cierre_ajustado,
        exp(lp_apertura_final) - exp(lag(lp_apertura_final) over (partition by ticker order by orden_bursatil)) as dif_apertura_ajustada
    from imputada
)

select
    ticker,
    fecha,
    precio_apertura,
    precio_maximo,
    precio_minimo,
    precio_cierre,
    exp(lp_cierre_final)                                              as precio_cierre_ajustado,
    exp(lp_apertura_final)                                            as precio_apertura_ajustado,
    precio_maximo_ajustado,
    precio_minimo_ajustado,
    volumen,
    dif_cierre_ajustado,
    exp(ret_log_diario) - 1                                           as ret_pct_diario,
    ret_log_diario,
    dif_apertura_ajustada,
    exp(ret_log_apertura) - 1                                         as ret_pct_apertura,
    ret_log_apertura,
    exp(lp_cierre_final - lp_apertura_final) - 1                      as ret_pct_intradia,
    lp_cierre_final - lp_apertura_final                               as ret_log_intradia,
    exp(ret_log_nocturno) - 1                                         as ret_pct_nocturno,
    ret_log_nocturno,
    precio_maximo / precio_minimo - 1                                 as rango_pct_hl,
    ln(precio_maximo / precio_minimo)                                 as rango_log_hl,
    imputado,
    case when imputado then largo_hueco end                           as largo_hueco_imputado,
    despues_de_tramo_excluido,
    coalesce(abs(ret_log_diario) > {{ var('umbral_retorno_extremo') }}, false) as es_retorno_extremo,
    coalesce(precio_cierre > precio_maximo * 1.001 or precio_cierre < precio_minimo * 0.999, false)
                                                                      as cierre_fuera_de_rango,
    coalesce(volumen = 0, false)                                      as volumen_cero,
    lote_id,
    ingesta_ts
from con_retornos
where lp_cierre_final is not null
  and lp_apertura_final is not null
