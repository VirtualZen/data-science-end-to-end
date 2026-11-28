-- Las dos tablas de detalle deben sumar lo mismo y coincidir con la metrica agregada
-- dias_miembro_sin_precio_pct de dq_metricas (tolerancia 0,01 puntos porcentuales).
with por_ticker as (
    select sum(dias_miembro) as esperado, sum(dias_miembro_con_precio) as observado
    from {{ ref('dq_huecos_por_ticker') }}
),
por_fecha as (
    select sum(miembros_composicion) as esperado, sum(miembros_con_precio) as observado
    from {{ ref('dq_universo_por_fecha') }}
),
agregada as (
    select valor from {{ ref('dq_metricas') }} where metrica = 'dias_miembro_sin_precio_pct'
)
select t.esperado, f.esperado, t.observado, f.observado, a.valor
from por_ticker as t, por_fecha as f, agregada as a
where t.esperado <> f.esperado
   or t.observado <> f.observado
   or abs(100.0 * (1 - f.observado * 1.0 / f.esperado) - a.valor) > 0.01
