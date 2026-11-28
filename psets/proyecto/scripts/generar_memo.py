"""Genera docs/PSet4_memo_Gomez_Ehmig.pdf: documento tecnico del proyecto final (<= 12 paginas + anexos).

Mismo formato que los memos de los PSets 2 y 3. Las cifras de la simulacion se leen de docs/simulacion/*.csv
(notebook 06). Anexos: glosario, docs/cambios.md y los memos de los PSets 1 (v2 con feedback), 2 y 3, que se
anexan como PDF. El enlace del video va en la variable VIDEO_URL. Uso, desde psets/pset-04/:
    VIDEO_URL=https://... uv run --project api --with reportlab --with pypdf python scripts/generar_memo.py
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)
from reportlab.platypus.flowables import CallerMacro

R = Path(__file__).resolve().parents[1]
D, F, S = R / "docs", R / "docs" / "figuras", R / "docs" / "simulacion"
REPO = R.parents[1]
AZUL, GRIS, LINEA = colors.HexColor("#17384D"), colors.HexColor("#526775"), colors.HexColor("#D5DEE3")
MAX_PAGINAS = 12
VIDEO = os.environ.get("VIDEO_URL", "https://drive.google.com/file/d/1btUpZCoxSnJRdy5f02ZRcjz0P7st4Lbu/view?usp=sharing")


def leer(n):
    return list(csv.DictReader((S / n).open()))


def c(x, d=2):
    return f"{float(x):.{d}f}".replace(".", ",")


neg = {r[""]: r for r in leer("resumen_negocio.csv")}
reent = leer("reentrenamientos_simulacion.csv")

st = getSampleStyleSheet()
st.add(ParagraphStyle("TitleX", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=AZUL, spaceAfter=6))
st.add(ParagraphStyle("BodyX", fontName="Helvetica", fontSize=9.2, leading=12.2, spaceAfter=5))
st.add(ParagraphStyle("SmallX", fontName="Helvetica", fontSize=7.6, leading=9.4, spaceAfter=4))
st.add(ParagraphStyle("CapX", fontName="Helvetica-Oblique", fontSize=7.6, leading=9.4, textColor=GRIS, spaceAfter=7))
st.add(ParagraphStyle("HeadX", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=AZUL, spaceBefore=7, spaceAfter=4))
st.add(ParagraphStyle("BulX", parent=st["BodyX"], leftIndent=11, bulletIndent=2, spaceAfter=2.5))
st.add(ParagraphStyle("CodeX", fontName="Courier", fontSize=7, leading=8.6, backColor=colors.HexColor("#F4F6F7"),
                      borderPadding=(4, 4, 4, 4), spaceBefore=2, spaceAfter=8))
st.add(ParagraphStyle("BoxX", parent=st["BodyX"], backColor=colors.HexColor("#EEF4F7"), borderPadding=(6, 6, 6, 6),
                      borderColor=colors.HexColor("#C9D8E0"), borderWidth=0.6, spaceBefore=4, spaceAfter=10))
story = []


def p(t, s="BodyX"):
    story.append(Paragraph(t.replace("&", "&amp;"), st[s]))


def b(t):
    story.append(Paragraph(t.replace("&", "&amp;"), st["BulX"], bulletText="•"))


def h(t):
    p(t, "HeadX")


def code(t):
    story.append(Paragraph(escape(t).replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;"), st["CodeX"]))


def table(headers, rows, widths, size=7.3):
    sty = ParagraphStyle("t", fontName="Helvetica", fontSize=size, leading=size + 1.8)
    sth = ParagraphStyle("th", parent=sty, fontName="Helvetica-Bold")
    data = [[Paragraph(escape(str(x)), sth) for x in headers]] + [[Paragraph(escape(str(x)), sty) for x in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7F0F5")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBELOW", (0, 0), (-1, 0), .7, AZUL), ("LINEBELOW", (0, 1), (-1, -1), .3, LINEA),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    story.extend([t, Spacer(1, 6)])


def figura(ruta, ancho, texto):
    im = Image(str(ruta))
    s = ancho / im.imageWidth
    im.drawWidth, im.drawHeight = im.imageWidth * s, im.imageHeight * s
    story.append(KeepTogether([im, Spacer(1, 2), Paragraph(texto.replace("&", "&amp;"), st["CapX"])]))


# ------------------------------------------------------------------ portada
p("PSet 4 | Proyecto final: del dato a la operación", "TitleX")
p("Allan Paul Gómez Ehmig · 00351916<br/>MSDS 6003 · USFQ · 27 de noviembre de 2026 · "
  f"Video de demostración: {escape(VIDEO)}", "SmallX")
story.append(Spacer(1, 6))
p("<b>Qué se construyó.</b> Un sistema que cada fin de mes propone al asesor las 10 acciones del S&P 500 que cotizan en "
  "la NYSE y su peso, con un modelo servido por una API, alimentado por el pipeline del PSet 2 y vigilado lote a lote. "
  "Los 35 meses posteriores al corte se pasaron por el sistema como si fueran producción, con tres meses de crisis inducida. "
  "<b>Resultado:</b> el monitoreo detectó la crisis en el primer lote y el ciclo de reentrenamiento con aprobación humana "
  "funcionó, pero reentrenar con la regla del PDF empeoró el negocio (Sharpe neto −0,23 frente a 0,05 del modelo fijo y "
  "−0,13 de B5). El competidor más fuerte es una regla sin modelo, la <b>operación manual</b> (las 10 acciones de mejor "
  "Sharpe de 12 meses bajo la volatilidad aprobada): Sharpe 1,20 en el hold-out real frente a 0,87 del modelo, y 0,35 en la "
  "simulación (US$ 100.000 → 128.025), aunque en la validación cruzada queda bajo B3 y B5. <b>Recomendación:</b> ajustar: el "
  "asesor opera con la operación manual; el modelo corre en paralelo y solo la reemplaza si la supera en 6 lotes reales.", "BoxX")

# ------------------------------------------------------------------ 1
h("1. Problema y formulación (versión final)")
table(["Elemento", "Definición final"], [
    ["Problema", "El inversionista minorista arma su portafolio por intuición, sin controlar la volatilidad. El asesor necesita una propuesta mensual disciplinada."],
    ["Unidad / universo", "Acción por cierre de mes; S&P 500 histórico ∩ NYSE (327–337 acciones elegibles por mes)."],
    ["Target y horizonte", "Retorno logarítmico del mes siguiente (ret_log_mes_siguiente); horizonte = rebalanceo = 1 mes (decisión H del feedback del PSet 1)."],
    ["Métrica técnica", "MAE (colas gruesas: curtosis en exceso 9,6), con acierto direccional como apoyo."],
    ["Métrica de negocio", "Sharpe neto anualizado del portafolio, con 15 pb por US$ negociado; drawdown máximo."],
    ["Línea base", "B1 media histórica (MAE CV 0,0641 ± 0,016); B5 universo con igual peso (referencia de negocio); efectivo."],
    ["Umbral de decisión", "Top 10 por retorno predicho, excluido el 20 % más volátil del mes; pesos 1/vol_63d; volatilidad del portafolio ≤ 1,35 × S&P 500 (el resto en efectivo)."],
    ["Juicio humano", "El asesor revisa y el cliente aprueba cada propuesta; el sistema no ejecuta órdenes. Un científico de datos aprueba cada cambio de modelo."],
], [95, 385])

# ------------------------------------------------------------------ 2
h("2. Arquitectura end-to-end")
p("<b>Flujo.</b> Kestra ingiere precios y composición a RAW (ingesta_diaria L-V 18:30 NY; backfill_historico por años) y "
  "llama a transformar: dbt construye y prueba Bronze, Silver y Gold, y Spark escribe la OBT mensual. Al cierre de mes, "
  "produccion_lotes lee el lote de la OBT, lo manda a POST /predecir y guarda cada predicción en PRODUCCION.PREDICCIONES; "
  "monitoreo calcula sistema, datos y modelo, escribe MONITOREO y ALERTAS y avisa por correo; si la regla lo pide, "
  "reentrenamiento entrena un challenger, lo registra en MLflow y espera aprobación antes de mover @champion. La API "
  "siempre sirve models:/portafolio-inversiones-modelo@champion: cambiar de modelo no reconstruye la imagen. GitHub "
  "Actions prueba cada cambio y publica la imagen en GHCR.")
figura(D / "arquitectura_vertical.png", 400, "Figura 1. Arquitectura: un solo docker-compose.yml con Kestra (y Postgres), Spark, MLflow y la API; "
       "datos y tablas de producción en Snowflake (PORTAFOLIO_P4). Fuente: docs/arquitectura.dot.")

# ------------------------------------------------------------------ 3
h("3. Datos")
b("<b>Ingesta, retries y backfill.</b> Grupos de 100 símbolos con 3 intentos; la tarea falla si más del 10 % de los grupos "
  "agota sus intentos (bitácora RAW.INGESTA_LOG). Kestra reintenta la ingesta con espera exponencial (2 → 30 min, 4 "
  "intentos), dbt 2 veces y Spark 2 veces; si dbt falla, Spark no corre. El backfill recorre 2010–2026 por año y transforma "
  "una vez; RAW es append-only y Bronze deduplica por clave, así que repetir una ventana no duplica hechos.")
b("<b>Calidad (métricas que cambiaron decisiones).</b> 50,3 % de filas de precios redundantes por reingestas (Bronze toma "
  "la última); 0,61 % de sesiones sin fila (forward-fill hasta 5 sesiones, huecos largos excluidos); 2,41 % de retornos "
  "atípicos por MAD > 3,5, marcados y no borrados (se concentran en marzo de 2020 y abril de 2025, eventos reales); 11,6 % "
  "de solicitudes sin datos, que la frescura de dbt no detecta.")
b("<b>Capas y estrella.</b> Bronze: tipos y deduplicación; Silver: calendario NYSE, membresía, retornos; Gold: "
  "FCT_PRECIOS_DIARIOS (grano acción por día bursátil, 1,83 millones de filas) y FCT_MERCADO_DIARIO con DIM_ACCION, "
  "DIM_FECHA y DIM_MEMBRESIA_SP500 (anexo: modelo_dimensional.png). 82 tests de dbt (not_null, unique, relationships y "
  "de negocio).")
b("<b>OBT.</b> OBT_ACCION_MES: grano acción por mes (accion_key + anio_mes), 87.178 filas y 75 columnas; 13 de 13 controles "
  "de joins y grano en VALIDACION_OBT; si uno falla no se sobrescribe la OBT. En el PSet 4 se reconstruyó en PORTAFOLIO_P4: "
  "mismas filas que el PSet 3; GM pasó de NYSE a Nasdaq en los listados actuales y sale del universo (docs/datos_p4.md).")
b("<b>Batch y no streaming.</b> Se consumen cierres diarios y se decide una vez al mes: el lote permite validar y "
  "reintentar antes de la revisión del asesor. Streaming solo tendría sentido con alertas intradía (sección 5).")

# ------------------------------------------------------------------ 4
h("4. Modelado")
b("<b>EDA que cambió el experimento.</b> El mes explica 34,5 % de la variación del retorno → validación por meses completos y "
  "feature dispersion_mes; ninguna de 28 variables tiene relación significativa dentro del mes → solo cuentan mejoras "
  "mayores que la variación entre pliegues; colas gruesas → MAE; 23 pares con correlación > 0,9 → regularización.")
b("<b>Features y fuga.</b> 33 de la OBT + dispersion_mes y mes_calendario_obj (35; 45 tras el one-hot). Quedan fuera el "
  "precio ajustado en nivel (cambia con dividendos futuros), sigue_en_sp500 y la bolsa actual. Pruebas: "
  "test_dispersion_solo_usa_el_mes, test_mes_calendario_del_objetivo, test_interpolacion_no_cruza_el_corte.")
b("<b>Validación.</b> TimeSeriesSplit de 7 pliegues de 12 meses con un mes de separación, división por fecha del objetivo "
  "(entrenamiento hasta 2023-12; hold-out 2024-01 a 2026-10).")
table(["Modelo", "MAE CV", "Sharpe neto CV", "Hold-out"], [
    ["B1 media histórica", "0,0641 ± 0,0165", "—", "MAE 0,0634"],
    ["B3 media por acción (regla manual)", "0,0652 ± 0,0159", "0,585", "—"],
    ["B5 universo igual peso", "—", "0,544", "Sharpe 0,68"],
    ["Ridge ajustado (v2, @challenger)", "≈ 0,0636", "—", "MAE 0,0635 · Sharpe −0,02"],
    ["LightGBM ajustado (v1, @champion)", "0,0636 ± 0,016", "—", "MAE 0,0673 · Sharpe 0,87"],
], [170, 95, 85, 130])
p("<b>Ganador:</b> LightGBM (objetivo L1, 63 árboles, semilla 42), run f7596a565f8a458492057238f245cf89, versión 1 de "
  "portafolio-inversiones-modelo. Ganó por menor MAE de CV, un empate técnico con Ridge (diferencia 0,00006 frente a una "
  "desviación de 0,016). En el PSet 4 su MAE del hold-out se reproduce en CI (tests/test_modelo.py).")

# ------------------------------------------------------------------ 5
h("5. Despliegue")
p("<b>Patrón: batch mensual servido por API.</b> La decisión es mensual, hay ≥ 17 h entre el cierre y la apertura, las "
  "features cambian una vez al mes y son ~330 predicciones por lote. El modelo predice un lote en ~9 ms (medido en la VM); "
  "en producción, la petición completa de un lote a la API en Docker tarda 41,9 ms (mediana de los 35 lotes; una "
  "petición por lote, por eso p50 = p95 en MONITOREO). La "
  "decisión necesita el corte transversal del mes (top 10, percentil 80 de volatilidad), así que /predecir recibe el lote "
  "completo. Online solo convendría con rebalanceo intradía o alertas por noticias (docs/despliegue.md).")
code('POST /predecir  {"anio_mes": 202312, "acciones": [{"accion_key": "...", "ticker": "JNJ", "ret_log_mes": 0.012, ... 33 features}, ...333]}\n'
     '200 {"id_lote": "9f...", "mes_objetivo": "2024-01", "usado": "modelo", "n_incluidas": 10,\n'
     '     "modelo": {"nombre": "portafolio-inversiones-modelo", "version": "1", "alias": "champion", "run_id": "f7596a56..."},\n'
     '     "acciones": [{"id_prediccion": "c1...", "ticker": "JNJ", "retorno_predicho": 0.0123, "decision": "incluir", "peso": 0.137}, ...]}\n'
     'POST /predecir {"anio_mes": 202313, ...}  ->  422 {"mensaje": "Entrada invalida en: anio_mes", "campos_invalidos": ["anio_mes"]}')
b("<b>Contrato.</b> El esquema Pydantic es la firma registrada en MLflow (33 features float, anio_mes entero); rangos del "
  "entrenamiento ± 50 % (rechaza errores de unidad como un retorno en %), campos extra prohibidos, mes 1–12. Las dos "
  "derivadas se calculan con src.pipeline.derivar, importada.")
b("<b>Pruebas (49, pytest, en pset-04 y en proyecto).</b> Contrato: 200; 422 con el campo por faltante, tipo, mes inexistente, fuera de rango, campo "
  "extra y acción repetida; 401 sin token. Modelo: la copia del champion en tests/fixtures (mlflow.sklearn.save_model) "
  "reproduce MAE 0,0673399888 con tolerancia 1e-6 (diferencias de plataforma; 10.000 veces menor que la desviación de CV), y la "
  "API predice igual que el modelo directo. Comportamiento: 10 incluidas y pesos que suman 1; ninguna sobre el percentil "
  "80 de volatilidad; la menos volátil pesa más; misma entrada, misma decisión; respaldo por interruptor y si el modelo no "
  "carga; recarga fallida conserva el modelo; cada predicción queda registrada. Producción: el mes en vivo se sirve sin "
  "objetivo, no se rellena con meses posteriores, A7 pide dos lotes y la deriva sola no dispara. Operación manual: Sharpe de 12 "
  "meses, tope de volatilidad y rotación solo por la diferencia. Auditoría: regla de promoción con los 5 casos reales, "
  "promoción solo con regla y aprobación, versión atómica ante una recarga, registro fallido visible, reproceso sin alertas "
  "y flows válidos para Kestra 2.0.")
b("<b>Fuera de CI:</b> Snowflake, Kestra, Spark y el servidor de MLflow (credenciales y memoria); la simulación y el "
  "reentrenamiento se verifican con la corrida de produccion_lotes. CI: pset4-ci.yml (pruebas, imagen y prueba de la imagen "
  "arrancada); CD: pset4-cd.yml publica ghcr.io/virtualzen/pset4-api:&lt;hash&gt; al integrar en master (captura en el anexo).")

# ------------------------------------------------------------------ 6
h("6. Versionado, reentrenamiento y despliegue continuo")
b("<b>Disparador:</b> rendimiento (A7: MAE de 2 lotes etiquetados seguidos > 0,0801, media de la CV + 1 desviación; un mes "
  "aislado sobre ese valor ocurre en 8 de 34 lotes) o calendario (12 lotes etiquetados), con enfriamiento de 3 lotes. La "
  "deriva de datos sola no dispara. Solo lotes cuyo objetivo ya llegó, tal como se sirvieron.")
b("<b>Ventana:</b> expansiva desde 2013 (la que validó el PSet 3; conserva las crisis de 2018, 2020 y 2022), misma "
  "preparación de src/pipeline.py e hiperparámetros del champion (clone, sin tuning). Tags fase=reentrenamiento y motivo; "
  "registro como versión nueva con alias @challenger.")
b("<b>Regla de promoción</b> (sobre el lote etiquetado más reciente, que ninguno vio): el retorno del top 10 del challenger "
  "debe superar al del champion por más de una desviación de la CV de esa métrica de negocio (0,0134: retorno mensual medio "
  "del top 10 en los 7 pliegues del PSet 3, scripts/desviacion_cv_negocio.py), y su MAE no puede ser peor en más de 0,1 "
  "desviaciones de la CV del MAE (0,0016).")
b("<b>No se promueve solo:</b> reentrenamiento.yml se detiene en una tarea Pause hasta que una persona apruebe o rechace con "
  "su motivo. Un lote es poco para separar habilidad de suerte, un mal cambio lo paga el cliente un mes entero, y la persona ve "
  "lo que la regla no (lotes sintéticos, concentración, restricciones del asesor). El código sí se despliega solo (CD), porque "
  "las pruebas verifican su contrato; el modelo no, porque su calidad solo se conoce un mes después.")
table(["Llegada", "Disparador", "Champion → challenger", "Evalúa en", "MAE champ. / chall.", "Retorno champ. / chall.", "Decisión"],
      [[r["anio_mes_llegada"], r["disparador"], f"{r['version_champion']} → {r['version_challenger']}",
        r["lotes_evaluacion"].strip("[]"), f"{c(r['mae_champion'], 4)} / {c(r['mae_challenger'], 4)}",
        f"{c(float(r['retorno_champion']) * 100, 1)} % / {c(float(r['retorno_challenger']) * 100, 1)} %",
        ("aprobado" if r["aprobado"] == "True" else "rechazado") + f" ({r['motivo_regla']})"] for r in reent],
      [40, 72, 62, 42, 74, 78, 112])
p("En la corrida en Kestra los challengers son las versiones 3, 4, 5, 6 y 8, con las mismas decisiones y comparaciones de la tabla: la v7 se rechazó por un error de captura en la pausa (no se marcó aprobado) y se repitió como v8, idéntica y aprobada; las dos filas quedan en REENTRENAMIENTOS. Al corregir se reprocesó desde 2026-05 y no desde 2026-04 (error de operación): 2026-04 quedó servido con v3. Producción y simulación coinciden en 34 de 35 lotes; difieren 2026-04 (cartera servida +5,8 % frente a −3,7 % simulada) y la alerta A9 de 2026-09, que solo aparece en la simulación (docs/reconciliacion.md). Producción es la historia observada; la simulación, el contrafactual sin el error. Desde la auditoría, Kestra promueve solo si la regla y la persona coinciden; la regla se prueba en CI con los cinco casos. <b>Rollback:</b> monitoreo.produccion "
  "revertir mueve @champion a @anterior y llama a /recargar; /modelo muestra la versión y el run_id antes y después (anexo C y "
  "video). <b>Ciclo sobre la deriva:</b> los lotes inducidos 2025-05 a 07 disparan A4 y A8 desde el primero; con el MAE de "
  "2025-05 (0,093) y 2025-06 (0,129) sobre el umbral, el monitoreo de 2025-07 dispara A7; al llegar 2025-08 se entrena r3 "
  "(hasta 2025-06), se compara en 2025-07 y, aunque mejora el MAE (0,1065 frente a 0,1173), su top 10 rinde lo mismo (−9,0 % "
  "frente a −8,9 %): la regla dice no promover y el revisor lo rechaza. Reentrenar no protege de una caída que golpea a todas "
  "las acciones por igual; protege el criterio de retirada R1.")

# ------------------------------------------------------------------ 7
h("7. Simulación, monitoreo y alertas")
b("<b>Lotes:</b> 35 cierres de mes posteriores al corte (2023-12 a 2026-10), 327–340 acciones cada uno, en orden. Los 34 "
  "primeros reciben su objetivo un lote después; 2026-10 es el mes en vivo y se predice sin objetivo. Los lotes se preparan "
  "sin el objetivo ni meses posteriores (preparar_inferencia, probado en tests/test_produccion.py). El mismo código corre en "
  "Kestra (Snowflake + API) y en el notebook 06, con los mismos reentrenamientos y alertas.")
b("<b>Deriva inducida (2025-05 a 07):</b> 9 features de volatilidad y rango ×2, retornos del mes −10 % log y objetivo −10 % "
  "log (crisis tipo marzo de 2020), marcados sintetico=True. Solo con features alteradas el MAE apenas cambiaba (0,0481 → 0,0495).")
b("<b>Métricas:</b> sistema (latencia p50 y p95, solicitudes, 4xx y 5xx en la ventana del lote, vía /metricas?desde=); datos "
  "(% de nulos y fuera del rango de entrenamiento por feature, categorías no vistas, PSI con umbral = max(0,10; p95) y "
  "max(0,25; p99) del PSI de los 132 meses de entrenamiento, KS como respaldo; PSI con chi-cuadrado de respaldo en la categórica; z mensual en las "
  "6 de mercado, que valen lo mismo para todas las acciones del mes y no tienen distribución transversal para un PSI: "
  "desviación equivalente, disclaimer 16); modelo (distribución de predicciones, tasa de incluir, MAE con un lote de retraso); negocio (Sharpe de 12 "
  "lotes frente a B5).")
table(["Id", "Métrica", "Umbral", "Ventana", "Sev.", "Quién la recibe", "Acción"], [
    ["A1", "errores 5xx", "> 0", "desde el envío", "crít.", "ing. ML", "Respaldo ya responde; recargar o revertir"],
    ["A3", "filas inválidas / categorías no vistas", "> 2 % / ≥ 1", "1 lote", "alerta", "ing. datos", "Revisar ingesta y dbt; no reentrenar"],
    ["A4", "features con PSI crítico", "≥ 5", "1 lote", "crít.", "cient. datos", "Diagnosticar captura vs. mercado"],
    ["A5", "features de mercado |z|", "> 3", "1 lote", "alerta", "cient. datos", "Revisar topes; informar al asesor"],
    ["A6", "salida del modelo |z|", "> 3", "1 lote", "alerta", "cient. datos", "Revisar estabilidad del top 10"],
    ["A7", "MAE por lote", "> 0,0801", "2 lotes seguidos", "crít.", "cient. datos", "Reentrenamiento con aprobación"],
    ["A8", "Sharpe − Sharpe B5", "< −0,5", "12 lotes", "crít.", "resp. producto", "Criterio R1: respaldo y revisión"],
    ["A9", "Sharpe − Sharpe operación manual (B7)", "< −0,5", "12 lotes", "crít.", "resp. producto", "Criterio R6: operar con B7, modelo en paralelo"],
], [20, 115, 52, 62, 32, 62, 137], size=6.9)
p("A2 (latencia p95 > 2 s) completa la plantilla (docs/monitoreo.md). <b>Diagnóstico</b> (tabla de la sección 6.2 del PDF): "
  "entradas que cambian con desempeño estable = deriva de datos sin impacto (2024: tasa libre de riesgo a más de 3 "
  "desviaciones de 2013-2023, A5; abril de 2025: aranceles, 8 features críticas, A4) → no se reentrena; entradas que cambian "
  "y desempeño que cae = deriva con impacto (la crisis inducida: A4 + A7) → reentrenar y, si no basta, retirada; entradas "
  "estables y desempeño que cae = deriva conceptual (fines de 2024, febrero-marzo de 2026: A7) → reentrenar. <b>Falsas "
  "alarmas</b> en los 32 lotes reales: A5 en 2024 es falsa para el modelo (ajuste: z contra los últimos 36 meses); A4 en "
  "2025-04 es un choque real (subir a 9 features la silenciaría, pero también al lote inducido 2025-06); A8 tras la crisis es "
  "efecto de la ventana de 12 lotes (ajuste: excluir los lotes sintéticos).")
figura(F / "psi_por_lote.png", 400, "Figura 2. PSI de cada feature por lote, relativo a su umbral crítico (recuadros: lotes inducidos).")
figura(F / "mae_por_lote.png", 400, "Figura 3. MAE de cada lote (medido un lote después), banda de la CV y umbral A7; líneas: reentrenamientos.")

# ------------------------------------------------------------------ 8
h("8. Ética y retirada")
sub = list(csv.reader((S / "subgrupos.csv").open()))
cab = sub[0]
sub = [dict(zip(["grupo", "quintil"] + cab[2:], r)) for r in sub[1:]]
filas = [[s["grupo"], s["quintil"], c(s["mae"], 4), f"{c(float(s['acierto_direccional']) * 100, 1)} %",
          f"{c(s['tasa_inclusion_%'], 1)} %",
          ("—" if not s["retorno_medio_incluidas"] else f"{c(float(s['retorno_medio_incluidas']) * 100, 1)} %")] for s in sub]
table(["Subgrupo", "Quintil", "MAE", "Acierto", "Tasa incluir", "Retorno incluidas"], filas, [60, 70, 55, 60, 60, 80], size=7)
p("El error es parejo por tamaño, pero las pocas acciones pequeñas que el modelo elige rinden −3,4 % al mes frente a +1,1 a "
  "3,8 % del resto: no es aceptable sin control para el negocio ni para el inversionista, que asume la pérdida (~US$ 340 por "
  "posición pequeña y mes); por eso tiene su criterio (R3). <b>Quién asume cada error</b> (US$ 100.000): la sobreestimación "
  "(incluir una acción que cae; 4,2 de 10 por lote, mediana US$ 1.638, máximo US$ 10.167) la paga el inversionista con su "
  "capital, y el asesor en confianza; la subestimación (dejar fuera una del top 10 real; mediana US$ 17.846 de oportunidad) "
  "también recae en el inversionista, sin pérdida de capital, y en la casa de valores si el cliente se compara con el índice.")
table(["Criterio", "Métrica y umbral", "Respuesta"], [
    ["R1", "Sharpe 12 lotes − B5 < −0,5 durante 3 lotes", "Interruptor de respaldo (B5) y revisión con el asesor"],
    ["R2", "Drawdown < −25 % (el cliente tolera −20 %)", "Efectivo en el exceso de riesgo; revisión antes de rearmar"],
    ["R3", "Retorno medio de pequeñas incluidas (12 lotes) < −2 %", "Excluir el quintil pequeño hasta reentrenar y revisar"],
    ["R4", "5xx o el modelo no carga", "La API ya responde con el respaldo marcado; recargar o revertir"],
    ["R5", "Dos reentrenamientos seguidos rechazados con A7 activa", "Retirar el modelo y volver a experimentación"],
    ["R6", "Sharpe 12 lotes − operación manual < −0,5 durante 3 lotes (A9)", "Operar con la operación manual; el modelo en paralelo"],
], [40, 210, 230])
p("En la simulación se cumplen R1 (2025-07), R3 (−3,4 %), R5 (rechazos en 2025-03, 2025-08 y 2025-11) y R6 (desde 2025-02). <b>Interruptor:</b> "
  "USAR_RESPALDO=true al arrancar, o POST /respaldo?activar=true con X-Token sin reiniciar; responde B1 + B5 marcado "
  "respaldo: true (pruebas y video). <b>Supervisión humana:</b> el juicio del PSet 1 se mantiene: el cliente aprueba siempre cada "
  "propuesta. Se amplía: el asesor le presenta cada mes la propuesta del modelo y la de la operación manual (B7, challenger "
  "adicional calculado en paralelo por la API); cada mes se decide mantener, pasar al respaldo o retirar el servicio según "
  "las alertas del reentrenamiento (A7 repetidas, rechazos seguidos, A8/A9); y un científico de datos aprueba cada cambio "
  "de modelo en la pausa de Kestra, que tras el incidente v7 debe mostrar el veredicto de la regla.")

# ------------------------------------------------------------------ 9
h("9. Resultado de negocio")
filas_c = list(csv.reader((S / "competidores.csv").open()))[1:]
cc = {(f[0], f[1]): f for f in filas_c}
def sh(etapa, n):
    f = cc.get((etapa, n))
    return "—" if not f or not f[2] else c(f[2])
nombres_c = ["modelo (LightGBM v1)", "Ridge (v2)", "B3 media por acción", "B5 universo igual peso", "operación manual"]
table(["Competidor (misma regla de riesgo y costos)", "Sharpe CV 2017-23", "Sharpe hold-out real", "Sharpe simulación", "Retorno anual simulación"],
      [[n, sh("validacion_cruzada", n), sh("holdout_real", n),
        sh("simulacion_produccion", "modelo fijo (v1)" if n.startswith("modelo") else n),
        (lambda f: "—" if not f else f"{c(float(f[3]) * 100, 1)} %")(cc.get(("simulacion_produccion", "modelo fijo (v1)" if n.startswith("modelo") else n)))]
       for n in nombres_c] + [["sistema con reentrenamientos (regla del PDF)", "—", "—", sh("simulacion_produccion", "sistema (regla del PDF)"),
                               f"{c(float(cc[('simulacion_produccion', 'sistema (regla del PDF)')][3]) * 100, 1)} %"],
                              ["efectivo (no hacer nada)", "—", "—", "—", f"{c(float(cc[('simulacion_produccion', 'efectivo')][3]) * 100, 1)} %"]],
      [170, 70, 75, 70, 95])
figura(F / "competidores_por_lote.png", 420, "Figura 4. Valor de US$ 100.000 lote a lote en la simulación, neto de costos. Rojo: lotes inducidos. "
       "Notebook 08; reentrenamientos marcados en docs/figuras/negocio_por_lote.png.")
p("<b>Operación manual</b> (src/operacion_manual.py): cada mes, las 10 acciones elegibles de mayor Sharpe de 12 meses "
  "((ret_log_252d − 12·rf) / vol_63d), sin el 20 % más volátil, con pesos 1/vol, el tope de portafolio y 15 pb por US$ "
  "negociado; se compra o vende solo la diferencia con el mes anterior. Usa la misma regla de riesgo que el modelo, así que "
  "la comparación aísla la selección. Está en todo el flujo como la línea base B7: corrida de línea base en MLflow "
  "(fase=linea_base), decisión en paralelo en cada respuesta de la API y en PREDICCIONES, retorno y Sharpe por lote en "
  "MONITOREO, alerta A9 y tablero. Elige casi otras acciones que el modelo (0 a 2 de 10 en común por lote).")
p("<b>¿Valió la pena actuar según la predicción?</b> Con la regla de reentrenamiento del PDF, <b>no</b>: US$ 100.000 terminan "
  "en 94.825, bajo B5 (103.507) y el efectivo (112.773). El modelo fijo supera a B5 en riesgo ajustado (0,05 frente a −0,13) "
  "pero no al efectivo. Y una regla sin modelo, la operación manual, le gana en el hold-out real (1,20 frente a 0,87, caída "
  "máxima −6,9 % frente a −11,5 %) y en la simulación (0,35; 128.025), con la mitad de rotación (0,90 frente a 1,76 por mes). "
  "En la validación cruzada 2017-2023, en cambio, queda bajo B3 (0,585) y B5 (0,544): su ventaja no es estable en todos los "
  "periodos. Por qué gana: el Sharpe de 12 meses premia acciones que suben con poca volatilidad, la misma idea de la regla de "
  "riesgo, mientras que el pronóstico del modelo empata con el promedio histórico. Estas cifras reemplazan las del pitch "
  "del PSet 1, cuya meta (superar al índice por 0,1 de Sharpe) el modelo no cumple.")
p("<b>Reconciliación (auditoría).</b> La API decide la composición y los pesos relativos (100 % en acciones); el tope de "
  "portafolio (1,35 veces la volatilidad del S&amp;P 500, con covarianzas diarias) y los 15 pb se aplican fuera de la API, y "
  "A8/A9 y la promoción usan retorno bruto. Medida sobre la trayectoria realmente servida (34 lotes etiquetados, "
  "scripts/reconciliacion.py): monitoreo bruto Sharpe 0,15 (US$ 116.291); estrategia completa con tope y costos −0,06 "
  "(US$ 103.925); simulación −0,23 (US$ 94.825). El tope invirtió menos de 100 % en 9 meses (64,7 % en 2026-02). Ninguna "
  "política de retirada se ejecutó en la corrida (el interruptor solo se demostró): los resultados son sin intervención.")

# ------------------------------------------------------------------ 10
h("10. Limitaciones y siguientes pasos")
b("<b>Señal débil:</b> el modelo empata con la media histórica en MAE; el valor viene de la disciplina de la regla.")
b("<b>Regla de promoción ruidosa:</b> comparar en un lote (PDF) promovió challengers con suerte; evaluar en 6 lotes dio "
  "Sharpe 0,12. Umbrales A4 y A8 calibrados con la misma simulación; hay que revisarlos con lotes reales. Los tres lotes de "
  "crisis son sintéticos y dominan el resultado.")
b("<b>Universo con sesgo:</b> bolsa actual para toda la historia (GM) y sin sector, lo que limita el análisis por subgrupo.")
b("<b>Operación local:</b> todo corre en una máquina; Kestra, Spark y MLflow juntos piden ~11 GB.")
b("<b>Operación manual:</b> gana en 2 de 3 etapas, no en la validación cruzada; vol_63d aproxima la volatilidad de 12 meses.")
b("<b>Primero, si el proyecto continúa:</b> (1) 6–12 meses reales operando con la operación manual y el modelo en paralelo "
  "(sombra), con el respaldo listo; (2) que el modelo solo la reemplace si la supera por más de una desviación de la CV en 6 "
  "lotes; (3) usar el Sharpe de 12 meses como feature o como objetivo de ranking; (4) una señal de régimen que lleve a efectivo "
  "en crisis; (5) sector y tamaño como restricciones del portafolio.")
b("<b>Mejora futura a evaluar (opción B de la auditoría):</b> una sola definición de la estrategia en código, la misma "
  "función de exposición (tope de portafolio con datos diarios) y de costos por rotación usada por la API (campo "
  "exposicion), el monitoreo (Sharpe neto en A8/A9) y la regla de promoción, con columnas nuevas en PREDICCIONES y MONITOREO. "
  "Antes de adoptarla hay que recalcular las 5 decisiones de reentrenamiento con la métrica nueva.")
b("<b>Fuentes nuevas a evaluar:</b> un modelo de noticias y sentimiento del mercado con EDGAR Online (reportes 10-K, 10-Q y "
  "8-K de la SEC), Reddit (foros de inversión) y sitios web de finanzas, como features adicionales o como señal de régimen; "
  "habría que medir su aporte con la misma validación temporal y cuidar la fuga de información por la fecha de publicación.")
b("<b>Trazabilidad del reentrenamiento (auditoría H7):</b> la huella de la OBT no incluye el objetivo y no se guarda un "
  "manifiesto del conjunto de entrenamiento; una versión no se reconstruye exacta si cambia la OBT. Pendiente: huella con "
  "objetivo y manifiesto como artefacto de MLflow.")
CUERPO_FIN = len(story)

# ------------------------------------------------------------------ anexos
story.append(PageBreak())
INICIO = {}
story.append(CallerMacro(drawCallable=lambda fl: INICIO.setdefault("pagina", fl.canv.getPageNumber())))
p("Anexo A. Glosario", "HeadX")
table(["Término", "Qué significa en este documento"], [
    ["Alias champion / challenger / anterior", "Etiquetas del Model Registry: la versión que se sirve, la candidata y la que se sirvió antes (para revertir)."],
    ["B1, B3, B5", "Líneas base: media histórica; media por acción (regla manual); todo el universo con igual peso."],
    ["Deriva de datos / de concepto", "Cambia la distribución de las entradas / cambia la relación entre entradas y objetivo (sube el error)."],
    ["Drawdown", "Peor caída del valor del portafolio desde un máximo anterior."],
    ["Lote", "Corte transversal de un cierre de mes: todas las acciones elegibles con sus 33 features."],
    ["MAE", "Error absoluto medio del retorno predicho."],
    ["PSI", "Índice de estabilidad de la población: cuánto se movió la distribución de una feature frente al entrenamiento."],
    ["KS / chi-cuadrado", "Pruebas de igualdad de distribuciones para variables numéricas / categóricas."],
    ["Sharpe neto", "Retorno anual sobre la tasa libre de riesgo dividido para la volatilidad, después de costos."],
    ["Respaldo (fallback)", "Respuesta sin modelo: B1 como retorno y B5 como decisión, marcada en la respuesta."],
], [130, 350], size=7.5)
p("Anexo B. Modelo dimensional (Gold)", "HeadX")
figura(D / "modelo_dimensional.png", 430, "Estrellas de precios y mercado (PSet 2).")
p("Anexo C. Evidencia de CI/CD y Kestra", "HeadX")
for n, t in (("ci_verde.png", "GitHub Actions: pset4-ci en verde."), ("cd_ghcr.png", "Imagen publicada en GHCR con el hash del commit."),
             ("kestra_pausa.png", "Kestra: reentrenamiento en pausa de aprobación."), ("rollback.png", "/modelo antes y después del rollback.")):
    if (F / n).exists():
        figura(F / n, 400, t)
    else:
        p(f"[{t} Captura pendiente: docs/figuras/{n}]", "SmallX")
p("Anexo D. Cambios por las observaciones de los PSets 1–3 (docs/cambios.md)", "HeadX")
for linea in (D / "cambios.md").read_text().splitlines():
    if linea.startswith("|---") or not linea.strip():
        continue
    if linea.startswith("#"):
        p(escape(linea.lstrip("# ")).replace("`", ""), "HeadX" if linea.startswith("## ") else "BodyX")
    elif linea.startswith("|"):
        p(escape(" · ".join(x.strip() for x in linea.strip("|").split("|"))).replace("**", "").replace("`", ""), "SmallX")
    else:
        p(escape(linea).replace("**", "").replace("`", ""), "SmallX")
p("Anexos E, F y G: memos de los PSets 1 (versión con feedback), 2 y 3, en las páginas siguientes.", "BodyX")


def pie(cv, doc):
    w, _ = cv._pagesize
    cv.setStrokeColor(LINEA)
    cv.line(42, 40, w - 42, 40)
    cv.setFont("Helvetica", 8)
    cv.setFillColor(GRIS)
    cv.drawString(42, 27, "PSet 4 · Portafolio de inversiones · Gómez Ehmig")
    cv.drawRightString(w - 42, 27, "Anexo" if doc.page >= INICIO.get("pagina", 999) else str(doc.page))


import tempfile  # noqa: E402
cuerpo = Path(tempfile.gettempdir()) / "PSet4_memo_cuerpo.pdf"
doc = BaseDocTemplate(str(cuerpo), pagesize=(595, 842), title="PSet 4 - Proyecto final", author="Allan Paul Gómez Ehmig")
doc.addPageTemplates([PageTemplate(id="m", frames=[Frame(52, 50, 491, 752, leftPadding=4, rightPadding=4, topPadding=4,
                                                         bottomPadding=4)], onPageEnd=pie)])
doc.build(story)
paginas = INICIO["pagina"] - 1
assert paginas <= MAX_PAGINAS, f"El cuerpo ocupa {paginas} paginas (maximo {MAX_PAGINAS})"

from pypdf import PdfWriter  # noqa: E402
w = PdfWriter()
for f in (cuerpo, REPO / "psets/pset-01/feedback/PSet1_memo_Gomez_Ehmig_v2.pdf",
          REPO / "psets/pset-02/docs/PSet2_memo_Gomez_Ehmig.pdf", REPO / "psets/pset-03/docs/PSet3_memo_Gomez_Ehmig.pdf"):
    w.append(str(f))
salida = D / "PSet4_memo_Gomez_Ehmig.pdf"
with salida.open("wb") as fh:
    w.write(fh)
cuerpo.unlink(missing_ok=True)
print(f"Cuerpo: {paginas} paginas; total {len(w.pages)}; {salida}")
