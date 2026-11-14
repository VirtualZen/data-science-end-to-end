-- Dias bursatiles de la NYSE desde fecha_inicio: los dias con cierre del S&P 500.
-- Sirve para descartar fechas que no son de mercado (fines de semana, feriados) y para
-- detectar huecos en la serie de cada accion.
with dias as (
    select distinct fecha
    from {{ ref('brz_precios_diarios') }}
    where ticker = '{{ var("ticker_calendario") }}'
      and precio_cierre is not null
      and fecha >= cast('{{ var("fecha_inicio") }}' as date)
      and {{ dia_semana_iso('fecha') }} between 1 and 5
)

select
    fecha,
    row_number() over (order by fecha) as orden_bursatil
from dias
