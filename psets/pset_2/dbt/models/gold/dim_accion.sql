-- Dimension accion: una fila por accion que estuvo en el S&P 500 o tiene precios.
-- es_nyse viene del listado actual; las acciones que dejaron de cotizar no tienen
-- bolsa conocida (limitacion documentada en el memo).
select
    {{ llave(['ticker']) }}   as accion_key,
    ticker,
    nombre,
    codigo_bolsa,
    coalesce(bolsa, 'Desconocida (no listada hoy)') as bolsa,
    es_nyse,
    en_listado_actual,
    primera_fecha_sp500,
    ultima_fecha_sp500,
    sigue_en_sp500,
    periodos_en_sp500,
    primera_fecha_precio,
    ultima_fecha_precio,
    dias_con_precio,
    dias_con_precio > 0       as tiene_precios
from {{ ref('slv_acciones') }}
