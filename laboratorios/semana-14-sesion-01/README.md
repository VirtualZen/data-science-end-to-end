# Semana 14, Sesión 1: Monitoreo en producción II: deriva de datos y deriva conceptual

> Objetivo de la sesión: distinguir deriva de datos de deriva conceptual en el modelo de tu proyecto, y diseñar una alerta que detecte cuál de las dos lo está degradando.

**Lectura previa de esta sesión:** ["Data Drift vs. Concept Drift and Why Monitoring for Them is Important"](https://medium.com/whylabs/data-drift-vs-concept-drift-and-why-monitoring-for-them-is-important-a68c08b141f0), WhyLabs.

**Referencia de esta sesión:** *Designing Machine Learning Systems*, Cap. 9: Continual Learning and Test in Production.

## Requisitos antes de esta sesión

Nada nuevo que instalar. El Ejercicio 1 es un notebook (simula la deriva y elige el umbral); el Ejercicio 2, un script del servicio (la alerta queda ahí, corriendo con cada predicción).

## Antes de empezar

A partir de la lectura previa:

**Según el artículo, ¿qué es la deriva de datos y qué es la deriva conceptual? Da un ejemplo de cada una.**

Deriva de datos: cambian las entradas, pero no su relación con el objetivo. Ejemplo: un modelo de ventas entrenado en temporada navideña y usado el resto del año. Deriva conceptual: cambia la relación entre las entradas y el objetivo, aunque las entradas sigan iguales. Ejemplo: una campaña de marketing nueva cambia cómo se comportan los clientes ante el churn.

**¿Por qué el artículo dice que hay que monitorear las dos, y no solo el desempeño del modelo?**

Porque el modelo debe seguir siendo preciso y confiable para decidir con él: detectar la deriva a tiempo permite corregirlo, evita sesgos contra ciertos grupos y es un requisito en industrias reguladas (salud, finanzas). Además, la deriva conceptual no se ve en las entradas, solo en el desempeño.

## Pregunta de apertura

Desde el 16 de noviembre, el modelo de la tarifa se equivoca casi cuatro veces más que en prueba. Los viajes que recibe son del mismo tipo que los de octubre: las mismas zonas, las mismas distancias, las mismas horas. ¿Qué cambió, entonces? ¿Lo hubieras detectado mirando solo los viajes que llegan?

Cambió la relación entre el viaje y su tarifa (por ejemplo, un aumento de la tarifa por taxímetro): es deriva conceptual. No se detecta mirando los viajes, porque son iguales a los de octubre; solo aparece al comparar la tarifa estimada con la cobrada.

## Ejercicio 1: ¿deriva de datos o deriva conceptual?

Carpeta: [`starter/ejercicio1/`](./starter/ejercicio1/). [`ejercicio1_deriva.ipynb`](./starter/ejercicio1/ejercicio1_deriva.ipynb) entrena la versión 1 del modelo de la tarifa y simula semanas de 300 viajes: semanas normales, semanas de feriado con más viajes al aeropuerto (deriva de datos) y semanas con un aumento de la tarifa por taxímetro (deriva conceptual). Para cada una mide el PSI de dos features contra los viajes de entrenamiento y el MAE del modelo. Los 4 `TODO`: la fórmula del PSI, medir 200 semanas normales, y las dos derivas simuladas.

Corre todas las celdas antes de tocar nada (**Run All**).

**Respuesta 1 (TODO 1 y 2):** antes de medir las semanas normales, ¿qué PSI esperas para una semana en la que nada cambió? Después de medirlas: ¿cuál fue el máximo en 200 semanas?

Cercano a 0, pero no 0: 300 viajes al azar nunca se reparten igual que los de entrenamiento. El máximo en 200 semanas fue **0.121** en distancia y **0.109** en zona.

**Respuesta 2 (TODO 3 y 4):** antes de correr, ¿qué esperas que pase con el PSI y con el MAE en la semana de feriado? ¿Y en la semana del aumento?

Feriado: PSI alto y MAE casi igual; aumento: PSI normal y MAE mucho peor. Así fue: el feriado dio un PSI de 0.19 y un MAE de 0.97, y el aumento un PSI de 0.08 y un MAE de 4.16 (3.6 veces el de prueba).

**Respuesta 3 (Paso 4):** en la semana de feriado con peso 8, el PSI es más de diez veces el de una semana normal. ¿Empeoró el modelo? ¿Por qué?

No: el MAE bajó de 1.19 a 0.94. Los viajes al aeropuerto son los más fáciles de predecir (78% con tarifa fija, MAE de 0.62), así que más de ellos baja el error. Un PSI alto dice que cambiaron los datos, no que empeoró el modelo.

**Respuesta 4 (Paso 5):** ¿qué umbral de PSI elegirías para la alerta, y con qué dos números de la tabla lo justificas?

**0.15**: 0% de falsas alarmas y 97.5% de detección del feriado. Con 0.10 las falsas alarmas suben a 4%, y con 0.20 la detección baja a 71.5%.

**Lo que mostró la simulación:**

| Escenario | PSI de distancia | PSI de zona | MAE |
|---|---|---|---|
| Semanas normales (máximo de 200) | 0.1214 | 0.1091 | 1.3164 |
| Feriado, aeropuerto ×4 | 0.1887 | 0.1964 | 0.9694 |
| Aumento de 20% | 0.0767 | 0.0615 | 4.1638 |

## Durante el ConcepTest

**Tu voto, antes de discutir en pareja** (A, B, C o D):

_(tu voto)_

**Tu razonamiento:**

_(tu respuesta)_

**Después de discutir en pareja, ¿cambiaste de voto? ¿Por qué?**

_(tu respuesta)_

## Ejercicio 2: la alerta, en el servicio

Solo o en pareja. Carpeta: [`starter/ejercicio2/`](./starter/ejercicio2/). El servicio de la tarifa de la sesión pasada tiene ahora una ruta `/deriva`. [`deriva.py`](./starter/ejercicio2/deriva.py) trae `MonitorDeDeriva`: guarda los últimos 300 viajes que recibió el servicio y calcula el PSI de `distancia_km` y de `zona_origen` contra la referencia que guarda `entrenar.py` (`referencia_deriva.json`), con el umbral de 0.15. Los pasos 1 a 3 tienen `TODO` (las proporciones numéricas, las categóricas y el PSI); los pasos 4 (guardar solo los últimos viajes) y 5 (el estado, con la alerta) solo tienen un comentario. Resuelve y corre `python comprobar.py` hasta que los cinco pasos digan `OK`. Después:

```
python entrenar.py
python simular_semanas.py
```

[`simular_semanas.py`](./starter/ejercicio2/simular_semanas.py) manda al servicio una semana normal, una de feriado y una del aumento, y muestra `/deriva` después de cada una (no lo modifiques).

**Respuesta 1:** ¿qué dijo `/deriva` después de cada semana? ¿Alguna alerta te sorprendió, o te faltó?

Normal: sin alerta (PSI 0.05). Feriado: **alerta** (PSI 0.26 y 0.22). Aumento: sin alerta (PSI 0.06). No me sorprendió; faltó la alerta del aumento, que es la semana en que más se equivoca el modelo.

**Respuesta 2:** la alerta del monitor no dijo nada en la semana del aumento, que es la que más empeora el modelo. ¿Qué alerta de la sesión pasada sí la habría visto, y por qué tarda más?

La del MAE semanal de `desempeno.py` (3.67 veces la referencia desde el 16 de noviembre). Tarda porque necesita la tarifa cobrada, que llega después del viaje; el PSI solo usa lo que llega en la petición.

**Respuesta 3:** escribe la regla que usaría el equipo para decidir, con las dos alertas (la de deriva de este ejercicio y la del MAE de la sesión pasada), si lo que pasa es deriva de datos, deriva conceptual o nada. ¿Qué haría en cada caso?

| PSI > 0.15 | MAE > 1.3 × referencia | Diagnóstico | Qué hacer |
|---|---|---|---|
| No | No | Nada | Seguir monitoreando |
| Sí | No | Deriva de datos inofensiva | Registrar la causa; no reentrenar |
| Sí | Sí | Deriva de datos que daña | Reentrenar con viajes recientes |
| No | Sí | Deriva conceptual | Confirmar qué cambió y reentrenar con las tarifas nuevas |

**Si terminas antes:** el monitor mira solo dos features. Inventa una semana con deriva de datos que este monitor no vería. ¿Empeoraría el modelo?

Una semana con 6 veces más viajes en hora pico (una huelga de metro): el PSI de `es_hora_pico` sube a 0.97, pero el de distancia y zona queda bajo 0.15, así que no hay alerta. El modelo no empeora (MAE 1.18), porque ya vio muchos viajes en hora pico.

## Ejercicio 3: la deriva de tu proyecto

Usa tu proyecto en [`psets/proyecto/`](../../psets/README.md) y el servicio instrumentado de la sesión pasada. Esta vez no hay plantilla.

### Entregable 1: la simulación, en `monitoreo/`

Un notebook o un script que, con tus datos de prueba:

- mida el PSI de al menos dos de tus features en ventanas normales (del tamaño de lo que recibe tu servicio en un período), para saber cuánto se mueve sin que nada cambie;
- simule una deriva de datos y una deriva conceptual que tengan sentido en tu problema, y mida el PSI y tu métrica de la Semana 11 en cada una;
- elija el umbral de la alerta con esos números, y guarde la referencia que necesita el servicio.

### Entregable 2: la alerta, en el servicio

Un monitor de deriva en tu servicio (puedes adaptar `deriva.py`) con una ruta que diga el PSI de la ventana actual y si hay alerta, y una prueba en `servicio/test_api.py` que compruebe que la alerta se enciende con una ventana alejada de la referencia.

### Entregable 3: `docs/monitoreo.md`

Agrega la sección **Deriva**: la tabla de la simulación, el umbral elegido y por qué, y qué deriva no detecta tu alerta.

**En tu proyecto, ¿qué deriva de datos es la más probable, y empeoraría tu modelo? ¿Y qué deriva conceptual?**

Cambios generales del mercado.

**Si tu alerta de deriva se enciende y tu métrica de desempeño no cambia, ¿qué haces?**

Es deriva de datos que el modelo tolera: registro la causa (por ejemplo, un mes de volatilidad alta) y no reentreno; sigo vigilando el MAE y el Sharpe del mes siguiente antes de decidir.

## Antes de la próxima sesión

**Lectura:** ["How to Effectively Communicate Results to Stakeholders As a Data Scientist"](https://medium.com/@sahin.samia/how-to-effectively-communicate-results-to-stakeholders-as-a-data-scientist-711e88dd464f), Sahin Samia.

En las últimas cuatro sesiones construiste un servicio, un registro, métricas y alertas, con PSI, MAE, p95 y recall. ¿Qué cambia entre explicarle tu proyecto a otro científico de datos y a quien paga la factura? Escribe la primera oración que le dirías a cada uno.

En el primer caso debo usar prioritariamente términos técnicos, en el otro primero explicar el negocio y solo si hay un técnico en la reunión y pregunta algo, profundizar.

- **A otro científico de datos:** "Predigo el retorno logarítmico a un mes de las acciones del S&P 500 en la NYSE, lo comparo en MAE con líneas base simples, y en producción vigilo el PSI de las features y el error de cada mes."
- **A quien paga:** "Cada mes le propongo al asesor 10 acciones con el riesgo que acordó con su cliente, con la meta de rendir más que el índice; si no lo logramos, recomendamos el índice."
