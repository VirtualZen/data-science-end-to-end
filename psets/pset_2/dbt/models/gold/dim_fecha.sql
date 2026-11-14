-- Dimension fecha: un dia bursatil de la NYSE por fila.
-- es_cierre_de_mes marca el ultimo dia bursatil de cada mes cerrado: es el dia en que
-- el asesor rebalancea y el grano mensual de la OBT. El mes en curso no esta cerrado.
-- conjunto separa entrenamiento y prueba segun el corte del PSet 1 (sujeto a cambios).
with base as (
    select
        fecha,
        orden_bursatil,
        cast(extract(year from fecha) as integer)                                   as anio,
        cast(extract(month from fecha) as integer)                                  as mes,
        cast(extract(quarter from fecha) as integer)                                as trimestre,
        cast(extract(year from fecha) * 100 + extract(month from fecha) as integer) as anio_mes,
        cast({{ dia_semana_iso('fecha') }} as integer)                              as dia_semana_iso
    from {{ ref('slv_calendario_nyse') }}
)

select
    {{ fecha_a_llave('fecha') }}                                          as fecha_key,
    fecha,
    orden_bursatil,
    anio,
    trimestre,
    mes,
    anio_mes,
    dia_semana_iso,
    row_number() over (partition by anio_mes order by fecha)             as dia_bursatil_del_mes,
    count(*) over (partition by anio_mes)                                as dias_bursatiles_del_mes,
    anio_mes < max(anio_mes) over ()                                     as mes_cerrado,
    (fecha = max(fecha) over (partition by anio_mes)
        and anio_mes < max(anio_mes) over ())                            as es_cierre_de_mes,
    case when fecha <= cast('{{ var("fecha_corte") }}' as date)
         then 'entrenamiento' else 'prueba' end                          as conjunto
from base
