// Genera docs/PSet3_presentacion_Gomez_Ehmig.pptx: presentacion ejecutiva del PSet 3.
// Mismo tema que el pitch del PSet 1 (psets/pset-01/feedback/PSet1_pitch_Gomez_Ehmig_v2.pptx).
// Uso, desde psets/pset-03:  node scripts/generar_presentacion.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const SALIDA = path.join(__dirname, "..", "docs", "PSet3_presentacion_Gomez_Ehmig.pptx");
const THEME = {
  name: "Portafolio PSet",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: { dk1: "1B2A33", lt1: "FFFFFF", dk2: "0E3B43", lt2: "EEF3F2", accent1: "0F7B6C", accent2: "E8A33D",
            accent3: "B5473A", accent4: "5B8C85", accent5: "9DB8B3", accent6: "2E4A55", hlink: "0F7B6C", folHlink: "5B8C85" },
};
const H = THEME.colors;
const PIE = "Allan Paul Gómez Ehmig · 00351916 · 2026-11-18 · Presentación ejecutiva: PSet 3, selección del modelo";

async function icono(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Allan Paul Gómez Ehmig";
  pres.title = "PSet 3: experimentación y selección del modelo";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  const marco = (nombre, oscuro) => pres.defineSlideMaster({
    title: nombre,
    background: { color: oscuro ? H.dk2 : H.lt1 },
    margin: [0.4, 0.5, 0.45, 0.5],
    objects: [
      { text: { text: PIE, options: { x: 0.5, y: 5.28, w: 8.2, h: 0.25, fontSize: 8, color: oscuro ? H.accent5 : H.accent4, isTextBox: true, margin: 0 } } },
      { placeholder: { options: { name: "seccion", type: "body", x: 0.5, y: 0.28, w: 7.5, h: 0.42, fontSize: 22, bold: true,
                                   fontFace: "Cambria", color: oscuro ? H.lt1 : H.dk2, margin: 0, valign: "middle" }, text: "" } },
      { placeholder: { options: { name: "subtitulo", type: "body", x: 0.5, y: 0.72, w: 8.6, h: 0.32, fontSize: 13, italic: true,
                                   color: oscuro ? H.accent5 : H.accent1, margin: 0, valign: "top" }, text: "" } },
    ],
    slideNumber: { x: 9.1, y: 5.26, w: 0.4, h: 0.25, fontSize: 8, color: oscuro ? H.accent5 : H.accent4, align: "right" },
  });
  marco("CONTENIDO", false);
  marco("OSCURO", true);

  const nueva = (sec, master, seccion, subtitulo, notas) => {
    const s = pres.addSlide({ masterName: master, sectionTitle: sec });
    s.addText(seccion, { placeholder: "seccion" });
    s.addText(subtitulo, { placeholder: "subtitulo" });
    s.addNotes(notas);
    return s;
  };
  const tarjeta = (s, x, y, w, h, fill, nombre) =>
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: { color: fill }, objectName: nombre });
  const circulo = async (s, Comp, x, y, d, fondo, color, nombre) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fondo }, line: { color: fondo }, objectName: nombre });
    s.addImage({ data: await icono(Comp, color), x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52, altText: nombre });
  };
  const ejes = { catAxisLabelColor: H.dk1, valAxisLabelColor: H.accent4, catAxisLabelFontSize: 10, valAxisLabelFontSize: 9,
                 catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
                 titleFontFace: "+mn-lt", valGridLine: { color: "DDE6E4", size: 0.5 }, catGridLine: { style: "none" } };

  // 1. Titulo y mensaje principal ------------------------------------------------------------
  pres.addSection({ title: "Mensaje" });
  let s = nueva("Mensaje", "OSCURO", "I. Selección del modelo", "PSet 3 · Portafolio de inversiones S&P 500 ∩ NYSE",
    "Mensaje principal. Probamos 11 modelos y 90 ajustes registrados en MLflow. Ninguno pronostica el retorno mejor que el promedio histórico; el ganador, LightGBM, armó en la prueba final un mejor portafolio que comprar todo el universo por igual, pero esa ventaja no se confirma con el resto de la evidencia. Recomendación: registrar el modelo, no usarlo todavía para invertir y operar con una regla manual que no requiere tecnología.");
  s.addText("Ningún modelo le gana aún al promedio histórico", { x: 0.5, y: 1.35, w: 5.4, h: 1.5, fontFace: "Cambria", fontSize: 30, bold: true, color: H.lt1, isTextBox: true, margin: 0, valign: "top" });
  s.addText("Se registra el ganador, no se usa todavía para invertir y el asesor opera con una regla manual que no requiere tecnología.",
    { x: 0.5, y: 3.0, w: 5.2, h: 1.0, fontSize: 14, color: H.lt2, isTextBox: true, margin: 0, valign: "top" });
  tarjeta(s, 6.25, 1.35, 3.25, 3.55, H.accent1, "Cifras clave");
  const cifras = [["142", "corridas en MLflow"], ["11 + 90", "modelos y ajustes probados"], ["0", "superan al promedio más allá del ruido"]];
  cifras.forEach(([n, t], i) => {
    s.addText(n, { x: 6.5, y: 1.5 + i * 1.12, w: 2.8, h: 0.55, fontFace: "Cambria", fontSize: 28, bold: true, color: H.accent2, isTextBox: true, margin: 0 });
    s.addText(t, { x: 6.5, y: 2.03 + i * 1.12, w: 2.8, h: 0.4, fontSize: 12, color: H.lt1, isTextBox: true, margin: 0 });
  });

  // 2. Decision y metricas ---------------------------------------------------------------------
  pres.addSection({ title: "Planteamiento" });
  s = nueva("Planteamiento", "CONTENIDO", "II. Qué se decide y cómo se mide", "Una decisión mensual, dos métricas: una técnica y una de negocio",
    "Cada fin de mes el asesor propone 10 acciones. El modelo pronostica el retorno del mes siguiente. Se mide con dos métricas: el MAE, que es el error promedio del pronóstico, y el Sharpe neto del portafolio, que es el retorno por unidad de riesgo después de costos de 15 puntos básicos por dólar negociado. El MAE decide qué modelo gana; el Sharpe dice si sirve para el negocio.");
  const cols = [
    [fa.FaCalendarCheck, "La decisión", "Cada fin de mes, qué 10 acciones del S&P 500 que cotizan en la NYSE comprar y en qué proporción. El inversionista aprueba."],
    [fa.FaBullseye, "Métrica técnica: MAE", "Error promedio del retorno pronosticado. Menor es mejor. Es la que elige al ganador."],
    [fa.FaBalanceScale, "Métrica de negocio: Sharpe neto", "Retorno por unidad de riesgo del portafolio, después de costos (15 pb por US$) y con topes de volatilidad."],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.5 + i * 3.05;
    tarjeta(s, x, 1.35, 2.85, 3.0, H.lt2, cols[i][1]);
    await circulo(s, cols[i][0], x + 0.25, 1.6, 0.6, H.accent1, "FFFFFF", "Icono " + cols[i][1]);
    s.addText(cols[i][1], { x: x + 0.25, y: 2.35, w: 2.4, h: 0.5, fontSize: 15, bold: true, color: H.dk2, isTextBox: true, margin: 0, valign: "top" });
    s.addText(cols[i][2], { x: x + 0.25, y: 2.9, w: 2.4, h: 1.35, fontSize: 12.5, color: H.dk1, isTextBox: true, margin: 0, valign: "top" });
  }
  s.addText("Datos: 87.178 filas de acción por mes (OBT del PSet 2). Entrenamiento hasta 2023; prueba final 2024-01 a 2026-10, usada una sola vez.",
    { x: 0.5, y: 4.6, w: 9.0, h: 0.4, fontSize: 11, italic: true, color: H.accent4, isTextBox: true, margin: 0 });

  // 3. Que se probo ---------------------------------------------------------------------------
  s = nueva("Planteamiento", "CONTENIDO", "III. Qué se probó", "Del más simple al más sofisticado, con la misma preparación y la misma validación",
    "Primero tres líneas base: el promedio histórico, retorno cero y el promedio de cada acción. Luego ocho candidatos de cinco familias, incluidos tres modelos fundacionales de series de tiempo usados sin entrenar. Los tres mejores se ajustaron con 30 configuraciones cada uno. Los dos mejores fueron a la prueba final. Todo quedó en MLflow: 142 corridas.");
  const pasos = [["3", "líneas base", "promedio histórico, retorno cero, promedio por acción"],
                 ["8", "candidatos", "lineal, bagging, boosting, red neuronal y 3 fundacionales"],
                 ["90", "ajustes", "Ridge, LightGBM y XGBoost, 30 cada uno (Optuna)"],
                 ["2", "finalistas", "evaluados una sola vez en la prueba final"],
                 ["1", "ganador", "registrado como champion en MLflow"]];
  for (let i = 0; i < 5; i++) {
    const x = 0.5 + i * 1.84;
    tarjeta(s, x, 1.45, 1.66, 2.5, i === 4 ? H.accent1 : H.lt2, "Paso " + pasos[i][1]);
    s.addText(pasos[i][0], { x: x + 0.15, y: 1.6, w: 1.36, h: 0.65, fontFace: "Cambria", fontSize: 32, bold: true, color: i === 4 ? H.accent2 : H.accent1, isTextBox: true, margin: 0 });
    s.addText(pasos[i][1], { x: x + 0.15, y: 2.28, w: 1.36, h: 0.35, fontSize: 14, bold: true, color: i === 4 ? H.lt1 : H.dk2, isTextBox: true, margin: 0 });
    s.addText(pasos[i][2], { x: x + 0.15, y: 2.68, w: 1.38, h: 1.15, fontSize: 11, color: i === 4 ? H.lt1 : H.dk1, isTextBox: true, margin: 0, valign: "top" });
    if (i < 4) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + 1.69, y: 2.6, w: 0.12, h: 0.2, rotate: 0, fill: { color: H.accent5 }, line: { color: H.accent5 }, objectName: "Flecha " + i, flipH: false });
  }
  s.addText("Validación: 7 años (2017–2023), cada uno pronosticado solo con datos anteriores. Una mejora cuenta solo si supera la variación entre años.",
    { x: 0.5, y: 4.25, w: 9.0, h: 0.6, fontSize: 12.5, color: H.dk1, isTextBox: true, margin: 0 });

  // 4. Resultado tecnico ----------------------------------------------------------------------
  pres.addSection({ title: "Resultados" });
  s = nueva("Resultados", "CONTENIDO", "IV. Resultado técnico", "El mejor pronóstico empata con el promedio histórico",
    "Error promedio de validación de cada modelo, de menor a mayor. La línea base B1, el promedio histórico, tiene 0,0641. Los tres modelos ajustados quedan apenas debajo, por menos de 0,0006, mientras que el error cambia 0,016 de un año a otro. Es un empate. Con valores por defecto, ningún modelo le gana a B1.");
  const mae = [["LightGBM ajustado", 0.0636], ["Ridge ajustado", 0.0636], ["XGBoost ajustado", 0.0640], ["B1 promedio", 0.0641],
               ["B2 retorno cero", 0.0647], ["B3 prom. por acción", 0.0652], ["Chronos", 0.0670], ["Ridge", 0.0681],
               ["TimesFM", 0.0687], ["Moirai", 0.0693], ["LightGBM", 0.0706], ["XGBoost", 0.0732], ["Random forest", 0.0757], ["MLP", 0.0896]];
  s.addChart(pres.charts.BAR, [{ name: "MAE de validación", labels: mae.map(m => m[0]), values: mae.map(m => m[1]) }], {
    x: 0.4, y: 1.15, w: 5.7, h: 3.95, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: 0.05, valAxisMaxVal: 0.092,
    valAxisLabelFormatCode: "0.000", showValue: true, dataLabelFormatCode: "0.0000", dataLabelFontSize: 8, dataLabelColor: H.dk1,
    dataLabelPosition: "outEnd", showLegend: false, chartColors: [H.accent5], barGapWidthPct: 40, ...ejes, catAxisLabelFontSize: 9,
    showTitle: true, title: "MAE de validación (menor es mejor)", titleFontSize: 11, titleColor: H.dk2,
  });
  tarjeta(s, 6.4, 1.25, 3.1, 1.6, H.lt2, "Empate");
  s.addText("0,0006", { x: 6.6, y: 1.35, w: 2.8, h: 0.6, fontFace: "Cambria", fontSize: 28, bold: true, color: H.accent1, isTextBox: true, margin: 0 });
  s.addText("ventaja del mejor modelo sobre el promedio histórico", { x: 6.6, y: 1.95, w: 2.8, h: 0.8, fontSize: 12, color: H.dk1, isTextBox: true, margin: 0, valign: "top" });
  tarjeta(s, 6.4, 3.05, 3.1, 1.6, H.lt2, "Ruido");
  s.addText("0,016", { x: 6.6, y: 3.15, w: 2.8, h: 0.6, fontFace: "Cambria", fontSize: 28, bold: true, color: H.accent3, isTextBox: true, margin: 0 });
  s.addText("cuánto cambia el error solo por el año evaluado: 27 veces más", { x: 6.6, y: 3.75, w: 2.8, h: 0.8, fontSize: 12, color: H.dk1, isTextBox: true, margin: 0, valign: "top" });

  // 5. Resultado de negocio --------------------------------------------------------------------
  s = nueva("Resultados", "CONTENIDO", "V. Resultado de negocio", "En validación, la mejor regla de portafolio es la más simple",
    "Sharpe neto del portafolio de 10 acciones en los siete años de validación. La regla más simple, B3, que compra las acciones con mejor promedio histórico, logra 0,585 y le gana a todo lo demás, incluido el universo completo por igual, B5, con 0,544. Chronos queda cerca. Los modelos ajustados quedan por debajo de B5.");
  const sh = [["B3 regla simple", 0.585], ["Chronos", 0.568], ["B5 universo por igual", 0.544], ["XGBoost", 0.490], ["TimesFM", 0.457],
              ["LightGBM", 0.440], ["Moirai", 0.430], ["Ridge ajustado", 0.421], ["B4 al azar", 0.344], ["LightGBM ajustado", 0.302]];
  s.addChart(pres.charts.BAR, [{ name: "Sharpe neto", labels: sh.map(m => m[0]), values: sh.map(m => m[1]) }], {
    x: 0.4, y: 1.15, w: 5.9, h: 3.95, barDir: "bar", catAxisOrientation: "maxMin", valAxisMinVal: 0, valAxisMaxVal: 0.7,
    valAxisLabelFormatCode: "0.0", showValue: true, dataLabelFormatCode: "0.00", dataLabelFontSize: 9, dataLabelColor: H.dk1,
    dataLabelPosition: "outEnd", showLegend: false, chartColors: [H.accent2, H.accent5, H.accent4, H.accent5, H.accent5, H.accent5, H.accent5, H.accent5, H.accent4, H.accent5],
    barGapWidthPct: 40, ...ejes, showTitle: true, title: "Sharpe neto en validación, 2017–2023 (mayor es mejor)", titleFontSize: 11, titleColor: H.dk2,
  });
  tarjeta(s, 6.6, 1.25, 2.9, 3.4, H.accent1, "Lectura negocio");
  await circulo(s, fa.FaLightbulb, 6.85, 1.45, 0.55, H.lt1, H.accent1, "Icono lectura");
  s.addText([{ text: "B3 no usa ningún modelo: ", options: { bold: true } },
             { text: "ordena las acciones por su retorno promedio histórico y compra las 10 mejores, con la misma ponderación por riesgo y los mismos topes." }],
    { x: 6.85, y: 2.15, w: 2.45, h: 2.3, fontSize: 12.5, color: H.lt1, isTextBox: true, margin: 0, valign: "top" });

  // 6. Prueba final --------------------------------------------------------------------------
  s = nueva("Resultados", "CONTENIDO", "VI. Prueba final 2024–2026", "El ganador arma un buen portafolio, pero pronostica peor que el promedio",
    "Prueba final con 34 meses que el modelo nunca vio, abierta una sola vez. En pronóstico, LightGBM tiene 0,0673 de error, peor que el promedio histórico con 0,0634; Ridge empata. En portafolio, LightGBM logra un Sharpe de 0,87, mejor que el universo por igual con 0,68, pero por debajo del S&P 500 con 1,10. Como el modelo no ordena bien las acciones, con un IC prácticamente cero, y en validación su Sharpe fue 0,30, esa ventaja se trata como algo a confirmar.");
  s.addChart(pres.charts.BAR, [{ name: "Sharpe neto", labels: ["LightGBM (ganador)", "Ridge (segundo)", "B5 universo por igual", "S&P 500"], values: [0.87, -0.02, 0.68, 1.10] }], {
    x: 0.4, y: 1.15, w: 5.2, h: 3.9, barDir: "col", valAxisMinVal: -0.2, valAxisMaxVal: 1.3, valAxisLabelFormatCode: "0.0",
    showValue: true, dataLabelFormatCode: "0.00", dataLabelFontSize: 11, dataLabelColor: H.dk1, dataLabelPosition: "outEnd",
    showLegend: false, chartColors: [H.accent1, H.accent5, H.accent4, H.accent6], barGapWidthPct: 50, ...ejes,
    showTitle: true, title: "Sharpe neto en la prueba final (mayor es mejor)", titleFontSize: 11, titleColor: H.dk2,
  });
  const stats = [["0,0673", "error del ganador (B1: 0,0634)", H.accent3], ["0,87", "Sharpe del ganador (B5: 0,68)", H.accent1], ["≈ 0", "IC: no ordena bien las acciones", H.accent2]];
  stats.forEach(([n, t, col], i) => {
    tarjeta(s, 5.9, 1.2 + i * 1.3, 3.6, 1.15, H.lt2, "Cifra " + t);
    s.addText(n, { x: 6.1, y: 1.28 + i * 1.3, w: 1.4, h: 0.95, fontFace: "Cambria", fontSize: 26, bold: true, color: col, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(t, { x: 7.5, y: 1.28 + i * 1.3, w: 1.9, h: 0.95, fontSize: 12, color: H.dk1, isTextBox: true, margin: 0, valign: "middle" });
  });

  // 7. Decision ------------------------------------------------------------------------------
  pres.addSection({ title: "Decisión" });
  s = nueva("Decisión", "CONTENIDO", "VII. Decisión", "Se registra el ganador; la elección se hizo antes de abrir la prueba final",
    "El ganador es LightGBM ajustado, versión 1 con alias champion en el Model Registry; el segundo es Ridge ajustado, versión 2, alias challenger. Ganó por tener el menor error de validación, la regla fijada antes de la prueba final, pero la diferencia es un empate técnico: gana en 2 de 7 años. No se cambió la elección al ver la prueba. El modelo se recarga en una sesión limpia y reproduce exactamente su error; en otra máquina también se reproduce.");
  const dec = [[fa.FaTrophy, "Ganador: LightGBM ajustado", "Model Registry portafolio-inversiones-modelo, versión 1, alias champion. Segundo: Ridge, versión 2, challenger."],
               [fa.FaEquals, "Empate técnico", "Diferencia de 0,00006 en el error frente a 0,016 de variación entre años; gana en 2 de 7."],
               [fa.FaRedo, "Reproducible", "Recargado desde el registro da el mismo error (0,0673399888). En otra máquina, el mismo resultado."],
               [fa.FaClock, "Barato y explicable", "Entrena en segundos. La variable que más pesa es la dispersión del mes, igual para todas las acciones."]];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.85;
    tarjeta(s, x, y, 4.4, 1.65, H.lt2, dec[i][1]);
    await circulo(s, dec[i][0], x + 0.22, y + 0.25, 0.6, i === 0 ? H.accent2 : H.accent1, "FFFFFF", "Icono " + dec[i][1]);
    s.addText(dec[i][1], { x: x + 1.0, y: y + 0.18, w: 3.25, h: 0.4, fontSize: 15, bold: true, color: H.dk2, isTextBox: true, margin: 0 });
    s.addText(dec[i][2], { x: x + 1.0, y: y + 0.6, w: 3.25, h: 0.95, fontSize: 12, color: H.dk1, isTextBox: true, margin: 0, valign: "top" });
  }

  // 8. Implicaciones de negocio -----------------------------------------------------------------
  s = nueva("Decisión", "CONTENIDO", "VIII. Implicaciones para el negocio", "Una regla manual sirve de contingencia y de vara mínima",
    "Implicaciones. Hoy ningún modelo justifica su costo de operación. El valor para el asesor sigue en la disciplina: rebalanceo en fecha fija, topes de riesgo acordados y aprobación del cliente. La regla B3 se hace en una hoja de cálculo y no depende del pipeline ni del modelo: sirve si algo falla y es la vara que un modelo debe superar. Frente al índice, el S&P 500 completo ganó en la prueba final porque el universo NYSE deja fuera a las tecnológicas de NASDAQ; el servicio se justifica por el control del riesgo, no por superar al índice.");
  s.addText("Regla contingente (B3), cada fin de mes", { x: 0.5, y: 1.2, w: 4.6, h: 0.35, fontSize: 15, bold: true, color: H.dk2, isTextBox: true, margin: 0 });
  const regla = ["Ordenar las acciones del universo S&P 500 ∩ NYSE por su retorno promedio histórico",
                 "Quitar el 20 % más volátil y tomar las 10 mejores",
                 "Dar más peso a las menos volátiles; tope de 1,35 × la volatilidad del S&P 500",
                 "El asesor propone y el inversionista aprueba"];
  regla.forEach((t, i) => {
    s.addShape(pres.shapes.OVAL, { x: 0.5, y: 1.72 + i * 0.72, w: 0.42, h: 0.42, fill: { color: H.accent1 }, line: { color: H.accent1 }, objectName: "Paso regla " + (i + 1) });
    s.addText(String(i + 1), { x: 0.5, y: 1.72 + i * 0.72, w: 0.42, h: 0.42, fontSize: 14, bold: true, color: H.lt1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText(t, { x: 1.1, y: 1.68 + i * 0.72, w: 3.9, h: 0.55, fontSize: 12.5, color: H.dk1, isTextBox: true, margin: 0, valign: "middle" });
  });
  const imp = [[fa.FaTools, "Sin tecnología", "Hoja de cálculo y precios públicos; sirve si el pipeline o el modelo fallan."],
               [fa.FaRulerHorizontal, "Vara mínima", "Sharpe 0,585 en validación: un modelo debe superarla con margen claro."],
               [fa.FaChartLine, "Frente al índice", "El S&P 500 ganó (1,10): el valor está en controlar el riesgo, no en superar al índice."]];
  for (let i = 0; i < 3; i++) {
    const y = 1.2 + i * 1.22;
    tarjeta(s, 5.4, y, 4.1, 1.08, H.lt2, imp[i][1]);
    await circulo(s, imp[i][0], 5.58, y + 0.22, 0.6, H.accent1, "FFFFFF", "Icono " + imp[i][1]);
    s.addText(imp[i][1], { x: 6.35, y: y + 0.1, w: 3.05, h: 0.32, fontSize: 13.5, bold: true, color: H.dk2, isTextBox: true, margin: 0 });
    s.addText(imp[i][2], { x: 6.35, y: y + 0.42, w: 3.05, h: 0.6, fontSize: 11.5, color: H.dk1, isTextBox: true, margin: 0, valign: "top" });
  }

  // 9. Riesgos y limites --------------------------------------------------------------------------
  s = nueva("Decisión", "CONTENIDO", "IX. Límites de la evidencia", "Qué limita la conclusión y qué se hizo al respecto",
    "Límites. La señal es débil y la variación entre años es mucho mayor que las diferencias entre modelos. Se probaron muchos modelos sobre los mismos años, por eso el mejor resultado es optimista, como confirmó la prueba final. Los modelos fundacionales pueden haber visto estos precios al entrenarse. El universo usa la bolsa actual y tiene sesgo de supervivencia. La prueba final fue un periodo muy alcista.");
  s.addTable([
    [{ text: "Límite", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Qué se hizo", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }],
    ["Señal débil: la variación entre años es 27 veces la diferencia entre modelos", "Una mejora solo cuenta si supera esa variación; ninguna lo hizo"],
    ["Muchas comparaciones sobre los mismos 84 meses", "Prueba final abierta una sola vez: el error del ganador sube de 0,0636 a 0,0673"],
    ["Fundacionales que pudieron ver estos precios", "Se reportan, pero no compiten por el registro"],
    ["Universo con sesgo de supervivencia (bolsa actual)", "Documentado (H11, H16, H19); BMS y AMCR excluidas"],
    ["Prueba final muy alcista (S&P 500: 1,10)", "Se compara siempre contra el índice y el universo por igual"],
  ], { x: 0.5, y: 1.25, w: 9.0, colW: [4.5, 4.5], fontSize: 12, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DEE3" },
       fill: { color: H.lt1 }, rowH: 0.6, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1] });

  // 10. Proximos pasos -----------------------------------------------------------------------------
  pres.addSection({ title: "Cierre" });
  s = nueva("Cierre", "OSCURO", "X. Próximos pasos", "PSet 4: desplegar con disciplina y medir fuera de muestra",
    "Próximos pasos para el PSet 4. Operar con la regla contingente y dejar al ganador en paralelo, registrando cada mes su pronóstico sin decidir compras. Medir la regla B3 en la prueba final. Probar los modelos pendientes: ARIMA-GARCH y los híbridos con MLP y LSTM, el ensamble y un objetivo de ranking dentro del mes. Y desplegar el ganador en un contenedor.");
  const sig = [[fa.FaUserTie, "Operar", "Regla contingente B3 o universo por igual; el asesor propone y el cliente aprueba."],
               [fa.FaEye, "Observar", "El ganador corre en paralelo sin decidir compras; se registra su pronóstico cada mes."],
               [fa.FaFlask, "Probar", "ARIMA-GARCH, híbridos MLP y LSTM, ensamble y un objetivo de ranking dentro del mes."],
               [fa.FaBoxOpen, "Desplegar", "El champion en un contenedor, con monitoreo de error y de Sharpe."]];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + i * 2.28;
    tarjeta(s, x, 1.4, 2.1, 2.9, H.accent6, sig[i][1]);
    await circulo(s, sig[i][0], x + 0.25, 1.62, 0.62, H.accent2, H.dk2, "Icono " + sig[i][1]);
    s.addText(sig[i][1], { x: x + 0.25, y: 2.4, w: 1.7, h: 0.4, fontSize: 16, bold: true, color: H.lt1, isTextBox: true, margin: 0 });
    s.addText(sig[i][2], { x: x + 0.25, y: 2.85, w: 1.7, h: 1.75, fontSize: 12, color: H.lt2, isTextBox: true, margin: 0, valign: "top" });
  }

  await pres.writeFile({ fileName: SALIDA });
  // Opcional: escribe los colores del tema en el .pptx (todos los colores de las diapositivas ya van en hex).
  if (process.env.PPTX_SKILL) await require(process.env.PPTX_SKILL + "/scripts/apply_theme.js").applyTheme(SALIDA, THEME);
  console.log("Presentacion generada:", SALIDA);
})();
