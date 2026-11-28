"""Tablero de monitoreo (Streamlit): sistema, datos, modelo y negocio por lote, con los umbrales de las alertas.

Lee PORTAFOLIO_P4.PRODUCCION (con las variables de Snowflake de pipeline/.env) o, con --csv, los exportados de docs/
(o docs/simulacion/ si aun no hay exportados). Desde psets/pset-04/:
    uv run --project modelos --group tablero streamlit run monitoreo/tablero.py -- --csv
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ), str(RAIZ / "modelos")]
from monitoreo.alertas import PLANTILLA, UMBRAL_MAE  # noqa: E402

st.set_page_config(page_title="Monitoreo del portafolio", layout="wide")


@st.cache_data(ttl=300)
def cargar(csv: bool):
    if csv:
        base = RAIZ / "docs" if (RAIZ / "docs/monitoreo.csv").exists() else RAIZ / "docs/simulacion"
        suf = "" if base.name == "docs" else "_simulacion"
        mon, al, re = (pd.read_csv(base / f"{n}{suf}.csv") for n in ("monitoreo", "alertas", "reentrenamientos"))
    else:
        from monitoreo.produccion import leer_tabla
        mon, al, re = (leer_tabla(t, False) for t in ("MONITOREO", "ALERTAS", "REENTRENAMIENTOS"))
    for d in (mon, al, re):
        d.columns = d.columns.str.lower()
    if "metricas" in mon:
        mon = pd.DataFrame([json.loads(x) | {"modelo_version": v} for x, v in zip(mon["metricas"], mon["modelo_version"])])
    mon = mon.sort_values("anio_mes")
    mon["lote"] = mon["anio_mes"].astype(int).astype(str)
    return mon, al, re


mon, al, re = cargar("--csv" in sys.argv or os.environ.get("TABLERO_CSV") == "1")
mon["fecha"] = pd.PeriodIndex(mon["lote"], freq="M").to_timestamp()
al["fecha"] = pd.PeriodIndex(al["anio_mes"].astype(int).astype(str), freq="M").to_timestamp()
re = re.copy()
re["fecha"] = pd.PeriodIndex(re["anio_mes_llegada"].astype(int).astype(str), freq="M").to_timestamp()
re["decision"] = re["aprobado"].astype(str).str.lower().map({"true": "promovido", "false": "rechazado"}).fillna("pendiente")


def marcas(base: alt.Chart) -> alt.LayerChart:
    """Capa comun: reentrenamientos (lineas verticales, verde = promovido) y lotes sinteticos (sombra)."""
    reglas = alt.Chart(re).mark_rule(strokeDash=[4, 3]).encode(
        x="fecha:T", color=alt.Color("decision:N", scale=alt.Scale(domain=["promovido", "rechazado", "pendiente"],
                                                                     range=["#0F7B6C", "#999999", "#E8A33D"]),
                                     title="reentrenamiento"),
        tooltip=["anio_mes_llegada", "disparador", "version_challenger", "decision"])
    sint = alt.Chart(mon[mon["sintetico"].astype(bool)]).mark_rect(opacity=0.12, color="#B5473A").encode(
        x="fecha:T", x2=alt.X2("fin:T")).transform_calculate(fin="datum.fecha + 2592000000")
    return alt.layer(sint, base, reglas)


st.title("Portafolio de inversiones · monitoreo por lote")
u = mon.iloc[-1]
c = st.columns(5)
c[0].metric("Último lote", u["lote"], f"modelo v{u['modelo_version']}")
c[1].metric("MAE del último lote etiquetado", "—" if pd.isna(u["mae_ultimo"]) else f"{u['mae_ultimo']:.4f}",
            f"umbral A7 {UMBRAL_MAE:.4f}", delta_color="off")
c[2].metric("Sharpe 12 lotes", "—" if pd.isna(u["sharpe_12"]) else f"{u['sharpe_12']:.2f}",
            "" if pd.isna(u["sharpe_b5_12"]) else f"B5 {u['sharpe_b5_12']:.2f}", delta_color="off")
c[3].metric("Features con PSI crítico", int(u["n_psi_critico"]))
c[4].metric("Alertas del lote", ", ".join(al.loc[al["anio_mes"] == u["anio_mes"], "id_alerta"]) or "ninguna")

st.subheader("Alertas por lote")
st.altair_chart(marcas(alt.Chart(al).mark_point(filled=True, size=90).encode(
    x=alt.X("fecha:T", title="lote"), y=alt.Y("id_alerta:N", title="alerta"),
    shape="severidad:N", tooltip=["anio_mes", "id_alerta", "metrica", "accion"])), width="stretch")

st.subheader("Modelo: MAE con un lote de retraso")
mae = mon.melt(id_vars="fecha", value_vars=["mae_ultimo"], var_name="serie").dropna()
base = alt.Chart(mae).mark_line(point=True, color="#0F7B6C").encode(x=alt.X("fecha:T", title="lote"),
                                                                    y=alt.Y("value:Q", title="MAE"))
umbral = alt.Chart(pd.DataFrame({"u": [UMBRAL_MAE]})).mark_rule(color="#B5473A").encode(y="u:Q")
st.altair_chart(marcas(base + umbral), width="stretch")

st.subheader("Negocio: Sharpe de 12 lotes frente a B5 y a la operación manual (B7)")
sh = mon.melt(id_vars="fecha", value_vars=[c for c in ("sharpe_12", "sharpe_b5_12", "sharpe_manual_12") if c in mon],
              var_name="serie").dropna()
st.altair_chart(marcas(alt.Chart(sh).mark_line().encode(x=alt.X("fecha:T", title="lote"), y="value:Q", color="serie:N")),
                width="stretch")

col1, col2 = st.columns(2)
col1.subheader("Datos: features con PSI crítico")
col1.altair_chart(marcas(alt.Chart(mon).mark_bar(color="#5B8C85").encode(x=alt.X("fecha:T", title="lote"),
                                                                         y="n_psi_critico:Q")), width="stretch")
col2.subheader("Sistema: latencia p50 y p95 (ms)")
lat = mon.melt(id_vars="fecha", value_vars=["latencia_p50_ms", "latencia_p95_ms"], var_name="serie").dropna()
col2.altair_chart(marcas(alt.Chart(lat).mark_line(point=True).encode(x=alt.X("fecha:T", title="lote"), y="value:Q",
                                                                      color="serie:N")), width="stretch")
st.subheader("Sistema: solicitudes y errores 4xx / 5xx por lote")
err = mon.melt(id_vars="fecha", value_vars=[c for c in ("solicitudes", "errores_4xx", "errores_5xx") if c in mon],
               var_name="serie").dropna()
st.altair_chart(marcas(alt.Chart(err).mark_bar(opacity=0.8).encode(
    x=alt.X("fecha:T", title="lote"), y=alt.Y("value:Q", title="peticiones"), color="serie:N",
    xOffset="serie:N")), width="stretch")
st.subheader("Alertas")
st.dataframe(al[["anio_mes", "id_alerta", "severidad", "metrica", "accion", "quien_la_recibe"]], width="stretch")
st.subheader("Reentrenamientos")
st.dataframe(re.drop(columns=["fecha"]), width="stretch")
with st.expander("Plantilla de alertas"):
    st.dataframe(PLANTILLA, width="stretch")
