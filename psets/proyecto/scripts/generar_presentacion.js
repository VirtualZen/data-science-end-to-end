// Genera docs/PSet4_presentacion_Gomez_Ehmig.pptx: presentacion ejecutiva del proyecto final (PSet 4).
// Mismo tema que el pitch del PSet 1 y la presentacion del PSet 3. Cifras de docs/simulacion/resultado_lotes.csv
// (notebook 06). Uso, desde psets/pset-04:  node scripts/generar_presentacion.js
// (requiere pptxgenjs, react, react-dom, react-icons y sharp; PPTX_SKILL opcional para escribir el tema).
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const RAIZ = path.join(__dirname, "..");
const SALIDA = path.join(RAIZ, "docs", "PSet4_presentacion_Gomez_Ehmig.pptx");
const THEME = {
  name: "Portafolio PSet",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: { dk1: "1B2A33", lt1: "FFFFFF", dk2: "0E3B43", lt2: "EEF3F2", accent1: "0F7B6C", accent2: "E8A33D",
            accent3: "B5473A", accent4: "5B8C85", accent5: "9DB8B3", accent6: "2E4A55", hlink: "0F7B6C", folHlink: "5B8C85" },
};
const H = THEME.colors;
const PIE = "Allan Paul Gómez Ehmig · 00351916 · PSet 4 · Universo: S&P 500 ∩ NYSE; se excluyen las acciones del NASDAQ por la dificultad de comprarlas";

// --- datos lote a lote -----------------------------------------------------------------------
const filas = fs.readFileSync(path.join(RAIZ, "docs", "simulacion", "resultado_lotes.csv"), "utf8").trim().split("\n");
const cab = filas[0].split(",");
const lotes = filas.slice(1).map((l) => Object.fromEntries(l.split(",").map((v, i) => [cab[i], v])));
const riqueza = (col) => { let w = 100000; return lotes.map((r) => (w *= 1 + Number(r[col]))); };
const series = { sistema: riqueza("sistema"), b5: riqueza("b5_universo"), efectivo: riqueza("no_hacer_nada_efectivo"), fijo: riqueza("champion_fijo"), seis: riqueza("sistema_6_lotes") };
const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const etiquetas = lotes.map((r) => { const m = Number(r.anio_mes.slice(4)) % 12; const a = Number(r.anio_mes.slice(0, 4)) + (m === 0 ? 1 : 0); return `${meses[m]} ${String(a).slice(2)}`; });
// Competidores (notebook 08): misma regla de riesgo y costos, mismos lotes.
const cfil = fs.readFileSync(path.join(RAIZ, "docs", "simulacion", "competidores_por_lote.csv"), "utf8").trim().split("\n");
const ccab = cfil[0].split(",");
const manual = (() => { let w = 100000; const i = ccab.indexOf("operación manual"); return cfil.slice(1).map((l) => (w *= 1 + Number(l.split(",")[i]))); })();
series.manual = manual;
const fin = (k) => Math.round(series[k][series[k].length - 1]);
const miles = (x) => "US$ " + Math.round(x).toLocaleString("es-EC").replace(/,/g, ".");

async function icono(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Allan Paul Gómez Ehmig";
  pres.title = "PSet 4: el portafolio en operación";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

  const marco = (nombre, oscuro) => pres.defineSlideMaster({
    title: nombre,
    background: { color: oscuro ? H.dk2 : H.lt1 },
    margin: [0.4, 0.5, 0.45, 0.5],
    objects: [
      { text: { text: PIE, options: { x: 0.5, y: 5.28, w: 8.2, h: 0.25, fontSize: 8, color: oscuro ? H.accent5 : H.accent4, isTextBox: true, margin: 0 } } },
      { placeholder: { options: { name: "seccion", type: "body", x: 0.5, y: 0.28, w: 8.8, h: 0.42, fontSize: 22, bold: true,
                                   fontFace: "Cambria", color: oscuro ? H.lt1 : H.dk2, margin: 0, valign: "middle" }, text: "" } },
      { placeholder: { options: { name: "subtitulo", type: "body", x: 0.5, y: 0.72, w: 9.0, h: 0.32, fontSize: 13, italic: true,
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
  const texto = (s, t, o) => s.addText(t, { isTextBox: true, margin: 0, valign: "top", ...o });

  // I. Mensaje ---------------------------------------------------------------------------------
  pres.addSection({ title: "Mensaje" });
  let s = nueva("Mensaje", "OSCURO", "I. El portafolio, en operación", "PSet 4 · Proyecto final · Portafolio de inversiones S&P 500 ∩ NYSE",
    "Mensaje principal. Construimos el sistema completo: cada fin de mes propone al asesor 10 acciones y sus pesos, y se vigila solo. Lo pusimos a prueba con 35 meses como si fueran reales, incluida una crisis provocada a propósito. La vigilancia funcionó: detectó la crisis en el primer mes. Pero cambiar de modelo cada vez que uno nuevo ganaba un mes empeoró el resultado. El modelo original, sin cambios, terminó en 110.800 por cada 100.000, frente a 103.500 de comprar todo por igual; el efectivo, en 112.800. Y una regla sin modelo, la operación manual, que cada mes toma las 10 acciones de mejor Sharpe de 12 meses bajo la volatilidad aprobada, terminó en 128.000: le gana al modelo en la prueba real y en la simulación, aunque no en todos los años de la validación. Recomendamos ajustar: operar con la operación manual y dejar el modelo en paralelo.");
  texto(s, "La vigilancia funciona, pero una regla simple le gana al modelo", { x: 0.5, y: 1.3, w: 5.5, h: 1.55, fontFace: "Cambria", fontSize: 28, bold: true, color: H.lt1 });
  texto(s, "Recomendación: ajustar. El asesor opera con la operación manual (las 10 de mejor Sharpe bajo el riesgo aprobado); el modelo corre en paralelo y solo la reemplaza si le gana con datos reales.",
    { x: 0.5, y: 3.05, w: 5.3, h: 1.0, fontSize: 14, color: H.lt2 });
  tarjeta(s, 6.25, 1.3, 3.25, 3.6, H.accent1, "Cifras clave");
  [[miles(fin("manual")), "valor final de US$ 100.000 con la operación manual"], [miles(fin("fijo")), "con el modelo"], ["1 mes", "para detectar la crisis simulada"]]
    .forEach(([n, t], i) => {
      texto(s, n, { x: 6.5, y: 1.45 + i * 1.15, w: 2.9, h: 0.55, fontFace: "Cambria", fontSize: 24, bold: true, color: H.accent2 });
      texto(s, t, { x: 6.5, y: 1.98 + i * 1.15, w: 2.9, h: 0.45, fontSize: 12, color: H.lt1 });
    });

  // II. Problema ------------------------------------------------------------------------------
  pres.addSection({ title: "Problema" });
  s = nueva("Problema", "CONTENIDO", "II. Qué problema resolvimos y para quién", "Para el asesor que arma portafolios de inversionistas minoristas",
    "El problema del PSet 1: el inversionista minorista arma su portafolio por intuición o noticias, sin controlar el riesgo, y suele rendir menos que el índice. El asesor necesita una propuesta mensual con reglas claras. El sistema le entrega cada fin de mes 10 acciones con su peso, calculado para que las más riesgosas pesen menos, y un tope de riesgo acordado con el cliente.");
  const pr = [[fa.FaUserFriends, "Para quién", "El asesor de una casa de valores y su cliente minorista, que aprueba cada cambio."],
              [fa.FaExclamationTriangle, "El problema", "Portafolios armados por intuición, sin control del riesgo ni fecha fija de revisión."],
              [fa.FaClipboardCheck, "Lo que entrega", "Cada fin de mes: 10 acciones del S&P 500 en la NYSE, su peso y las alertas del mes."]];
  for (let i = 0; i < 3; i++) {
    const x = 0.5 + i * 3.05;
    tarjeta(s, x, 1.35, 2.85, 3.1, H.lt2, pr[i][1]);
    await circulo(s, pr[i][0], x + 0.25, 1.6, 0.6, H.accent1, "FFFFFF", "Icono " + pr[i][1]);
    texto(s, pr[i][1], { x: x + 0.25, y: 2.35, w: 2.4, h: 0.45, fontSize: 16, bold: true, color: H.dk2 });
    texto(s, pr[i][2], { x: x + 0.25, y: 2.85, w: 2.4, h: 1.5, fontSize: 13, color: H.dk1 });
  }

  // III. Que cambio en la decision ------------------------------------------------------------
  s = nueva("Problema", "CONTENIDO", "III. Qué cambió en la decisión", "De una decisión por intuición a un proceso mensual con reglas y vigilancia",
    "Antes y después. Lo importante no es solo la predicción sino el proceso: fecha fija, pesos según el riesgo, tope de riesgo, aprobación del cliente y ahora vigilancia mensual con alertas. Si el sistema falla, responde una alternativa simple y lo dice.");
  s.addTable([
    [{ text: "Paso", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Antes", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Ahora", options: { bold: true, color: H.lt1, fill: { color: H.accent1 } } }],
    ["Selección", "El asesor o el cliente eligen por noticias", "El sistema propone 10 acciones y su peso"],
    ["Riesgo", "Sin tope acordado", "Las más volátiles pesan menos; se excluye el 20 % más riesgoso; tope de riesgo del portafolio"],
    ["Revisión", "Sin fecha fija", "Cada fin de mes, con alertas si algo cambió"],
    ["Cambio de modelo", "No aplica", "Solo con aprobación de una persona"],
    ["Si algo falla", "No hay plan", "Responde una alternativa simple y lo marca"],
  ], { x: 0.5, y: 1.25, w: 9.0, colW: [1.8, 3.2, 4.0], fontSize: 12, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DEE3" },
       fill: { color: H.lt1 }, rowH: 0.55, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1] });

  // IV. Como funciona --------------------------------------------------------------------------
  pres.addSection({ title: "Resultado" });
  s = nueva("Resultado", "CONTENIDO", "IV. Cómo funciona", "Un solo circuito mensual, de los precios públicos a la propuesta",
    "La arquitectura en un diagrama. Los precios públicos se cargan cada día a la base de datos. Al cierre de mes, el modelo calcula la propuesta. Un vigilante revisa cada mes si los datos, el modelo y los resultados siguen bien. Si el modelo pierde precisión, se entrena uno nuevo, pero solo reemplaza al actual si una persona lo aprueba. El detalle técnico está en el anexo.");
  const caja = [[fa.FaDatabase, "Datos públicos", "precios diarios y composición del índice"], [fa.FaWarehouse, "Base de datos", "limpia y ordenada por acción y mes"],
                [fa.FaBrain, "Modelo", "pronostica el retorno del mes siguiente"], [fa.FaFileSignature, "Propuesta", "10 acciones y pesos para el asesor"]];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + i * 2.3;
    tarjeta(s, x, 1.35, 2.0, 2.0, i === 3 ? H.accent2 : H.lt2, caja[i][1]);
    await circulo(s, caja[i][0], x + 0.7, 1.5, 0.6, i === 3 ? H.dk2 : H.accent1, "FFFFFF", "Icono " + caja[i][1]);
    texto(s, caja[i][1], { x: x + 0.1, y: 2.2, w: 1.8, h: 0.35, fontSize: 14, bold: true, color: H.dk2, align: "center" });
    texto(s, caja[i][2], { x: x + 0.1, y: 2.58, w: 1.8, h: 0.7, fontSize: 11, color: H.dk1, align: "center" });
    if (i < 3) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 2.02, y: 2.15, w: 0.26, h: 0.35, fill: { color: H.accent4 }, line: { color: H.accent4 }, objectName: "Flecha " + i });
  }
  tarjeta(s, 0.5, 3.6, 9.0, 1.35, H.dk2, "Vigilancia");
  await circulo(s, fa.FaShieldAlt, 0.75, 3.8, 0.9, H.accent2, H.dk2, "Icono vigilancia");
  texto(s, "Vigilancia mensual", { x: 1.85, y: 3.75, w: 7.4, h: 0.4, fontSize: 15, bold: true, color: H.lt1 });
  texto(s, "Revisa que la propuesta llegue a tiempo, que los datos se parezcan a los de siempre y que el portafolio no pierda contra la alternativa simple. Si el modelo pierde precisión, propone uno nuevo y espera la aprobación de una persona.",
    { x: 1.85, y: 4.15, w: 7.4, h: 0.75, fontSize: 11.5, color: H.lt2 });

  // V. Valor ------------------------------------------------------------------------------------
  s = nueva("Resultado", "CONTENIDO", "V. Cuánto valor generó", "US$ 100.000 durante 34 meses con resultado conocido, incluida una crisis provocada",
    `Valor generado. Pasamos los meses de prueba por el sistema como si fueran reales, mes a mes. Con US$ 100.000, el modelo original sin cambios terminó en ${miles(fin("fijo"))}; comprar todo el universo por igual, en ${miles(fin("b5"))}; dejar el dinero en efectivo, en ${miles(fin("efectivo"))}. Si se cambiaba de modelo cada vez que uno nuevo ganaba un solo mes, terminó en ${miles(fin("sistema"))}: dos cambios ganaron un mes y perdieron después. Exigir medio año de ventaja para cambiar habría terminado en ${miles(fin("seis"))}. La operación manual, sin modelo, terminó en ${miles(fin("manual"))}. La caída de mayo a septiembre de 2025 incluye tres meses inventados para probar las alarmas.`);
  s.addChart(pres.charts.LINE, [
    { name: "Operación manual", labels: etiquetas, values: series.manual.map(Math.round) },
    { name: "Modelo fijo", labels: etiquetas, values: series.fijo.map(Math.round) },
    { name: "Cambiando de modelo cada mes que gana", labels: etiquetas, values: series.sistema.map(Math.round) },
    { name: "Comprar todo por igual", labels: etiquetas, values: series.b5.map(Math.round) },
    { name: "Efectivo", labels: etiquetas, values: series.efectivo.map(Math.round) },
  ], { x: 0.4, y: 1.15, w: 6.2, h: 3.95, chartColors: [H.accent6, H.accent1, H.accent3, H.accent2, H.accent5], lineSize: 2, lineDataSymbol: "none",
       showLegend: true, legendPos: "b", legendFontSize: 9, legendFontFace: "+mn-lt", valAxisMinVal: 75000, valAxisMaxVal: 160000,
       valAxisLabelFormatCode: "#,##0", catAxisLabelFontSize: 8, valAxisLabelFontSize: 9, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
       catAxisLabelColor: H.dk1, valAxisLabelColor: H.accent4, valGridLine: { color: "DDE6E4", size: 0.5 }, catGridLine: { style: "none" },
       catAxisLabelFrequency: 4, showTitle: true, title: "Valor de US$ 100.000, neto de costos", titleFontSize: 12, titleFontFace: "+mn-lt", titleColor: H.dk2 });
  tarjeta(s, 6.85, 1.15, 2.65, 3.95, H.lt2, "Resultado");
  [[miles(fin("manual")), "operación manual", H.accent6], [miles(fin("fijo")), "modelo fijo", H.accent1], [miles(fin("efectivo")), "efectivo", H.accent4], [miles(fin("b5")), "comprar todo por igual", H.accent4], [miles(fin("sistema")), "cambiando de modelo cada mes", H.accent3]].forEach(([n, t, col], i) => {
    texto(s, n, { x: 7.05, y: 1.22 + i * 0.62, w: 2.35, h: 0.35, fontFace: "Cambria", fontSize: 16, bold: true, color: col });
    texto(s, t, { x: 7.05, y: 1.55 + i * 0.62, w: 2.35, h: 0.25, fontSize: 10, color: H.dk1 });
  });
  texto(s, "La regla simple le gana al modelo en la prueba real y en la simulación; no en todos los años de la validación.",
    { x: 7.05, y: 4.35, w: 2.35, h: 0.7, fontSize: 10, italic: true, color: H.accent3 });

  // VI. Prueba de estres ------------------------------------------------------------------------
  s = nueva("Resultado", "CONTENIDO", "VI. La prueba de estrés", "Provocamos una crisis de tres meses para ver si el sistema la detecta",
    "Prueba de estrés. Entre mayo y julio de 2025 reemplazamos los datos por una crisis inventada, parecida a marzo de 2020. Las alarmas de datos y de resultados se encendieron en el primer mes. Reentrenar el modelo no ayudó: ningún modelo que elige acciones prevé una caída que golpea a todas por igual. Lo que protege al cliente es el freno de mano: pasar a la alternativa simple y revisar con el asesor.");
  const est = [[fa.FaBolt, "Qué hicimos", "Tres meses de crisis inventada: riesgo al doble y caídas de 10 % en todas las acciones."],
               [fa.FaBell, "Qué detectó", "En el primer mes: los datos cambiaron y el portafolio quedó por debajo de la alternativa simple."],
               [fa.FaRedo, "Reentrenar no bastó", "El modelo nuevo, entrenado ya con la crisis, no rindió más: la regla y una persona lo rechazaron."],
               [fa.FaHandPaper, "Qué protege", "El freno de mano: responde la alternativa simple. Probado y listo; en la simulación no se activó."]];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + i * 2.28;
    tarjeta(s, x, 1.35, 2.1, 3.55, i === 3 ? H.accent1 : H.lt2, est[i][1]);
    await circulo(s, est[i][0], x + 0.25, 1.55, 0.6, i === 3 ? H.accent2 : H.accent3, "FFFFFF", "Icono " + est[i][1]);
    texto(s, est[i][1], { x: x + 0.2, y: 2.3, w: 1.75, h: 0.55, fontSize: 14, bold: true, color: i === 3 ? H.lt1 : H.dk2 });
    texto(s, est[i][2], { x: x + 0.2, y: 2.9, w: 1.75, h: 1.9, fontSize: 12, color: i === 3 ? H.lt1 : H.dk1 });
  }

  // VII. Como se vigila --------------------------------------------------------------------------
  pres.addSection({ title: "Riesgos" });
  s = nueva("Riesgos", "CONTENIDO", "VII. Cómo se vigila", "Cada mes, cinco preguntas con una consecuencia de negocio",
    "Vigilancia. Cada mes el sistema responde tres preguntas. Una: ¿llegó la propuesta completa y a tiempo? Dos: ¿los datos del mes se parecen a los de siempre? En 2024 detectó que las tasas de interés estaban muy por encima de su historia y en abril de 2025 el choque de los aranceles. Tres: ¿el portafolio sigue igual o mejor que comprar todo por igual? Cuatro: ¿gana a la operación manual, que el sistema calcula en paralelo cada mes? Las alertas críticas llegan por correo con la acción y el responsable.");
  s.addTable([
    [{ text: "Pregunta", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Si la respuesta es no…", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Qué detectó en la simulación", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }],
    ["¿Llegó la propuesta completa y a tiempo?", "El cliente se queda sin propuesta: responde la alternativa simple y se avisa", "Ninguna falla; cada propuesta tardó menos de un segundo"],
    ["¿Los datos se parecen a los de siempre?", "La propuesta puede apoyarse en un mercado que el modelo no conoce", "Tasas de interés altas en 2024; choque de aranceles en abril de 2025; la crisis simulada"],
    ["¿Acierta igual que antes?", "Se entrena un modelo nuevo y una persona decide si lo usa", "Cinco veces; dos modelos nuevos aprobados, tres rechazados"],
    ["¿Gana a comprar todo por igual?", "Se activa el freno de mano y se revisa con el asesor", "Durante y después de la crisis simulada"],
    ["¿Gana a la operación manual?", "El asesor opera con la operación manual y el modelo queda en paralelo", "En 13 de 35 meses no (14 en la simulación): la regla simple le gana"],
  ], { x: 0.5, y: 1.2, w: 9.0, colW: [2.6, 3.2, 3.2], fontSize: 11, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DEE3" },
       fill: { color: H.lt1 }, rowH: 0.6, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1] });

  // VIII. Riesgos y retirada ------------------------------------------------------------------------
  s = nueva("Riesgos", "CONTENIDO", "VIII. Qué riesgos quedan", "Y cuándo retirar el modelo: reglas fijadas antes de que pase",
    "Riesgos que quedan. Uno: el pronóstico es débil, empata con el promedio histórico; el valor viene de la disciplina del proceso. Dos: una crisis general; el modelo no la prevé. Tres: las empresas pequeñas que el modelo elige rinden peor que el resto. Cuatro: el sistema corre en una sola computadora. Para cada uno hay una regla de retirada con una cifra.");
  const rg = [["Pronóstico débil", "Retirar si dos modelos nuevos seguidos son rechazados", fa.FaChartLine],
              ["Crisis general", "Freno de mano si pierde contra la alternativa simple 3 meses seguidos", fa.FaCloudShowersHeavy],
              ["Pérdida grande", "Pasar a efectivo si la caída supera 25 % (el cliente tolera 20 %)", fa.FaArrowDown],
              ["Empresas pequeñas", "Excluirlas si las elegidas pierden más de 2 % al mes en promedio", fa.FaBuilding]];
  for (let i = 0; i < 4; i++) {
    const y = 1.25 + i * 0.95;
    tarjeta(s, 0.5, y, 9.0, 0.8, i % 2 ? H.lt1 : H.lt2, rg[i][0]);
    await circulo(s, rg[i][2], 0.65, y + 0.1, 0.6, H.accent3, "FFFFFF", "Icono " + rg[i][0]);
    texto(s, rg[i][0], { x: 1.45, y: y + 0.22, w: 2.4, h: 0.4, fontSize: 14, bold: true, color: H.dk2 });
    texto(s, rg[i][1], { x: 3.9, y: y + 0.22, w: 5.5, h: 0.45, fontSize: 12.5, color: H.dk1 });
  }

  // IX. Recomendacion ------------------------------------------------------------------------------
  pres.addSection({ title: "Cierre" });
  s = nueva("Cierre", "OSCURO", "IX. Recomendación: ajustar, no escalar", "Operar con la operación manual y el modelo en paralelo 6 a 12 meses reales antes de decidir",
    "Recomendación: ajustar. No escalar a compra automática. El asesor opera con la operación manual, una regla de hoja de cálculo que ganó en la prueba real y en la simulación, y el modelo corre en paralelo durante 6 a 12 meses reales; solo la reemplaza si le gana durante medio año y una persona lo aprueba. Lo que se necesita: un responsable que apruebe cada cambio de modelo y vigile las alertas; agregar el sector de cada empresa para controlar concentración; una señal que lleve a efectivo en crisis; y mantener el costo bajo: hoy corre en una sola computadora con servicios gratuitos salvo la base de datos.");
  const rec = [[fa.FaUserCheck, "Operación manual", "El asesor arma el portafolio con las 10 de mejor Sharpe bajo el riesgo aprobado; el cliente aprueba."],
               [fa.FaUserShield, "Modelo en paralelo", "Propone cada mes sin decidir compras; reemplaza a la regla solo si le gana medio año y una persona lo aprueba."],
               [fa.FaLayerGroup, "Mejorar el modelo", "Sharpe de 12 meses, sector y señal de crisis; evaluar noticias y sentimiento (EDGAR, Reddit, sitios de finanzas)."],
               [fa.FaFlagCheckered, "Decidir en 12 meses", "Escalar si supera a la alternativa simple con datos reales; si no, retirar."]];
  for (let i = 0; i < 4; i++) {
    const x = 0.5 + i * 2.28;
    tarjeta(s, x, 1.35, 2.1, 3.55, H.accent6, rec[i][1]);
    await circulo(s, rec[i][0], x + 0.25, 1.55, 0.62, H.accent2, H.dk2, "Icono " + rec[i][1]);
    texto(s, rec[i][1], { x: x + 0.2, y: 2.33, w: 1.75, h: 0.55, fontSize: 15, bold: true, color: H.lt1 });
    texto(s, rec[i][2], { x: x + 0.2, y: 2.95, w: 1.75, h: 1.85, fontSize: 12, color: H.lt2 });
  }

  // X. Anexo tecnico: metricas ------------------------------------------------------------------------
  pres.addSection({ title: "Anexo" });
  s = nueva("Anexo", "CONTENIDO", "X. Anexo técnico: cifras y su consecuencia", "Para el equipo técnico; cada cifra con lo que significa para el negocio",
    "Anexo técnico con las cifras exactas y su consecuencia de negocio.");
  s.addTable([
    [{ text: "Cifra", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Valor", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }, { text: "Qué significa para el negocio", options: { bold: true, color: H.lt1, fill: { color: H.dk2 } } }],
    ["Sharpe neto, 34 meses", "0,35 operación manual · 0,05 modelo fijo · -0,23 cambiando cada mes · 0,12 con 6 meses · -0,13 todo por igual", "La regla simple da el mejor retorno por unidad de riesgo"],
    ["Retorno anual neto / peor caída", "3,7 % / -34 % fijo (efectivo 4,3 %; todo por igual 1,2 % / -27 %)", "En la crisis cae más que la alternativa: por eso el freno de mano"],
    ["Error del pronóstico (MAE)", "0,068 por mes; igual al promedio histórico (0,064 ± 0,016)", "El valor viene de la regla de riesgo, no de adivinar retornos"],
    ["Hold-out real sin crisis (PSet 3)", "Sharpe 0,87 modelo · 1,20 operación manual · 0,68 todo por igual", "La regla simple le gana al modelo"],
    ["Validación cruzada 2017-2023", "0,30 modelo · 0,50 operación manual · 0,58 media por acción · 0,54 todo por igual", "Ninguna regla gana en todos los periodos"],
    ["Tiempo de la propuesta", "42 ms por mes en producción (333 acciones)", "La propuesta está lista mucho antes de la apertura"],
    ["Pruebas automáticas", "53 pruebas en cada cambio; imagen publicada al integrar", "Un cambio que rompe la propuesta no llega a producción"],
    ["Cambios de modelo", "5 propuestos, 2 aprobados, 3 rechazados; reversión en un paso", "Ningún modelo cambia sin que una persona lo apruebe"],
  ], { x: 0.5, y: 1.15, w: 9.0, colW: [2.1, 3.7, 3.2], fontSize: 8.5, color: H.dk1, border: { type: "solid", pt: 0.5, color: "D5DEE3" },
       fill: { color: H.lt1 }, rowH: 0.4, valign: "middle", margin: [0.03, 0.06, 0.03, 0.06] });

  // XI. Anexo arquitectura -----------------------------------------------------------------------------
  s = nueva("Anexo", "CONTENIDO", "XI. Anexo técnico: arquitectura", "Kestra, dbt, Spark, Snowflake, MLflow, API FastAPI y GitHub Actions en un docker-compose",
    "Arquitectura técnica completa, para referencia del equipo técnico.");
  const img = path.join(RAIZ, "docs", "arquitectura.png");
  if (fs.existsSync(img)) s.addImage({ path: img, x: 0.4, y: 1.6, w: 9.2, h: 9.2 * 799 / 4918, altText: "Arquitectura técnica del sistema" });
  texto(s, "Detalle en el documento técnico (PSet4_memo_Gomez_Ehmig.pdf, secciones 2 a 7) y en el README del repositorio.",
    { x: 0.5, y: 4.6, w: 9.0, h: 0.4, fontSize: 11, italic: true, color: H.accent4 });

  await pres.writeFile({ fileName: SALIDA });
  if (process.env.PPTX_SKILL) await require(process.env.PPTX_SKILL + "/scripts/apply_theme.js").applyTheme(SALIDA, THEME);
  console.log("Presentacion generada:", SALIDA);
})();
