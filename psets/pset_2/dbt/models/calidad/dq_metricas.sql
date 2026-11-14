-- Metricas de calidad de datos, recalculadas en cada corrida. Son la evidencia de la
-- tabla Problema | Evidencia | Accion | Justificacion del memo (seccion 3).
-- Una fila por metrica: dimension (completitud, precision, consistencia, validez),
-- capa donde se mide, valor y unidad.
{% set inicio = "cast('" ~ var('fecha_inicio') ~ "' as date)" %}

with raw_precios as (
    select * from {{ source('raw', 'precios_diarios') }}
),
brz as (
    select * from {{ ref('brz_precios_diarios') }}
),
brz_acciones as (
    select * from brz where not es_indice
),
cal as (
    select * from {{ ref('slv_calendario_nyse') }}
),
memb as (
    select * from {{ ref('slv_membresia_sp500') }}
),
fotos as (
    select fecha_foto, count(*) as miembros
    from {{ ref('brz_composicion_sp500') }}
    where fecha_foto >= {{ inicio }}
    group by fecha_foto
),
-- Dias bursatiles en que cada accion era miembro del indice (lo esperado).
esperado as (
    select m.ticker, c.fecha
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
tickers_memb as (
    select distinct ticker from memb
    where coalesce(fecha_fin, cast('9999-12-31' as date)) >= {{ inicio }}
),
slv as (
    select * from {{ ref('slv_precios_acciones') }}
),
mercado as (
    select * from {{ ref('slv_mercado_diario') }}
),
comp_original as (
    select distinct ticker_original, ticker from {{ ref('brz_composicion_sp500') }}
),

metricas as (

    -- COMPLETITUD ---------------------------------------------------------------
    select 'completitud' as dimension, 'BRONZE/SILVER' as capa,
           'tickers_sp500_sin_precios_pct' as metrica,
           100.0 * sum(case when s.ticker is null then 1 else 0 end) / nullif(count(*), 0) as valor,
           '%' as unidad,
           'Acciones que estuvieron en el S&P 500 desde fecha_inicio y no tienen ningun precio (Yahoo no conserva muchas que dejaron de cotizar).' as descripcion
    from tickers_memb as t
    left join (select distinct ticker from slv) as s on t.ticker = s.ticker

    union all
    select 'completitud', 'GOLD', 'dias_miembro_sin_precio_pct',
           100.0 * (1 - (select count(*) from observado) * 1.0 / nullif((select count(*) from esperado), 0)),
           '%', 'Dias bursatiles en que una accion era miembro del indice pero no tiene precio en Gold.'
    from (select 1 as x) as uno

    union all
    select 'completitud', 'RAW', 'filas_cierre_ajustado_nulo_pct',
           100.0 * sum(case when adj_close is null then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Filas de RAW.PRECIOS_DIARIOS sin cierre ajustado.'
    from raw_precios

    union all
    select 'completitud', 'BRONZE', 'fotos_composicion_bajo_495_pct',
           100.0 * sum(case when miembros < 495 then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Fotos de la composicion (desde fecha_inicio) con menos de 495 simbolos: la fuente reconstruye mal los primeros anios.'
    from fotos

    union all
    select 'completitud', 'BRONZE', 'miembros_minimo_por_foto',
           min(miembros), 'acciones', 'Menor numero de simbolos en una foto de la composicion desde fecha_inicio.'
    from fotos

    union all
    select 'completitud', 'SILVER', 'dias_tasa_irx_rellenada_pct',
           100.0 * sum(case when tasa_irx_rellenada then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Dias bursatiles sin cotizacion de ^IRX, rellenados con el ultimo valor.'
    from mercado

    union all
    select 'completitud', 'SILVER', 'dias_con_hueco_previo_pct',
           100.0 * sum(case when hay_hueco_previo then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Filas cuya observacion anterior de la misma accion no es el dia bursatil previo (suspensiones o datos faltantes).'
    from slv

    -- PRECISION -----------------------------------------------------------------
    union all
    select 'precision', 'SILVER', 'retornos_extremos_pct',
           100.0 * sum(case when es_retorno_extremo then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Retornos log diarios con valor absoluto mayor al umbral (marcados, no eliminados).'
    from slv

    union all
    select 'precision', 'SILVER', 'retornos_extremos_filas',
           sum(case when es_retorno_extremo then 1 else 0 end), 'filas', 'Cantidad de retornos diarios extremos.'
    from slv

    union all
    select 'precision', 'SILVER', 'cierre_fuera_de_rango_pct',
           100.0 * sum(case when cierre_fuera_de_rango then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Filas con cierre fuera de [minimo, maximo] del dia (tolerancia 0,1%).'
    from slv

    union all
    select 'precision', 'SILVER', 'volumen_cero_pct',
           100.0 * sum(case when volumen_cero then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Dias con volumen cero (posible dia sin negociacion o dato faltante de Yahoo).'
    from slv

    -- CONSISTENCIA --------------------------------------------------------------
    union all
    select 'consistencia', 'RAW->BRONZE', 'filas_raw_duplicadas_pct',
           100.0 * (1 - (select count(*) from brz) * 1.0 / nullif(count(*), 0)),
           '%', 'Filas de RAW que repiten (ticker, fecha) por re-ingestas y backfill; Bronze conserva la carga mas reciente.'
    from raw_precios

    union all
    select 'consistencia', 'BRONZE', 'tickers_con_dos_formatos',
           count(distinct ticker), 'tickers', 'Acciones que la fuente de composicion escribe con punto y con guion (BRK.B y BRK-B).'
    from comp_original
    where ticker in (select ticker from comp_original where ticker_original like '%.%')
      and ticker in (select ticker from comp_original where ticker_original like '%-%')

    union all
    select 'consistencia', 'GOLD', 'acciones_sin_bolsa_pct',
           100.0 * sum(case when codigo_bolsa is null then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Acciones del universo sin bolsa conocida (ya no estan en los listados actuales).'
    from {{ ref('dim_accion') }}

    -- VALIDEZ -------------------------------------------------------------------
    union all
    select 'validez', 'BRONZE', 'filas_fuera_de_calendario_pct',
           100.0 * sum(case when c.fecha is null then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Filas de acciones (desde fecha_inicio) en dias que no son bursatiles en la NYSE; se descartan en Silver.'
    from brz_acciones as b
    left join cal as c on b.fecha = c.fecha
    where b.fecha >= {{ inicio }}

    union all
    select 'validez', 'BRONZE', 'filas_precio_invalido_pct',
           100.0 * sum(case when precio_cierre_ajustado is null or precio_cierre_ajustado <= 0
                             or precio_cierre is null or precio_cierre <= 0
                             or precio_maximo < precio_minimo then 1 else 0 end) / nullif(count(*), 0),
           '%', 'Filas con precio nulo, no positivo o maximo < minimo; se descartan en Silver.'
    from brz_acciones

    union all
    select 'validez', 'BRONZE', 'filas_fecha_futura',
           sum(case when fecha > current_date then 1 else 0 end), 'filas', 'Filas con fecha posterior a hoy.'
    from brz
)

select
    dimension,
    capa,
    metrica,
    cast(valor as double) as valor,
    unidad,
    descripcion,
    current_timestamp as calculado_en
from metricas
