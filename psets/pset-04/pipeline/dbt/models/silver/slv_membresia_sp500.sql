-- Periodos de pertenencia al S&P 500 por empresa (islas de fotos consecutivas). La
-- empresa se identifica por su simbolo actual de Yahoo (brz_composicion_sp500.ticker), asi
-- que un cambio de simbolo (FB -> META) no corta la pertenencia.
-- Una accion es miembro desde la foto en que aparece hasta el dia anterior a la
-- primera foto en que ya no aparece. Si sigue en la ultima foto, fecha_fin es nula.
-- Usar la composicion de cada fecha (y no la actual) evita el sesgo de supervivencia.
with fotos as (
    select
        fecha_foto,
        row_number() over (order by fecha_foto) as n_foto,
        lead(fecha_foto) over (order by fecha_foto) as siguiente_foto
    from (select distinct fecha_foto from {{ ref('brz_composicion_sp500') }}) as f
),

presencia as (
    select
        b.ticker,
        f.fecha_foto,
        f.n_foto,
        f.siguiente_foto,
        f.n_foto - row_number() over (partition by b.ticker order by f.n_foto) as isla
    from {{ ref('brz_composicion_sp500') }} as b
    inner join fotos as f
        on b.fecha_foto = f.fecha_foto
),

islas as (
    select
        ticker,
        isla,
        min(fecha_foto) as fecha_inicio,
        max(n_foto) as ultima_n_foto
    from presencia
    group by ticker, isla
),

periodos as (
    select
        i.ticker,
        i.fecha_inicio,
        case when f.siguiente_foto is not null
             then {{ dbt.dateadd('day', -1, 'f.siguiente_foto') }}
        end                                   as fecha_fin,
        f.siguiente_foto is null              as vigente
    from islas as i
    inner join fotos as f
        on i.ultima_n_foto = f.n_foto
),

-- La fuente tiene fotos sueltas en las que falta una empresa uno o dos dias (por ejemplo
-- el dia del cambio FLT -> CPAY). Dos periodos separados por menos de
-- tolerancia_hueco_membresia_dias se unen en uno; el detalle queda en CALIDAD.
con_corte as (
    select
        *,
        case when {{ dbt.datediff('lag(fecha_fin) over (partition by ticker order by fecha_inicio)', 'fecha_inicio', 'day') }}
                  <= {{ var('tolerancia_hueco_membresia_dias') }} + 1
             then 0 else 1 end as nuevo_periodo
    from periodos
),

numerados as (
    select *, sum(nuevo_periodo) over (partition by ticker order by fecha_inicio
                                       rows between unbounded preceding and current row) as n_periodo
    from con_corte
)

select
    ticker,
    min(fecha_inicio)                                         as fecha_inicio,
    case when max(case when vigente then 1 else 0 end) = 1 then null
         else max(fecha_fin) end                              as fecha_fin,
    max(case when vigente then 1 else 0 end) = 1              as vigente,
    count(*) - 1                                              as huecos_unidos,
    {{ llave(['ticker', 'min(fecha_inicio)']) }}              as periodo_key
from numerados
group by ticker, n_periodo
