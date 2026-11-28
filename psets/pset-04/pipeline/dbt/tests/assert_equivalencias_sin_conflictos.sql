-- Un simbolo antiguo no puede traducirse a dos simbolos actuales en la misma fecha.
select ticker_antiguo, valido_hasta, count(distinct ticker_yahoo) as destinos
from {{ ref('equivalencias_tickers') }}
group by ticker_antiguo, valido_hasta
having count(distinct ticker_yahoo) > 1
