-- El calendario NYSE (seed) debe incluir todo dia en que el S&P 500 tiene cierre: si no,
-- el seed esta desactualizado o la fuente trae fechas que no son de mercado.
select p.fecha
from {{ ref('brz_precios_diarios') }} as p
left join {{ ref('calendario_nyse') }} as c on p.fecha = c.fecha
where p.ticker = '{{ var("ticker_calendario") }}'
  and p.fecha >= cast('{{ var("fecha_inicio") }}' as date)
  and c.fecha is null
