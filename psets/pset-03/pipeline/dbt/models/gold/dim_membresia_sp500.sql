-- Dimension historica de membresia. Grano: un intervalo continuo por simbolo.
-- Publica en Gold los intervalos ya resueltos en Silver; no vuelve a imputarlos.
-- fecha_fin NULL representa vigencia abierta, no un dato que deba rellenarse.
select
    periodo_key,
    ticker,
    fecha_inicio,
    fecha_fin,
    vigente,
    huecos_unidos
from {{ ref('slv_membresia_sp500') }}
