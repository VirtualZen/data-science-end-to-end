-- Bronze de la composicion: una fila por (fecha de la foto, ticker), de la carga mas
-- reciente del archivo. La fuente mezcla formatos (BRK.B y BRK-B para la misma accion):
-- se normaliza al formato de Yahoo (guion) y se guarda el original para auditar.
with ultima_carga as (
    select *
    from {{ source('raw', 'composicion_sp500') }}
    qualify dense_rank() over (order by ingesta_ts desc, lote_id desc) = 1
),

explotada as (
    {{ explotar_lista('ultima_carga', 'tickers') }}
)

select
    cast(fecha as date)                        as fecha_foto,
    upper(replace(valor, '.', '-'))            as ticker,
    valor                                      as ticker_original,
    lote_id,
    cast(ingesta_ts as timestamp)              as ingesta_ts
from explotada
where valor is not null and valor <> ''
qualify row_number() over (
    partition by cast(fecha as date), upper(replace(valor, '.', '-'))
    order by valor
) = 1
