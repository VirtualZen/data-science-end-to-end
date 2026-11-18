-- Hecho de mercado. Grano: un dia bursatil. Comparte dim_fecha con fct_precios_diarios
-- (dimension conformada): los referentes de la meta (S&P 500 y NYSE Composite) y la
-- tasa libre de riesgo del Sharpe.
select
    f.fecha_key,
    m.cierre_sp500,
    m.cierre_nyse_composite,
    m.ret_log_sp500,
    m.ret_log_nyse_composite,
    m.tasa_irx_anual_pct,
    m.tasa_irx_rellenada,
    m.rf_diaria
from {{ ref('slv_mercado_diario') }} as m
inner join {{ ref('dim_fecha') }} as f
    on m.fecha = f.fecha
