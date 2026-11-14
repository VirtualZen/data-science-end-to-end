-- Bronze de los listados de Nasdaq Trader: ultima carga, sin la fila de pie
-- ("File Creation Time: ..."), simbolo en formato Yahoo y nombre de la bolsa.
with ultima_carga as (
    select *
    from {{ source('raw', 'listados_bolsa') }}
    qualify dense_rank() over (order by ingesta_ts desc, lote_id desc) = 1
)

select
    upper(replace(trim(simbolo), '.', '-'))      as ticker,
    trim(simbolo)                                as simbolo_original,
    trim(nombre)                                 as nombre,
    trim(codigo_bolsa)                           as codigo_bolsa,
    case trim(codigo_bolsa)
        when 'N' then 'NYSE'
        when 'A' then 'NYSE American'
        when 'P' then 'NYSE Arca'
        when 'Z' then 'Cboe BZX'
        when 'V' then 'IEX'
        when 'Q' then 'Nasdaq'
    end                                          as bolsa,
    coalesce(trim(es_etf) = 'Y', false)          as es_etf,
    coalesce(trim(es_prueba) = 'Y', false)       as es_prueba,
    archivo,
    lote_id,
    cast(ingesta_ts as timestamp)                as ingesta_ts
from ultima_carga
where simbolo is not null
  and simbolo not like 'File Creation Time%'
qualify row_number() over (
    partition by upper(replace(trim(simbolo), '.', '-'))
    order by archivo desc
) = 1
