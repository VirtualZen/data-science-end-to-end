-- Bronze (staging) de precios: tipos explicitos, simbolos normalizados y una sola fila
-- por (ticker, fecha). Raw es append-only y el backfill o la ventana de revision del
-- flow diario cargan la misma fecha varias veces: se conserva la carga mas reciente,
-- porque Yahoo corrige cierres y ajustes despues del dia.
with origen as (
    select * from {{ source('raw', 'precios_diarios') }}
)

select
    upper(trim(ticker))                     as ticker,
    cast(fecha as date)                     as fecha,
    cast(open as double)                    as precio_apertura,
    cast(high as double)                    as precio_maximo,
    cast(low as double)                     as precio_minimo,
    cast(close as double)                   as precio_cierre,
    cast(adj_close as double)               as precio_cierre_ajustado,
    cast(volume as double)                  as volumen,
    upper(trim(ticker)) like '^%'           as es_indice,
    lote_id,
    cast(ingesta_ts as timestamp)           as ingesta_ts
from origen
where ticker is not null
  and fecha is not null
qualify row_number() over (
    partition by upper(trim(ticker)), cast(fecha as date)
    order by ingesta_ts desc, lote_id desc
) = 1
