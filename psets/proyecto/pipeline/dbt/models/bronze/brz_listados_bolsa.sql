-- Bronze de los listados de bolsa (rreichel3/US-Stock-Symbols, origen Nasdaq): ultima
-- carga, simbolo en formato Yahoo, nombre de la bolsa. Se descartan acciones preferentes
-- (BFH^A), warrants (.WS) y unidades, que no son acciones comunes.
-- ES_ETF/ES_PRUEBA no vienen en el JSON: desconocido permanece NULL, no false.
with ultima_carga as (
    select *
    from {{ source('raw', 'listados_bolsa') }}
    qualify dense_rank() over (order by ingesta_ts desc, lote_id desc) = 1
)

select
    upper(replace(replace(trim(simbolo), '.', '-'), '/', '-'))  as ticker,
    trim(simbolo)                                               as simbolo_original,
    trim(nombre)                                                as nombre,
    trim(codigo_bolsa)                                          as codigo_bolsa,
    case trim(codigo_bolsa)
        when 'N' then 'NYSE'
        when 'A' then 'NYSE American'
        when 'P' then 'NYSE Arca'
        when 'Z' then 'Cboe BZX'
        when 'V' then 'IEX'
        when 'Q' then 'Nasdaq'
    end                                                         as bolsa,
    case when trim(es_etf) in ('Y', 'N') then trim(es_etf) = 'Y' end                         as es_etf,
    case when trim(es_prueba) in ('Y', 'N') then trim(es_prueba) = 'Y' end                      as es_prueba,
    archivo,
    lote_id,
    cast(ingesta_ts as timestamp)                               as ingesta_ts
from ultima_carga
where simbolo is not null
  and simbolo not like 'File Creation Time%'
  and simbolo not like '%^%'
  and simbolo not like '%.WS%'
  and simbolo not like '%.U'
  and simbolo not like '%.R'
qualify row_number() over (
    partition by upper(replace(replace(trim(simbolo), '.', '-'), '/', '-'))
    order by archivo desc
) = 1
