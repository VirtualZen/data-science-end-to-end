{#
  Macros propias del proyecto. Las que cambian segun la base de datos usan
  adapter.dispatch: la version default es la de Snowflake (destino del PSet) y la de
  duckdb existe solo para probar el codigo localmente sin cuenta de Snowflake.
#}

{# Usa el nombre de esquema tal cual (BRONZE, SILVER, GOLD) en vez de GOLD_BRONZE. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}


{# Una fila por elemento de una lista separada por comas: devuelve c.* y "valor". #}
{% macro explotar_lista(relacion, columna) -%}
    {{ return(adapter.dispatch('explotar_lista', 'portafolio')(relacion, columna)) }}
{%- endmacro %}

{% macro default__explotar_lista(relacion, columna) -%}
    select c.*, trim(s.value::varchar) as valor
    from {{ relacion }} as c,
         lateral split_to_table(c.{{ columna }}, ',') as s
{%- endmacro %}

{% macro duckdb__explotar_lista(relacion, columna) -%}
    select c.*, trim(unnest(string_split(c.{{ columna }}, ','))) as valor
    from {{ relacion }} as c
{%- endmacro %}


{# Dia de la semana ISO: 1 = lunes ... 7 = domingo. #}
{% macro dia_semana_iso(columna) -%}
    {{ return(adapter.dispatch('dia_semana_iso', 'portafolio')(columna)) }}
{%- endmacro %}

{% macro default__dia_semana_iso(columna) -%} dayofweekiso({{ columna }}) {%- endmacro %}
{% macro duckdb__dia_semana_iso(columna) -%} isodow({{ columna }}) {%- endmacro %}


{# Llave sustituta estable a partir de una o varias columnas. #}
{% macro llave(columnas) -%}
    md5(
    {%- for c in columnas -%}
        coalesce(cast({{ c }} as varchar), '~'){% if not loop.last %} || '|' || {% endif %}
    {%- endfor -%}
    )
{%- endmacro %}


{# Fecha (DATE) a entero AAAAMMDD, la llave de dim_fecha. #}
{% macro fecha_a_llave(columna) -%}
    cast(extract(year from {{ columna }}) * 10000 + extract(month from {{ columna }}) * 100 + extract(day from {{ columna }}) as integer)
{%- endmacro %}
