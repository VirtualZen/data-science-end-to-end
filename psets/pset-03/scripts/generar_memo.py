"""Genera docs/PSet3_memo_Gomez_Ehmig.pdf (6 paginas + anexos) y docs/memo/PSet3_memo_fuente.txt.

Mismo formato que el memo del PSet 2 (psets/pset-02/scripts/generar_memo.py). Las tablas de resultados se leen
de docs/candidatos.csv, docs/tuning_*.csv y docs/holdout_finalistas.csv; el texto se edita aqui.
Uso, desde psets/pset-03:
  uv run python scripts/generar_memo.py
"""
from pathlib import Path
import csv
from xml.sax.saxutils import escape
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, Image, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

R = Path(__file__).resolve().parents[1]
D = R / 'docs'
F = D / 'figuras'
AZUL, GRIS, LINEA = colors.HexColor('#17384D'), colors.HexColor('#526775'), colors.HexColor('#D5DEE3')
PAGINAS_CUERPO = 6  # se recalcula abajo con la pagina donde empieza el anexo A

cand = {r['modelo']: r for r in csv.DictReader((D / 'candidatos.csv').open())}
ho = {r['rol']: r for r in csv.DictReader((D / 'holdout_finalistas.csv').open())}
tun = {}
for m in ('M3_lightgbm', 'M4_ridge', 'M3b_xgboost'):
    filas = list(csv.DictReader((D / f'tuning_{m}.csv').open()))
    tun[m] = min(filas, key=lambda r: float(r['mae_cv_media']))


def c(x, d=4):
    """Numero con coma decimal (estilo del memo)."""
    return f'{float(x):.{d}f}'.replace('.', ',')


st = getSampleStyleSheet()
st.add(ParagraphStyle('TitleX', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=AZUL, spaceAfter=6))
st.add(ParagraphStyle('BodyX', fontName='Helvetica', fontSize=9.3, leading=12.4, spaceAfter=5))
st.add(ParagraphStyle('SmallX', fontName='Helvetica', fontSize=7.6, leading=9.4, spaceAfter=4))
st.add(ParagraphStyle('CapX', fontName='Helvetica-Oblique', fontSize=7.6, leading=9.4, textColor=GRIS, spaceAfter=7))
st.add(ParagraphStyle('HeadX', fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=AZUL, spaceBefore=7, spaceAfter=4))
st.add(ParagraphStyle('BulX', parent=st['BodyX'], leftIndent=11, bulletIndent=2, spaceAfter=2.5))
st.add(ParagraphStyle('BoxX', parent=st['BodyX'], backColor=colors.HexColor('#EEF4F7'), borderPadding=(6, 6, 6, 6),
                      borderColor=colors.HexColor('#C9D8E0'), borderWidth=0.6, spaceBefore=4, spaceAfter=10))
story, plain = [], []


def p(text, sty='BodyX'):
    story.append(Paragraph(text.replace('&', '&amp;'), st[sty]))
    plain.append(text)


def b(text):
    story.append(Paragraph(text.replace('&', '&amp;'), st['BulX'], bulletText='•'))
    plain.append('- ' + text)


def h(text):
    p(text, 'HeadX')


def table(headers, rows, widths, size=7.4, negrita=()):
    sty = ParagraphStyle('t', fontName='Helvetica', fontSize=size, leading=size + 1.8)
    sth = ParagraphStyle('th', parent=sty, fontName='Helvetica-Bold')
    data = [[Paragraph(escape(str(x)), sth) for x in headers]]
    for i, row in enumerate(rows):
        data.append([Paragraph(escape(str(x)), sth if i in negrita else sty) for x in row])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E7F0F5')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('LINEBELOW', (0, 0), (-1, 0), .7, AZUL), ('LINEBELOW', (0, 1), (-1, -1), .3, LINEA),
                           ('TOPPADDING', (0, 0), (-1, -1), 2.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
                           ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]))
    story.append(t)
    story.append(Spacer(1, 6))
    plain.append('\n'.join(' | '.join(str(v) for v in r) for r in [headers] + rows))


def figura(nombre, ancho, texto, titulo=None):
    im = Image(str(F / nombre))
    s = ancho / im.imageWidth
    im.drawWidth, im.drawHeight = im.imageWidth * s, im.imageHeight * s
    partes = [Paragraph(titulo, st['HeadX'])] if titulo else []
    story.append(KeepTogether(partes + [im, Spacer(1, 2), Paragraph(texto.replace('&', '&amp;'), st['CapX'])]))
    plain.extend(([titulo] if titulo else []) + [texto])


# ---------------------------------------------------------------- portada y resumen
p('PSet 3 | Experimentación y selección del modelo', 'TitleX')
p('Allan Paul Gómez Ehmig · 00351916<br/>MSDS 6003 · USFQ · Verificación: 18 de noviembre de 2026 (Ecuador)', 'SmallX')
p('<b>Decisión que apoya el modelo.</b> Cada fin de mes, el asesor propone al inversionista qué 10 acciones del S&P 500 '
  'que cotizan en la NYSE comprar y en qué proporción. El modelo pronostica el retorno de cada acción en el mes '
  'siguiente; con ese pronóstico se eligen las 10 mejores y se ponderan según su riesgo (más peso a las menos '
  'volátiles). Los datos son la OBT mensual del PSet 2: 87.178 filas de acción por mes (Snowflake, base '
  'PORTAFOLIO_P3). <b>Resultado:</b> ningún modelo pronostica mejor que el promedio histórico. El modelo ganador '
  '(LightGBM) armó en la prueba final un portafolio mejor que comprar todo el universo por igual, pero esa ventaja '
  'no se confirma con el resto de la evidencia. <b>Recomendación:</b> registrar el modelo, no usarlo todavía para '
  'invertir, y operar con una regla manual que no requiere tecnología (sección 7). Los términos marcados se explican '
  'en el glosario (anexo A).', 'BoxX')

# ---------------------------------------------------------------- 1. EDA
h('1. EDA')
p('Se revisaron tamaño, tipos, faltantes, estadística descriptiva, la distribución del objetivo, atípicos por IQR y '
  'Z-score, y la relación de cada variable con el objetivo por Spearman, que no supone normalidad y resiste las colas '
  'gruesas del retorno (notebooks/01_eda.ipynb, figuras en el anexo B). Los hallazgos que cambian el experimento:')
table(['Hallazgo', 'Evidencia', 'Qué cambia en el modelo'], [
    ['Retornos con meses extremos', 'Curtosis en exceso 9,6; 1,27 % de filas a 3 o más desviaciones (en una normal, 0,27 %)',
     'Se mide el error con MAE, que no se deja dominar por pocos meses extremos; no se borran los extremos'],
    ['El mes pesa más que la acción', 'El mes explica el 34,5 % de la variación del retorno',
     'Validación por meses completos; se mide si el modelo ordena bien las acciones dentro de cada mes (IC); se crea la variable dispersion_mes'],
    ['Señal débil para ordenar acciones', 'Ninguna de 28 variables tiene una relación significativa (|t| ≥ 2) con el retorno dentro del mes',
     'Se esperan mejoras pequeñas; una mejora solo cuenta si supera la variación entre pliegues'],
    ['Variables repetidas', '23 pares con correlación mayor a 0,9 y 4 combinaciones exactas',
     'Modelos con regularización; selección de variables (SelectKBest) dentro del Pipeline en el tuning'],
    ['Riesgo muy distinto entre acciones', 'Volatilidad anual de 14,8 % (p10) a 41,3 % (p90)',
     'Escalado dentro del Pipeline; ponderación por riesgo y topes de volatilidad en el portafolio'],
    ['Casi sin faltantes', '0 de 33 variables con nulos tras excluir BMS y AMCR',
     'Huecos intermedios: interpolación por acción a cada lado del corte; extremos: mediana dentro del Pipeline'],
], [118, 165, 197])
figura('eda_target_distribucion.png', 330, 'Figura 1. Distribución del retorno del mes siguiente: colas más gruesas que una '
       'normal. Boxplots de atípicos y mapa de calor de Spearman en el anexo B.')
p('BMS y AMCR se excluyen (H19): el pipeline trata la compra de Bemis por Amcor como un cambio de símbolo y AMCR '
  '2012–2014 tiene precios de solo cierre (109 filas).', 'SmallX')

# ---------------------------------------------------------------- 2. Features
h('2. Features')
p('Se usan las 33 variables numéricas de la OBT y dos derivadas. Las dos se conocen al cierre del mes de decisión, '
  'antes de comprar, así que existen en el momento de la inferencia:')
b('<b>dispersion_mes</b> (sale del hallazgo 2): cuánto se separan entre sí los retornos de todas las acciones en el '
  'mes que acaba de cerrar (desviación estándar entre acciones). Usa solo datos de ese mes.')
b('<b>mes_calendario_obj</b>: el mes del calendario que se quiere pronosticar (enero a diciembre), que se sabe de '
  'antemano. Al ser categórica se codifica con one-hot de 12 categorías fijas, enero como referencia; un valor '
  'desconocido produce un error en lugar de pasar en silencio.')
p('<b>Evidencia:</b> en los 7 pliegues, las dos juntas bajan el MAE de LightGBM en 0,0012 y lo mejoran en los 7 años; '
  'en Ridge lo bajan en 0,0014 (5 de 7). Otras cuatro candidatas no mejoraron y se descartaron (anexo B2). '
  '<b>Sin fuga:</b> quedan fuera los precios ajustados en nivel, que cambian con dividendos futuros, y sigue_en_sp500, '
  'que describe el presente. Las 28 pruebas de tests/ pasan, entre ellas test_dispersion_solo_usa_el_mes, '
  'test_mes_calendario_del_objetivo y test_interpolacion_no_cruza_el_corte.')

# ---------------------------------------------------------------- 3. Preparacion y validacion
h('3. Preparación y validación')
p('<b>División única.</b> Entrenamiento: meses objetivo hasta diciembre de 2023, 46.851 filas, para validación cruzada, '
  'comparación y tuning. Prueba (hold-out): enero de 2024 a octubre de 2026, 11.326 filas y 34 meses, usada una sola '
  'vez al final. Imputación, escalado, one-hot y selección de variables están en el Pipeline de src/pipeline.py, que '
  'los notebooks importan, y se ajustan solo con el entrenamiento de cada pliegue.')
p('<b>Validación cruzada temporal</b> (TimeSeriesSplit sobre meses): 7 pliegues; cada uno entrena con todo el pasado y '
  'valida el año siguiente (2017 a 2023, 84 meses), dejando un mes de separación porque las variables de 21 a 252 días '
  'se traslapan. Se eligió porque el modelo siempre pronosticará el futuro con datos del pasado. Los esquemas que '
  'mezclan meses dan un error un 27 % menor, que no es real: entrenan con el mismo mes que validan.')
table(['Esquema (LightGBM)', 'MAE de CV', 'Filas validadas cuyo mes estaba en el entrenamiento'], [
    ['TimeSeriesSplit por meses (elegido)', '0,0651 ± 0,0177', '0 %'],
    ['TimeSeriesSplit por filas', '0,0670 ± 0,0139', '3,3 %'],
    ['KFold aleatorio (5)', '0,0476 ± 0,0004', '100 %'],
    ['GroupKFold por acción (5)', '0,0475 ± 0,0022', '100 %'],
], [170, 90, 220], negrita=(0,))
p('<b>Métricas.</b> La técnica, igual para todos los modelos, es el <b>MAE</b>: el error promedio del retorno '
  'pronosticado, en puntos de retorno logarítmico. RMSE, R<super>2</super>, acierto de dirección e IC se registran pero no '
  'deciden. La de negocio es el <b>Sharpe neto</b> del portafolio: retorno ganado por cada unidad de riesgo, después de '
  'costos. Refleja el error más costoso del proyecto, comprar acciones que caen y concentrar riesgo, porque mide la '
  'regla completa:')
b('cada mes, las 10 acciones con mayor pronóstico, con más peso a las menos volátiles (1/vol de 63 días);')
b('<b>tope relativo:</b> no se compra el 20 % más volátil del mes; <b>tope del portafolio:</b> como máximo 1,35 veces la '
  'volatilidad del S&P 500, y lo que exceda queda en efectivo, que rinde la tasa libre de riesgo;')
b('costo de 15 pb por cada US$ comprado o vendido; todo en US$. Se reporta junto con la peor caída (drawdown).')

# ---------------------------------------------------------------- 4. Diseno experimental
h('4. Diseño experimental')
p('MLflow corre en Docker (localhost:5001, SQLite como backend y carpeta de artefactos). El experimento '
  '<b>portafolio-inversiones</b> tiene 142 corridas, exportadas a docs/corridas.csv:')
table(['Fase', 'Corridas', 'Mínimo del PDF'], [
    ['Líneas base', 'B1 promedio histórico, B2 retorno cero, B3 promedio de cada acción', '2'],
    ['Referencias de negocio', 'B4 al azar (200 sorteos), B5 todo el universo por igual, índices S&P 500 y NYSE', '—'],
    ['Candidatos', '8: cinco familias y tres modelos fundacionales', '5'],
    ['Tuning', '3 corridas padre con 30 hijas cada una: 90 configuraciones', '90'],
    ['Final', '2: ganador y segundo en la prueba final', '1'],
], [95, 330, 55])
p('<b>Qué guarda cada corrida:</b> hiperparámetros y semilla 42; tabla de origen, fecha y sha256 del snapshot; MAE, '
  'RMSE y demás métricas en entrenamiento y por pliegue, con su promedio y desviación; IC, Sharpe neto y bruto, '
  'drawdown y segundos; los tags fase, familia, modelo y commit de Git; y el Pipeline entrenado con firma y ejemplo de '
  'entrada. Las corridas con problemas no se borraron: tienen fase = descartada y su motivo (docs/corridas_descartadas.md). '
  'Son una prueba de TimesFM con 500 filas (0,94 % de cobertura), reemplazada por la corrida eff5db04 con 26.750 '
  'pronósticos; una prueba previa al pipeline final; registros repetidos de B1, B2 y B5; y un tuning de XGBoost '
  'que falló porque dos procesos compartían un archivo temporal, y que se repitió.')
figura('mlflow_comparacion.png', 480, 'Figura 2. Comparación de líneas base, candidatos y B5 en MLflow, ordenados por MAE de CV '
       '(filtro: fase distinta de tuning, final y descartada).')

# ---------------------------------------------------------------- 5. Resultados
h('5. Resultados')
p('Todos los candidatos usan la misma preparación, los mismos 7 pliegues y la misma métrica, con hiperparámetros '
  'por defecto y semilla 42. Los fundacionales se usan sin entrenar (zero-shot): reciben los últimos 512 días de cada '
  'acción y pronostican los 21 siguientes. Un LLM por prompting no se probó: ya conoce los precios de 2017–2026, así que '
  'su "pronóstico" sería memoria y no hay forma de cortarla en la fecha de decisión (notebook 03, sección 6.4).')
LR = {'M3_lightgbm': '0,1', 'M3b_xgboost': '0,3', 'M5_mlp': '0,001'}
INF = {'M8_chronos': 'inferencia 23', 'M9_timesfm': 'inferencia 2.884', 'M10_moirai': 'inferencia 252'}
NOM = {'B1_media': ('B1 promedio histórico', 'línea base'), 'B2_rw_cero': ('B2 retorno cero', 'línea base'),
       'B3_rw_deriva': ('B3 promedio por acción', 'línea base'), 'M8_chronos': ('M8 Chronos-Bolt', 'fundacional'),
       'M4_ridge': ('M4 Ridge', 'lineal'), 'M9_timesfm': ('M9 TimesFM 2.5', 'fundacional'),
       'M10_moirai': ('M10 Moirai 2.0', 'fundacional'), 'M3_lightgbm': ('M3 LightGBM', 'boosting'),
       'M3b_xgboost': ('M3b XGBoost', 'boosting'), 'M2_random_forest': ('M2 Random Forest', 'bagging'),
       'M5_mlp': ('M5 MLP', 'red neuronal')}
filas = []
for m in sorted(NOM, key=lambda k: float(cand[k]['mae_cv_media'])):
    r = cand[m]
    sh = r['negocio_sharpe_neto']
    filas.append([NOM[m][0], NOM[m][1], c(r['mae_train_cv']), f"{c(r['mae_cv_media'])} ± {c(r['mae_cv_std'])}",
                  c(r['brecha_mae'], 3), LR.get(m, '—'), INF.get(m, c(r['segundos_entrenamiento'], 1)),
                  c(sh, 3) if sh else '—'])
table(['Modelo', 'Familia', 'MAE entrena', 'MAE CV (± desv.)', 'Brecha', 'Learning rate', 'Segundos', 'Sharpe neto CV'],
      filas, [88, 58, 50, 78, 40, 48, 62, 56])
p('Referencias de negocio en CV: B5 (todo el universo por igual) 0,544; B4 (al azar) 0,344; índice S&P 500 0,626.', 'SmallX')
figura('resultados_modelos.png', 470, 'Figura 3. MAE de CV (media ± desviación) y Sharpe neto de todos los modelos, con su '
       'versión por defecto y ajustada. Líneas punteadas: B1 y B5.')
p('<b>Lectura.</b> Con hiperparámetros por defecto, <b>ningún candidato pronostica mejor que B1</b>, el promedio '
  'histórico; tampoco superan a la vez a B1 y a B5, lo que queda como hallazgo. Los árboles memorizan el '
  'entrenamiento: el random forest tiene un error de 0,015 en entrenamiento y de 0,076 en validación (brecha 0,061). Los '
  'fundacionales quedan cerca de B1 sin entrenar nada. En el portafolio, solo B3 (0,585) y Chronos (0,568) superan a B5.')

# ---------------------------------------------------------------- 6. Tuning
h('6. Tuning')
p('Se ajustan los tres mejores modelos que tienen hiperparámetros: Ridge, LightGBM y XGBoost (los fundacionales no se '
  'entrenan). Se usó <b>Optuna</b> con muestreador TPE y semilla 42: con 30 intentos en un espacio de hasta 10 '
  'dimensiones, una búsqueda exhaustiva no cabe y una aleatoria desperdicia intentos; TPE concentra los siguientes '
  'donde el error fue menor. Cada configuración es una corrida hija en MLflow y se evalúa con los mismos 7 pliegues. '
  'Espacio: tasa de aprendizaje 0,005–0,2, número de árboles 50–1000, regularización 0,001–100 y alpha de Ridge '
  '0,001–100.000, en escala logarítmica porque su efecto es multiplicativo; profundidad y fracciones de filas y '
  'columnas, en escala lineal; tipo de pérdida (cuadrática, absoluta o Huber), número de variables (10, 20, 30 o '
  'todas) y rango dentro del mes, como categorías. Detalle en src/tuning.py y notebooks/04_tuning.ipynb.')
t3 = []
for m, nom, conf in (('M3_lightgbm', 'LightGBM', '63 árboles, tasa 0,021, pérdida absoluta, 10 variables'),
                     ('M4_ridge', 'Ridge', 'alpha 47.651, todas las variables, rango dentro del mes'),
                     ('M3b_xgboost', 'XGBoost', '51 árboles, tasa 0,016, profundidad 3, 10 variables')):
    d, a = cand[m], tun[m]
    mejora = float(d['mae_cv_media']) - float(a['mae_cv_media'])
    t3.append([nom, c(d['mae_cv_media']), f"{c(a['mae_cv_media'])} ± {c(a['mae_cv_std'])}", c(mejora),
               f"no ({c(d['mae_cv_std'], 3)})", conf, c(a['negocio_sharpe_neto'], 3)])
table(['Modelo', 'MAE por defecto', 'MAE ajustado', 'Mejora', '¿Supera la desviación?', 'Mejor configuración', 'Sharpe CV'],
      t3, [48, 50, 72, 40, 62, 150, 58])
figura('tuning_historia.png', 440, 'Figura 4. MAE de CV de cada una de las 30 configuraciones y mejor acumulado, por modelo.')
p('<b>Lectura.</b> Los tres mejoran, pero <b>ninguna mejora supera la variación entre pliegues</b>, así que según el '
  'criterio del PDF no cuentan como mejora. Se debe notar hacia dónde empuja la búsqueda: pocos árboles, tasas bajas y '
  'mucha regularización (en Ridge, alpha de 47.651), o sea, modelos que se acercan a predecir casi lo mismo para todas '
  'las acciones. Por eso los ajustados quedan apenas debajo de B1, por menos de 0,0006: un empate con el promedio.')

# ---------------------------------------------------------------- 7. Decision
h('7. Decisión')
ch, cl = ho['champion'], ho['challenger']
table(['', 'Ganador (champion)', 'Segundo (challenger)'], [
    ['Modelo', 'M3 LightGBM ajustado', 'M4 Ridge ajustado'],
    ['Corrida (run_id) del tuning', tun['M3_lightgbm']['run_id'], tun['M4_ridge']['run_id']],
    ['Corrida en la prueba final', ch['run_id'], cl['run_id']],
    ['Model Registry portafolio-inversiones-modelo', 'versión 1, alias champion', 'versión 2, alias challenger'],
    ['MAE de CV', f"{c(tun['M3_lightgbm']['mae_cv_media'], 5)} ± {c(tun['M3_lightgbm']['mae_cv_std'])}",
     f"{c(tun['M4_ridge']['mae_cv_media'], 5)} ± {c(tun['M4_ridge']['mae_cv_std'])}"],
    ['MAE en la prueba final (B1: 0,0634)', c(ch['mae_holdout']), c(cl['mae_holdout'])],
    ['Acierto de dirección / IC en la prueba', f"{c(float(ch['acierto_direccional_holdout']) * 100, 1)} % / {c(ch['ic_media_holdout'], 3)}",
     f"{c(float(cl['acierto_direccional_holdout']) * 100, 1)} % / {c(cl['ic_media_holdout'], 3)}"],
    ['Sharpe neto en la prueba (B5: 0,68; S&P 500: 1,10)', c(ch['negocio_sharpe_neto_holdout'], 2), c(cl['negocio_sharpe_neto_holdout'], 2)],
    ['Peor caída / retorno anual neto', f"{c(float(ch['negocio_drawdown_max_holdout']) * 100, 1)} % / {c(float(ch['negocio_retorno_anual_neto_holdout']) * 100, 1)} %",
     f"{c(float(cl['negocio_drawdown_max_holdout']) * 100, 1)} % / {c(float(cl['negocio_retorno_anual_neto_holdout']) * 100, 1)} %"],
    ['Entrenamiento (7 pliegues) / predicción', '8,9 s / 0,0045 ms por fila', '5,8 s / 0,0033 ms por fila'],
], [150, 165, 165], size=7.2, negrita=(0,))
figura('holdout.png', 400, 'Figura 5. Prueba final (2024-01 a 2026-10): MAE frente a B1 (el eje no empieza en cero) y Sharpe neto '
       'frente a B5 y al S&P 500.')
b('<b>Por qué gana LightGBM:</b> tiene el menor MAE de CV, la regla fijada antes de abrir la prueba. La diferencia con '
  'Ridge es de 0,00006 frente a una variación entre pliegues de 0,016: gana en 2 de 7 años y el t pareado es 0,07. '
  '<b>No supera la variación entre pliegues; es un empate técnico.</b>')
b('<b>En la prueba final</b>, Ridge tiene mejor MAE (empata con B1) y LightGBM mejor Sharpe (0,87 frente a 0,68 de B5). '
  'No se cambió la elección después de ver la prueba, para no usarla como una segunda validación.')
b('<b>Costo y explicabilidad:</b> ambos entrenan en segundos y predicen al instante. Ridge se explica con sus '
  'coeficientes; LightGBM, con la importancia de cada variable. En los dos domina dispersion_mes, que es igual para '
  'todas las acciones del mes: el modelo aprende sobre todo el nivel general del mes siguiente y no qué acción rinde '
  'más que otra. Eso explica un IC cercano a cero.')
b('<b>Reproducibilidad:</b> notebooks/06_champion.ipynb carga models:/portafolio-inversiones-modelo@champion en una '
  'sesión limpia y obtiene MAE 0,0673399888, igual al registrado. En otra máquina (Linux, entorno creado desde uv.lock) '
  'el MAE de CV del champion, de B1 y de Ridge se reproduce exactamente (docs/reproducibilidad.md).')
p('<b>Implicaciones de negocio.</b>')
b('<b>El valor para el asesor sigue en la disciplina del proceso</b>, no en la predicción: rebalanceo en fecha fija, '
  'topes de volatilidad acordados con el cliente y su aprobación antes de cada cambio. Hoy ningún modelo justifica el '
  'costo de operarlo (pipeline, Snowflake, servidor de modelos y monitoreo).')
b('<b>Estrategia contingente sin tecnología:</b> la regla de B3. Cada mes, el asesor ordena las acciones del universo '
  'común S&P 500 ∩ NYSE por su retorno promedio histórico, toma las 10 mejores y aplica la misma ponderación por riesgo y '
  'los mismos topes. Se hace en una hoja de cálculo con precios públicos. En CV logró el mejor Sharpe neto del '
  'experimento (0,585, frente a 0,544 de B5 y 0,568 de Chronos). Sirve de plan si el pipeline o el modelo fallan y de '
  'vara mínima: un modelo solo justifica su costo si la supera con un margen mayor que la variación entre pliegues. Su '
  'Sharpe en la prueba final queda por medir.')
b('<b>Frente al índice:</b> en la prueba final, comprar el S&P 500 completo (1,10) le gana a toda estrategia limitada a la '
  'NYSE, que deja fuera a las grandes tecnológicas de NASDAQ. El servicio se justifica por el control del riesgo y la '
  'personalización, no por superar al índice.')
b('<b>Recomendación:</b> operar con la regla contingente o con el universo por igual (B5), y dejar al ganador corriendo '
  'en paralelo sin decidir compras, registrando cada mes su pronóstico, hasta tener evidencia fuera de muestra.')

# ---------------------------------------------------------------- 8. Limitaciones
h('8. Limitaciones')
b('<b>Señal débil.</b> La variación entre pliegues (0,016) es más de 25 veces la diferencia entre los mejores modelos; '
  'ninguna elección se distingue estadísticamente. Ya el EDA anticipaba relaciones de 0,02 como máximo.')
b('<b>Muchas comparaciones.</b> 8 candidatos, 3 líneas base y 90 configuraciones sobre los mismos 84 meses: el mejor '
  'resultado de CV es optimista. La prueba final lo confirma: el MAE del ganador sube de 0,0636 a 0,0673.')
b('<b>Fundacionales posiblemente contaminados.</b> Chronos, TimesFM y Moirai se entrenaron con series públicas que pueden '
  'incluir los precios de validación; se reportan, pero no compiten por el registro (tampoco son un Pipeline reentrenable).')
b('<b>Universo con sesgo de supervivencia.</b> El filtro NYSE usa la bolsa de hoy (H11: 20,8 % de símbolos sin precios) y '
  'las fusiones se tratan como cambio de símbolo (H16, H19).')
b('<b>Periodo de prueba muy alcista</b> (S&P 500 con Sharpe 1,10): los topes de volatilidad y el efectivo castigan a '
  'todos los portafolios frente al índice.')
b('<b>Reproducibilidad.</b> El snapshot de datos no va en Git; se vuelve a crear desde Snowflake y su sha256 cambia si '
  'el pipeline cargó días nuevos. LightGBM por defecto varía en 0,00005 entre procesadores por sumas en paralelo.')
b('<b>Pendiente para el PSet 4:</b> ARIMA-GARCH y los híbridos con MLP y LSTM (M1, M6, M7), el ensamble por rangos, las '
  'pruebas Diebold-Mariano y Wilcoxon con ajuste de Holm (src/evaluacion.py) y un objetivo de ranking dentro del mes.')
CUERPO = len(story)

# ---------------------------------------------------------------- Anexos
story.append(PageBreak())
from reportlab.platypus.flowables import CallerMacro
INICIO_ANEXO = {}
story.append(CallerMacro(drawCallable=lambda fl: INICIO_ANEXO.setdefault('pagina', fl.canv.getPageNumber())))
p('Anexo A. Glosario', 'HeadX')
glos = [
    ('Acierto de dirección', 'Porcentaje de veces que el modelo acierta si el retorno sube o baja.'),
    ('Alias champion / challenger', 'Etiquetas del Model Registry: champion es el modelo ganador; challenger, el segundo, que queda listo para reemplazarlo.'),
    ('Bagging / boosting', 'Formas de combinar muchos árboles de decisión: en bagging cada árbol se entrena por separado con una muestra distinta (random forest); en boosting cada árbol corrige los errores del anterior (LightGBM, XGBoost).'),
    ('Brecha', 'Diferencia entre el error en validación y en entrenamiento. Una brecha grande indica que el modelo memoriza los datos en lugar de aprender (sobreajuste).'),
    ('Corrida / corrida hija', 'Un entrenamiento registrado en MLflow con sus parámetros, métricas y archivos. En el tuning, cada configuración es una corrida hija agrupada bajo una corrida padre por modelo.'),
    ('Drawdown', 'Peor caída del valor del portafolio desde un máximo anterior hasta un mínimo posterior.'),
    ('Fuga de datos', 'Usar en el entrenamiento información que no existiría en el momento de decidir, por ejemplo datos del mes que se quiere pronosticar. Hace que el modelo parezca mejor de lo que es.'),
    ('Hiperparámetro', 'Ajuste del modelo que no se aprende de los datos y se fija antes de entrenar, por ejemplo el número de árboles o la tasa de aprendizaje.'),
    ('Hold-out (prueba final)', 'Datos que se separan al inicio y se usan una sola vez al final para medir al ganador y al segundo, sin influir en ninguna decisión.'),
    ('IC (coeficiente de información)', 'Correlación de Spearman, dentro de cada mes, entre el orden pronosticado de las acciones y el orden real de sus retornos, promediada en todos los meses. 0 significa que el modelo no ordena mejor que el azar.'),
    ('Learning rate (tasa de aprendizaje)', 'Cuánto corrige el modelo en cada paso del entrenamiento. Más baja es más lenta y más prudente.'),
    ('Línea base', 'Regla sencilla que todo modelo debe superar para valer la pena: B1 promedio histórico, B2 retorno cero, B3 promedio de cada acción.'),
    ('MAE', 'Error absoluto medio: en promedio, cuánto se aleja el retorno pronosticado del real. Menor es mejor.'),
    ('MLflow / Model Registry', 'Herramienta que guarda cada corrida con sus datos, métricas y modelo; el Model Registry guarda versiones de los modelos elegidos con alias.'),
    ('Modelo fundacional / zero-shot', 'Modelo grande ya entrenado por otra empresa con millones de series (Chronos, TimesFM, Moirai) que se usa sin entrenarlo con nuestros datos.'),
    ('OBT', 'One Big Table: la tabla única de acción por mes que construyó el pipeline del PSet 2.'),
    ('One-hot', 'Forma de convertir una categoría (el mes) en columnas de 0 y 1, una por categoría.'),
    ('Optuna / TPE', 'Librería de búsqueda de hiperparámetros; TPE elige la siguiente configuración según dónde salió mejor el error en las anteriores.'),
    ('pb (punto básico)', 'Centésima parte de 1 %: 15 pb = 0,15 % de cada US$ comprado o vendido.'),
    ('Pipeline', 'Cadena de pasos (rellenar faltantes, escalar, codificar, seleccionar variables y modelo) que se ajusta como una sola pieza con los datos de entrenamiento.'),
    ('Pliegue / validación cruzada', 'Partición de los datos de entrenamiento: el modelo se entrena con una parte y se evalúa con otra; aquí 7 veces, cada una con un año distinto de validación.'),
    ('Regularización', 'Penalización que obliga al modelo a ser más sencillo para que no memorice; en Ridge la controla alpha.'),
    ('Retorno logarítmico', 'Logaritmo de (precio final / precio inicial); para retornos pequeños es casi igual al porcentual.'),
    ('Sharpe neto', 'Retorno anual del portafolio por encima de la tasa libre de riesgo, dividido para su volatilidad, después de costos. Mayor es mejor.'),
    ('Snapshot y sha256', 'Copia fija de la OBT en un archivo; el sha256 es su huella digital: si cambia un dato, cambia la huella.'),
    ('t pareado', 'Prueba que compara dos modelos año por año; valores cercanos a 0 indican que no hay diferencia.'),
    ('Variación entre pliegues', 'Desviación estándar del MAE entre los 7 años de validación; mide cuánto cambia el resultado solo por el año evaluado.'),
    ('Volatilidad', 'Desviación estándar de los retornos diarios, anualizada; mide el riesgo de la acción.'),
]
table(['Término', 'Qué significa en este memo'], [[a, b_] for a, b_ in glos], [115, 365], size=7.6)
for titulo, nombre, ancho, texto in (
        ('Anexo B1. EDA: atípicos (IQR) y correlación de Spearman', 'eda_atipicos_boxplots.png', 430, 'Diagramas de caja de las variables principales.'),
        (None, 'eda_correlacion_spearman.png', 380, 'Correlación de Spearman entre variables: bloques de variables casi repetidas.'),
        ('Anexo B2. Ablación de features', 'features_ablacion.png', 430, 'Cambio en el MAE al agregar cada feature derivada, en los 7 pliegues.'),
        ('Anexo B3. Pliegues de la validación temporal', 'validacion_pliegues.png', 430, 'Entrenamiento creciente, un mes de separación y un año de validación.'),
        ('Anexo B4. Brecha entre entrenamiento y validación', 'candidatos_brecha.png', 400, 'Diagnóstico de sobreajuste de los candidatos.'),
        ('Anexo B5. Importancia de hiperparámetros (LightGBM)', 'tuning_M3_lightgbm_importancia.png', 330, 'Según Optuna.'),
        ('Anexo B6. Líneas base y referencias de negocio', 'lineas_base_negocio.png', 430, 'Valor de US$ 100.000 invertidos al inicio de 2017, neto de costos.')):
    figura(nombre, ancho, texto, titulo)
p('Anexo C. Cómo reproducir', 'HeadX')
b('MLflow: docker compose up -d mlflow, con Kestra y Spark apagados. Snowflake: copiar .env.example a .env y llenar la '
  'cuenta y la llave; uv run python -m src.datos crea el snapshot y su manifiesto con sha256.')
b('Entorno: uv sync --group modelos (o requirements.txt). Notebooks, en orden: 01_eda, 02_features, '
  '03_preparacion_validacion, 03_baseline_candidatos, 04_tuning, 05_seleccion y 06_champion.')
b('Fundacionales: src/modelos/fundacionales.py (comandos en el README). Tuning: python -m src.tuning --modelo <m> '
  '--trials 30. Verificación: python -m src.verificar_reproducibilidad y pytest tests.')


def footer(cv, doc):
    w, _ = cv._pagesize
    cv.setStrokeColor(LINEA)
    cv.line(42, 40, w - 42, 40)
    cv.setFont('Helvetica', 8)
    cv.setFillColor(GRIS)
    cv.drawString(42, 27, 'PSet 3 · Portafolio de inversiones · Gómez Ehmig')
    cv.drawRightString(w - 42, 27, 'Anexo' if doc.page >= INICIO_ANEXO.get('pagina', 99) else str(doc.page))


doc = BaseDocTemplate(str(D / 'PSet3_memo_Gomez_Ehmig.pdf'), pagesize=(595, 842),
                      title='PSet 3 - Experimentación y selección del modelo', author='Allan Paul Gómez Ehmig')
doc.addPageTemplates([PageTemplate(id='memo', frames=[Frame(52, 50, 491, 752, leftPadding=4, rightPadding=4,
                                                              topPadding=4, bottomPadding=4)], onPageEnd=footer)])
doc.build(story)
assert INICIO_ANEXO['pagina'] - 1 <= PAGINAS_CUERPO, f"El cuerpo ocupa {INICIO_ANEXO['pagina'] - 1} paginas (maximo 6)"
print('Paginas del cuerpo:', INICIO_ANEXO['pagina'] - 1)
(D / 'memo').mkdir(exist_ok=True)
(D / 'memo' / 'PSet3_memo_fuente.txt').write_text('\n\n'.join(plain))
print('Memo generado:', D / 'PSet3_memo_Gomez_Ehmig.pdf')
