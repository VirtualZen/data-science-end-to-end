-- Regla de evaluacion del PSet 1: nada posterior al corte puede quedar en
-- entrenamiento (fuga de informacion del futuro).
select fecha, conjunto
from {{ ref('dim_fecha') }}
where (fecha <= cast('{{ var("fecha_corte") }}' as date) and conjunto <> 'entrenamiento')
   or (fecha >  cast('{{ var("fecha_corte") }}' as date) and conjunto <> 'prueba')
