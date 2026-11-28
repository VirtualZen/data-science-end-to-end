-- Las tres formas de la diferencia diaria describen el mismo movimiento:
--   ret_pct = exp(ret_log) - 1, dif = P(t-1) * ret_pct, ret_log_diario = nocturno + intradia,
--   y dentro del dia el rango contiene al cierre y a la apertura (rango >= |intradia|) en dias observados.
-- Devuelve las filas que no cumplen (tolerancia por redondeo).
select ticker, fecha
from {{ ref('slv_precios_acciones') }}
where abs(ret_pct_diario - (exp(ret_log_diario) - 1)) > 1e-9
   or abs(ret_pct_intradia - (exp(ret_log_intradia) - 1)) > 1e-9
   or abs(ret_log_diario - (ret_log_nocturno + ret_log_intradia)) > 1e-9
   or abs(dif_cierre_ajustado - (precio_cierre_ajustado - precio_cierre_ajustado / (1 + ret_pct_diario)))
      > 1e-6 * precio_cierre_ajustado
   or (not imputado and not cierre_fuera_de_rango
       and abs(ret_log_intradia) > rango_log_hl + 1e-3)
   or (imputado and (rango_log_hl is not null or precio_maximo_ajustado is not null))
