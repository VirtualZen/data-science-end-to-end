-- Vigencia, orden de fechas y solapes son reglas del negocio, no solo de tipos.
select a.periodo_key
from {{ ref('dim_membresia_sp500') }} a
where a.fecha_fin < a.fecha_inicio
   or a.vigente <> (a.fecha_fin is null)
   or a.huecos_unidos < 0
   or exists (
       select 1 from {{ ref('dim_membresia_sp500') }} b
       where a.ticker = b.ticker and a.periodo_key <> b.periodo_key
         and a.fecha_inicio <= coalesce(b.fecha_fin, cast('9999-12-31' as date))
         and b.fecha_inicio <= coalesce(a.fecha_fin, cast('9999-12-31' as date))
   )
