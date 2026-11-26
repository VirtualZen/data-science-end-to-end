# Semana 14, Sesión 2: Comunicación técnica y ejecutiva de los resultados

> Objetivo de la sesión: adaptar la presentación de los resultados y limitaciones de tu proyecto a una audiencia técnica y a una audiencia ejecutiva.

**Lectura previa de esta sesión:** ["How to Effectively Communicate Results to Stakeholders As a Data Scientist"](https://medium.com/@sahin.samia/how-to-effectively-communicate-results-to-stakeholders-as-a-data-scientist-711e88dd464f), Sahin Samia.

**Referencia de esta sesión:** *Designing Machine Learning Systems*, Cap. 11: The Human Side of Machine Learning.

## Requisitos antes de esta sesión

Nada nuevo que instalar. Hoy se escribe más de lo que se programa: los dos scripts preparan los números y los gráficos, y el trabajo es decidir qué se dice a quién.

### Cómo correrlo localmente con uv

`starter/` es un proyecto uv (Python 3.11, versiones del `requirements.txt` del curso). Desde `laboratorios/semana-14-sesion-02/starter/`:

```bash
uv sync
cd ejercicio1 && uv run --project .. python graficos_tarifa.py && cd ..
cd ejercicio2 && uv run --project .. python comprobar.py && uv run --project .. python costos_fraude.py && cd ..
```

El Ejercicio 1 deja `grafico_tecnico.png` y `grafico_ejecutivo.png` en `ejercicio1/`; el Ejercicio 2 imprime los cinco pasos de `comprobar.py` y el costo del fraude.

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿qué hay que saber de la audiencia antes de preparar la presentación? ¿Qué recomienda hacer con la jerga técnica?**

_(tu respuesta)_

**¿Qué lugar le da el artículo a las limitaciones y a la incertidumbre de los resultados?**

_(tu respuesta)_

## Pregunta de apertura

¿Qué cambia entre explicarle tu proyecto a otro científico de datos y a quien paga la factura? Escribe la primera oración que le dirías a cada uno.

_(la primera oración para un científico de datos)_

_(la primera oración para quien paga)_

## Ejercicio 1: noviembre, para dos audiencias

Carpeta: [`starter/ejercicio1/`](./starter/ejercicio1/). [`tarifas_noviembre.csv`](./starter/ejercicio1/tarifas_noviembre.csv) tiene los 1156 viajes de noviembre del monitoreo de la Semana 13: la tarifa estimada por la versión 1, la cobrada y si el viaje tenía tarifa fija. [`graficos_tarifa.py`](./starter/ejercicio1/graficos_tarifa.py) calcula el resumen por semana y dibuja dos gráficos con los mismos datos, `grafico_tecnico.png` y `grafico_ejecutivo.png`. Los 3 `TODO`: el resumen, el gráfico técnico y el gráfico ejecutivo.

```
python graficos_tarifa.py
```

**Respuesta 1 (TODO 1):** el MAE pasó de 1.18 a 4.29. Antes de calcularlo: ¿qué número de la tabla le dirías a la gerente de operaciones, que nunca oyó hablar del MAE?

Los pasajeros que pagan más de 20% sobre lo estimado: de 3% a 47%.

**Respuesta 2 (TODO 2 y 3):** los dos gráficos usan los mismos viajes. Haz una lista de todo lo que cambia entre uno y otro: la métrica, el título, la cantidad de series, los colores.

Métrica: MAE en dólares → % de pasajeros. Título: la métrica → la conclusión. Series: dos más la referencia → una. Colores: azules por tipo → gris y rojo para resaltar. El ejecutivo muestra el valor en cada barra y no tiene leyenda.

**Respuesta 3:** escribe las dos diapositivas. Cada una tiene un título que es una oración completa, el gráfico y como máximo cuatro líneas.

**Diapositiva técnica** (para el equipo de datos):

**Desde el 16/11, el MAE con taxímetro se triplicó y el de tarifa fija no cambió.**

- MAE semanal de la versión 1 contra la tarifa cobrada, 1156 viajes.
- Taxímetro: 1.30 → 4.75; el modelo subestima 4.23 dólares por viaje.
- Deriva conceptual: cambió la tarifa, no los viajes.
- Limitación: la semana del 23 está incompleta.

**Diapositiva ejecutiva** (para la gerente de operaciones):

**Desde el 16 de noviembre, casi la mitad de los pasajeros paga más de 20% sobre lo estimado.**

- Antes, 3 de cada 100; ahora, 47.
- Cada viaje cuesta 4 dólares más de lo estimado.
- Recomendamos reentrenar el modelo con las tarifas nuevas.
- Necesitamos confirmar con la ciudad la fecha y el monto del aumento.

## Durante el ConcepTest

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Ejercicio 2: el fraude, en dólares

Solo o en pareja. Carpeta: [`starter/ejercicio2/`](./starter/ejercicio2/). El reporte técnico de la Semana 13 decía que el recall de la semana del 16 cayó de 0.74 a 0.28. [`costos_fraude.py`](./starter/ejercicio2/costos_fraude.py) lo traduce a dólares con los costos de la Semana 11 (40 por fraude no detectado, 3 por revisar un pago legítimo). Los pasos 1 a 3 tienen `TODO`: los errores por semana, su costo y el costo de una semana normal. Los pasos 4 (la oración para la gerencia) y 5 (lo que cuesta un mes así) solo tienen un comentario. Resuelve y corre `python comprobar.py` hasta que los cinco pasos digan `OK`; después, `python costos_fraude.py`.

**Respuesta 1:** ¿qué oración te dio el paso 4? ¿Qué le falta para que la gerente pueda decidir algo?

"La semana del 2026-11-16, el fraude que no detectamos y las revisiones costaron 2359 dolares, 2.7 veces una semana normal." Le falta la causa y qué hacer.

**Respuesta 2:** escribe el mensaje ejecutivo completo, en cinco oraciones como máximo: qué pasó, cuánto cuesta, qué recomiendan, qué necesitan y qué riesgo queda.

Desde el 16 de noviembre el modelo detecta 28 de cada 100 fraudes, antes 74. Esa semana costó 2359 dólares, 2.7 veces lo normal; un mes así, 6000 más. Recomendamos reentrenarlo con los fraudes de noviembre y, mientras tanto, revisar más pagos. Necesitamos los contracargos de noviembre y una semana del equipo. El riesgo: la semana del 23 muestra la misma señal.

**Respuesta 3:** el costo de 40 dólares por fraude no detectado es una suposición de la Semana 11. ¿Dónde lo dirías, en el mensaje ejecutivo o en el técnico? ¿Qué pasa con tu recomendación si el costo real fuera la mitad?

En el técnico. Con la mitad, la semana costaría 1259 dólares (2.5 veces lo normal) y la recomendación no cambia.

## Ejercicio 3: los resultados de tu proyecto, dos veces

Usa tu proyecto en [`psets/proyecto/`](../../psets/README.md). Esta vez no hay plantilla.

### Entregable 1: `docs/resultados_tecnico.pdf`

Una diapositiva para otra persona del equipo de datos: el modelo y la línea base, la métrica de la Semana 11 con su esquema de validación, lo que mostró el monitoreo y las limitaciones, con los números.

### Entregable 2: `docs/resultados_ejecutivo.pdf`

La misma diapositiva para quien decide si se usa el modelo: un título que dice la conclusión, el resultado en la unidad de quien decide (dinero, tiempo, casos), qué recomiendan, qué necesitan y qué no hace el modelo. Sin el nombre del algoritmo ni de la métrica.

Puedes armar las dos diapositivas en lo que prefieras (Google Slides, PowerPoint, Markdown exportado) y guardarlas en PDF.

**¿Qué número de tu proyecto usaste en la versión ejecutiva que no aparece en la técnica? ¿De dónde salió?**

_(tu respuesta)_

**¿Qué limitación dejaste en las dos versiones, y cómo la dijiste en cada una?**

_(tu respuesta)_

## Antes de la próxima sesión

**Lectura:** ["AI Model Lifecycle Management: From Development to Decommissioning"](https://blog.cognitiveview.com/ai-model-lifecycle-management-from-development-to-decommissioning/), CognitiveView.

Hoy escribiste "qué no hace el modelo" en una diapositiva. Ahora imagina que sí lo hace mal: ¿bajo qué condición apagarías el modelo de tu proyecto, y quién tendría que enterarse?

_(tu respuesta)_
