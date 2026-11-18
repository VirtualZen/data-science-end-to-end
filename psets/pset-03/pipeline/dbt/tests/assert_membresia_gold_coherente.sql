-- Un FK existente no basta: debe pertenecer a la misma accion y cubrir la fecha.
-- Fuera de membresia se admite periodo_sp500_key NULL y en_sp500=false.
select p.accion_key, p.fecha_key, p.periodo_sp500_key
from {{ ref('fct_precios_diarios') }} p
left join {{ ref('dim_accion') }} a on p.accion_key = a.accion_key
left join {{ ref('dim_fecha') }} f on p.fecha_key = f.fecha_key
left join {{ ref('dim_membresia_sp500') }} m on p.periodo_sp500_key = m.periodo_key
where p.en_sp500 is null
   or p.en_sp500 <> (p.periodo_sp500_key is not null)
   or (p.periodo_sp500_key is not null and (
       m.periodo_key is null or a.accion_key is null or f.fecha_key is null
       or a.ticker <> m.ticker
       or f.fecha < m.fecha_inicio
       or f.fecha > coalesce(m.fecha_fin, cast('9999-12-31' as date))
   ))
