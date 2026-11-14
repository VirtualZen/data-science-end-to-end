-- Regla del dominio: el S&P 500 tiene alrededor de 500 acciones (503 a 505 hoy, por
-- las clases dobles como BRK-B o GOOG/GOOGL). Una foto con menos de 440 o mas de 510
-- simbolos indica un archivo de composicion danado. Las fotos antiguas de la fuente
-- traen entre 444 y 499 (reconstruccion incompleta): por eso el piso es 440 y el
-- detalle queda en CALIDAD.dq_metricas.
select fecha_foto, count(*) as miembros
from {{ ref('brz_composicion_sp500') }}
where fecha_foto >= cast('{{ var("fecha_inicio") }}' as date)
group by fecha_foto
having count(*) < 440 or count(*) > 510
