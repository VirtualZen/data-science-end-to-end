-- Bronze (staging) de la composicion: una fila por (fecha de la foto, empresa), de la
-- carga mas reciente del archivo.
--   1. Formatos: la fuente mezcla BRK.B y BRK-B; se normaliza al formato de Yahoo (guion).
--   2. Cambios de simbolo: la foto usa el simbolo que tenia la empresa ese dia (FB en
--      2020), pero Yahoo guarda toda la historia bajo el simbolo actual (META). Con el seed
--      equivalencias_tickers, cada simbolo antiguo se traduce al actual solo en las fotos
--      anteriores a la fecha del cambio (despues, el simbolo viejo puede ser de otra empresa).
-- ticker = simbolo de Yahoo (la empresa); ticker_composicion = como lo escribe la fuente.
with ultima_carga as (
    select *
    from {{ source('raw', 'composicion_sp500') }}
    qualify dense_rank() over (order by ingesta_ts desc, lote_id desc) = 1
),

explotada as (
    {{ explotar_lista('ultima_carga', 'tickers') }}
),

normalizada as (
    select
        cast(fecha as date)                                       as fecha_foto,
        upper(replace(replace(valor, '.', '-'), '/', '-'))       as ticker_composicion,
        valor                                                     as ticker_original,
        lote_id,
        cast(ingesta_ts as timestamp)                             as ingesta_ts
    from explotada
    where valor is not null and valor <> ''
)

select
    n.fecha_foto,
    coalesce(e.ticker_yahoo, n.ticker_composicion)   as ticker,
    n.ticker_composicion,
    n.ticker_original,
    e.ticker_yahoo is not null                       as simbolo_traducido,
    n.lote_id,
    n.ingesta_ts
from normalizada as n
left join {{ ref('equivalencias_tickers') }} as e
    on n.ticker_composicion = e.ticker_antiguo
   and n.fecha_foto < e.valido_hasta
qualify row_number() over (
    partition by n.fecha_foto, coalesce(e.ticker_yahoo, n.ticker_composicion)
    order by case when e.ticker_yahoo is null then 0 else 1 end, n.ticker_original
) = 1
