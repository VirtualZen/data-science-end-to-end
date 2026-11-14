-- Silver de precios de acciones: solo dias bursatiles, sin filas invalidas, con el
-- retorno logaritmico diario y banderas de calidad.
--   Se eliminan: precios nulos o no positivos y maximo < minimo (no se puede calcular
--   un retorno confiable con ellos).
--   Se marcan, sin eliminar: retornos extremos (pueden ser reales, como en marzo de
--   2020), cierre fuera del rango [minimo, maximo], volumen cero y huecos en la serie.
with precios as (
    select p.*, c.orden_bursatil
    from {{ ref('brz_precios_diarios') }} as p
    inner join {{ ref('slv_calendario_nyse') }} as c
        on p.fecha = c.fecha
    where not p.es_indice
),

validos as (
    select *
    from precios
    where precio_cierre_ajustado > 0
      and precio_cierre > 0
      and precio_maximo > 0
      and precio_minimo > 0
      and precio_maximo >= precio_minimo
),

con_retorno as (
    select
        *,
        lag(precio_cierre_ajustado) over (partition by ticker order by fecha) as cierre_ajustado_anterior,
        orden_bursatil - lag(orden_bursatil) over (partition by ticker order by fecha) as dias_bursatiles_desde_anterior
    from validos
)

select
    ticker,
    fecha,
    precio_apertura,
    precio_maximo,
    precio_minimo,
    precio_cierre,
    precio_cierre_ajustado,
    volumen,
    ln(precio_cierre_ajustado / cierre_ajustado_anterior)               as ret_log_diario,
    coalesce(dias_bursatiles_desde_anterior, 1)                         as dias_bursatiles_desde_anterior,
    coalesce(dias_bursatiles_desde_anterior, 1) > 1                     as hay_hueco_previo,
    coalesce(abs(ln(precio_cierre_ajustado / cierre_ajustado_anterior)) > {{ var('umbral_retorno_extremo') }}, false)
                                                                        as es_retorno_extremo,
    (precio_cierre > precio_maximo * 1.001 or precio_cierre < precio_minimo * 0.999)
                                                                        as cierre_fuera_de_rango,
    coalesce(volumen = 0, false)                                        as volumen_cero,
    lote_id,
    ingesta_ts
from con_retorno
