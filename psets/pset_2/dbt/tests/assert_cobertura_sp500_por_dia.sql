{{ config(severity='warn') }}
-- Advertencia (no error): dias en que menos de 400 acciones miembros del indice tienen
-- precio. Yahoo no conserva muchas acciones que dejaron de cotizar, asi que la
-- cobertura de los primeros anios es menor; CALIDAD.dq_metricas mide cuanto.
select f.fecha, sum(case when p.en_sp500 then 1 else 0 end) as miembros_con_precio
from {{ ref('fct_precios_diarios') }} as p
inner join {{ ref('dim_fecha') }} as f on p.fecha_key = f.fecha_key
group by f.fecha
having sum(case when p.en_sp500 then 1 else 0 end) < 400
