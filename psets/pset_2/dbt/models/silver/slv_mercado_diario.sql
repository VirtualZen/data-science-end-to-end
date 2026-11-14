-- Silver de mercado: un dia bursatil por fila con el S&P 500 (^GSPC), el NYSE
-- Composite (^NYA) y la tasa de las letras del Tesoro a 13 semanas (^IRX, en % anual).
-- ^IRX no cotiza algunos dias en que la NYSE si abre (feriados de bonos): se rellena
-- con el ultimo valor conocido y se marca. Tasa libre de riesgo diaria = IRX/100/252.
with indices as (
    select ticker, fecha, precio_cierre, precio_cierre_ajustado
    from {{ ref('brz_precios_diarios') }}
    where es_indice
),

pivote as (
    select
        c.fecha,
        c.orden_bursatil,
        max(case when i.ticker = '{{ var("ticker_sp500") }}' then i.precio_cierre_ajustado end)          as cierre_sp500,
        max(case when i.ticker = '{{ var("ticker_nyse_composite") }}' then i.precio_cierre_ajustado end) as cierre_nyse_composite,
        max(case when i.ticker = '{{ var("ticker_tasa_libre_riesgo") }}' then i.precio_cierre end)       as tasa_irx_original
    from {{ ref('slv_calendario_nyse') }} as c
    left join indices as i
        on i.fecha = c.fecha
    group by c.fecha, c.orden_bursatil
),

con_grupo as (
    -- grupo = cuantos valores no nulos de IRX hay hasta el dia: todos los dias sin
    -- dato quedan en el grupo del ultimo dia con dato (relleno hacia adelante).
    select
        *,
        count(tasa_irx_original) over (order by fecha rows between unbounded preceding and current row) as grupo_irx
    from pivote
),

rellenado as (
    select
        *,
        max(tasa_irx_original) over (partition by grupo_irx) as tasa_irx_anual_pct
    from con_grupo
)

select
    fecha,
    cierre_sp500,
    cierre_nyse_composite,
    ln(cierre_sp500 / lag(cierre_sp500) over (order by fecha))                   as ret_log_sp500,
    ln(cierre_nyse_composite / lag(cierre_nyse_composite) over (order by fecha)) as ret_log_nyse_composite,
    tasa_irx_anual_pct,
    tasa_irx_original is null and tasa_irx_anual_pct is not null                 as tasa_irx_rellenada,
    tasa_irx_anual_pct / 100.0 / 252.0                                           as rf_diaria
from rellenado
