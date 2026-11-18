{# Falla si algun valor no nulo queda fuera de [minimo, maximo]. #}
{% test rango_valores(model, column_name, minimo=none, maximo=none) %}
select {{ column_name }} as valor_fuera_de_rango
from {{ model }}
where {{ column_name }} is not null
  and (
      {% if minimo is not none %}{{ column_name }} < {{ minimo }}{% else %}false{% endif %}
      or
      {% if maximo is not none %}{{ column_name }} > {{ maximo }}{% else %}false{% endif %}
  )
{% endtest %}


{# Falla si la combinacion de columnas se repite (grano de la tabla). #}
{% test combinacion_unica(model, columnas) %}
select {{ columnas | join(', ') }}, count(*) as repeticiones
from {{ model }}
group by {{ columnas | join(', ') }}
having count(*) > 1
{% endtest %}
