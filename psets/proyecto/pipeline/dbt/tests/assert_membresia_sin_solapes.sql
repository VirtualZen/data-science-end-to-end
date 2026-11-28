-- Un ticker no puede tener dos periodos en el indice que se crucen: si los hubiera,
-- el join de fct_precios_diarios duplicaria filas.
select a.ticker, a.fecha_inicio, b.fecha_inicio as fecha_inicio_otro
from {{ ref('slv_membresia_sp500') }} as a
inner join {{ ref('slv_membresia_sp500') }} as b
    on a.ticker = b.ticker
   and a.periodo_key <> b.periodo_key
   and a.fecha_inicio <= coalesce(b.fecha_fin, cast('9999-12-31' as date))
   and b.fecha_inicio <= coalesce(a.fecha_fin, cast('9999-12-31' as date))
