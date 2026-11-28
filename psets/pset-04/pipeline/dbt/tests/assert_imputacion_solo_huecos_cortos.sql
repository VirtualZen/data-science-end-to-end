-- Regla de limpieza: solo se imputan huecos de hasta max_hueco_imputable dias bursatiles.
select ticker, fecha, largo_hueco_imputado
from {{ ref('slv_precios_acciones') }}
where imputado
  and (largo_hueco_imputado is null or largo_hueco_imputado > {{ var('max_hueco_imputable') }})
