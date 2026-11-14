-- Todo retorno diario por encima del umbral debe llegar marcado a Gold, para que el
-- modelo pueda tratarlo (winsorizar o excluir) en vez de aprender de un error de dato.
select a.ticker, f.fecha, p.ret_log_diario
from {{ ref('fct_precios_diarios') }} as p
inner join {{ ref('dim_accion') }} as a on p.accion_key = a.accion_key
inner join {{ ref('dim_fecha') }} as f on p.fecha_key = f.fecha_key
where abs(p.ret_log_diario) > {{ var('umbral_retorno_extremo') }}
  and not p.es_retorno_extremo
