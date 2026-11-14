-- Periodos de pertenencia al S&P 500 por accion (islas de fotos consecutivas).
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
)

select
    i.ticker,
    i.fecha_inicio,
    case when f.siguiente_foto is not null
         then {{ dbt.dateadd('day', -1, 'f.siguiente_foto') }}
    end                                   as fecha_fin,
    f.siguiente_foto is null              as vigente,
    {{ llave(['i.ticker', 'i.fecha_inicio']) }} as periodo_key
from islas as i
inner join fotos as f
    on i.ultima_n_foto = f.n_foto
