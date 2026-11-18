"""Compara los modelos del PSet 1 en la tarea real del proyecto: pronosticar el retorno log
del MES SIGUIENTE (~21 dias habiles, igual al rebalanceo) de cada accion, en cada cierre
de mes.

Modelos (tabla "Modelos a comparar" del memo del PSet 1):
  Lineas base   rw_cero         random walk: retorno esperado 0
                rw_deriva       random walk con deriva: media historica del retorno mensual
  A (clasicos)  arima_aic       ARIMA diario sobre dif_cierre, orden elegido por AIC,
                arima_bic       y por BIC; pronostico = suma de h pasos (h = dias del mes)
                random_forest   bosque aleatorio con rezagos, volatilidad y momentum (panel)
                xgboost         gradient boosting con las mismas variables
  B (redes)     hibrido_arima_mlp   ARIMA (AIC) + red MLP que corrige su residuo [Choi 2018]
                lstm            solo si PyTorch esta instalado (si no, queda "no disponible")
                chronos         modelo fundacional zero-shot, solo si el paquete chronos-forecasting
                                y los pesos de Hugging Face estan disponibles
                timesfm, moirai quedan registrados como pendientes (ver plan.txt)

Particion (PSet 1: validacion hasta dic-2023, prueba desde ene-2024):
  entrenamiento  origenes cuyo mes objetivo termina hasta dic-2021
  validacion     objetivos de ene-2022 a dic-2023 (modelos entrenados con lo anterior)
  prueba         objetivos desde ene-2024 (modelos reentrenados con todo hasta dic-2023)
Ninguna variable usa informacion posterior al origen (cierre de mes).

Metricas (PSet 1): RMSE, MAE, acierto direccional, R2 fuera de muestra frente a rw_cero y
prueba Diebold-Mariano (con correccion de Harvey-Leybourne-Newbold) contra rw_cero sobre la
perdida cuadratica promedio de cada mes (asi se respeta la correlacion entre acciones).

Lee analisis/datos/yahoo.duckdb (series_diarias y arima_modelos, de series_y_arima.py).
Escribe:
  panel_mensual            una fila por accion y cierre de mes: variables y objetivo
  pronosticos_mensuales    pronostico de cada modelo por accion, mes y periodo
  comparacion_modelos      metricas por modelo y periodo (validacion, prueba)
  comparacion_por_accion   metricas por modelo, periodo y accion

Uso, desde psets/pset-03/ (uv sync --group analisis):
  uv run python analisis/modelos/comparar_modelos.py [--procesos 4]
"""

import argparse
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).parent
FIN_ENTRENAMIENTO = pd.Timestamp("2021-12-31")
CORTE = pd.Timestamp("2023-12-31")
VARIABLES = ["ret_m1", "ret_m2", "ret_m3", "ret_m6", "momentum_12_1", "vol_21d", "vol_63d",
             "intradia_21d", "nocturno_21d", "vol_apertura_21d"]
SEMILLA = 7


# ---------------------------------------------------------------------------------------
# Panel mensual
# ---------------------------------------------------------------------------------------

def panel_mensual(ser: pd.DataFrame) -> pd.DataFrame:
    ser = ser.sort_values(["ticker_yahoo", "fecha"]).copy()
    ser["fecha"] = pd.to_datetime(ser["fecha"])
    g = ser.groupby("ticker_yahoo")
    r = ser["dif_cierre"]
    ser["vol_21d"] = g["dif_cierre"].transform(lambda x: x.rolling(21, min_periods=15).std())
    ser["vol_63d"] = g["dif_cierre"].transform(lambda x: x.rolling(63, min_periods=40).std())
    ser["intradia_21d"] = g["intradia"].transform(lambda x: x.rolling(21, min_periods=15).mean())
    ser["nocturno_21d"] = g["nocturno"].transform(lambda x: x.rolling(21, min_periods=15).mean())
    ser["vol_apertura_21d"] = g["dif_apertura"].transform(lambda x: x.rolling(21, min_periods=15).std())
    ser["mes"] = ser["fecha"].dt.to_period("M")

    # Cierre de mes = ultimo dia bursatil del mes en el calendario comun.
    ultimos = ser.groupby("mes")["fecha"].max()
    fin = ser[ser["fecha"].isin(ultimos.values)].copy()
    fin = fin[fin["nivel_cierre"].notna()]
    fin = fin.sort_values(["ticker_yahoo", "fecha"])
    gm = fin.groupby("ticker_yahoo")
    fin["ret_mes"] = gm["nivel_cierre"].diff()          # retorno del mes que termina
    consecutivo = gm["mes"].diff().apply(lambda d: d.n if pd.notna(d) else np.nan) == 1
    fin.loc[~consecutivo, "ret_mes"] = np.nan
    for k in (1, 2, 3, 6):
        fin[f"ret_m{k}"] = gm["ret_mes"].shift(k - 1)
    fin["momentum_12_1"] = gm["ret_mes"].transform(lambda x: x.shift(1).rolling(11, min_periods=9).sum())
    fin["objetivo"] = gm["ret_mes"].shift(-1)           # retorno del mes siguiente
    sig_consec = gm["mes"].shift(-1) == fin["mes"] + 1
    fin.loc[~sig_consec, "objetivo"] = np.nan
    dias_mes = ser.groupby("mes")["fecha"].nunique()
    fin["h_dias"] = (fin["mes"] + 1).map(dias_mes)
    fin["mes_objetivo_fin"] = (fin["mes"] + 1).dt.to_timestamp(how="end").dt.normalize()
    fin["periodo"] = np.select(
        [fin["mes_objetivo_fin"] <= FIN_ENTRENAMIENTO, fin["mes_objetivo_fin"] <= CORTE],
        ["entrenamiento", "validacion"], "prueba")
    cols = ["ticker_yahoo", "fecha", "mes", "periodo", "h_dias", "objetivo", "ret_mes"] + VARIABLES
    return fin[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------------------
# ARIMA mensual a partir del modelo diario
# ---------------------------------------------------------------------------------------

def arima_mensual(args):
    """Ajusta el ARIMA diario con datos hasta fin_ajuste y pronostica, en cada origen, la
    suma de los h retornos diarios siguientes usando solo datos hasta ese origen."""
    ticker, criterio, orden, fechas, y, origenes, hs, fin_ajuste = args
    from statsmodels.tsa.arima.model import ARIMA
    fechas = pd.DatetimeIndex(fechas)
    y = np.asarray(y, dtype=float)
    m = fechas <= fin_ajuste
    if np.isfinite(y[m]).sum() < 250:
        return []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = ARIMA(y[m], order=orden, trend="c").fit()
    out = []
    for o, h in zip(origenes, hs):
        idx = int(np.searchsorted(fechas, pd.Timestamp(o), side="right"))
        if idx < 250 or not np.isfinite(h):
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rr = r.apply(y[:idx], refit=False)
            f = rr.forecast(int(h))
        out.append((ticker, pd.Timestamp(o), criterio, float(np.sum(f))))
    return out


def pronosticos_arima(ser, panel, modelos_arima, fin_ajuste, procesos):
    ordenes = modelos_arima[modelos_arima["serie"] == "dif_cierre"]
    trabajos = []
    for t, g in ser.groupby("ticker_yahoo"):
        o = panel[panel["ticker_yahoo"] == t]
        for _, fila in ordenes[ordenes["ticker_yahoo"] == t].iterrows():
            trabajos.append((t, fila.criterio, (int(fila.p), 0, int(fila.q)), g["fecha"].values,
                             g["dif_cierre"].values, o["fecha"].values, o["h_dias"].values, fin_ajuste))
    filas = []
    with ProcessPoolExecutor(max_workers=procesos) as ex:
        for res in ex.map(arima_mensual, trabajos, chunksize=2):
            filas.extend(res)
    df = pd.DataFrame(filas, columns=["ticker_yahoo", "fecha", "criterio", "pred"])
    return df.pivot_table(index=["ticker_yahoo", "fecha"], columns="criterio", values="pred").reset_index()


# ---------------------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------------------

def ajustar_y_predecir(nombre, ent, pru):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X, y, Xp = ent[VARIABLES], ent["objetivo"], pru[VARIABLES]
    if nombre == "random_forest":
        m = RandomForestRegressor(n_estimators=300, min_samples_leaf=20, max_features=0.5,
                                  n_jobs=-1, random_state=SEMILLA)
        return m.fit(X, y).predict(Xp)
    if nombre == "xgboost":
        from xgboost import XGBRegressor
        m = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8,
                         colsample_bytree=0.8, min_child_weight=20, random_state=SEMILLA)
        return m.fit(X, y).predict(Xp)
    if nombre == "hibrido_arima_mlp":
        Xh, Xph = ent[VARIABLES + ["AIC"]], pru[VARIABLES + ["AIC"]]
        m = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(16, 8), alpha=1e-2,
                                                         early_stopping=True, max_iter=500,
                                                         random_state=SEMILLA))
        m.fit(Xh, y - ent["AIC"])
        return pru["AIC"].to_numpy() + m.predict(Xph)
    raise ValueError(nombre)


def predecir_lstm(ent, pru):
    import torch  # noqa: F401  (solo si esta instalado)
    raise NotImplementedError("LSTM: instalar PyTorch y completar (ver plan.txt)")


def predecir_chronos(panel, pru):
    import torch
    from chronos import BaseChronosPipeline
    pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", device_map="cpu")
    preds = []
    for _, fila in pru.iterrows():
        hist = panel[(panel["ticker_yahoo"] == fila.ticker_yahoo) & (panel["fecha"] <= fila.fecha)]["ret_mes"].dropna()
        if len(hist) < 24:
            preds.append(np.nan)
            continue
        q, _ = pipe.predict_quantiles(context=[torch.tensor(hist.to_numpy(), dtype=torch.float32)],
                                      prediction_length=1, quantile_levels=[0.5])
        preds.append(float(q[0, 0, 0]))
    return np.array(preds)


# ---------------------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------------------

def diebold_mariano(d_t: np.ndarray, h: int = 1):
    """d_t: diferencia de perdidas (modelo - referencia) por mes. Negativo = modelo mejor."""
    d_t = d_t[np.isfinite(d_t)]
    T = len(d_t)
    if T < 6:
        return np.nan, np.nan
    var = np.var(d_t, ddof=0) / T
    dm = d_t.mean() / np.sqrt(var) if var > 0 else np.nan
    hln = dm * np.sqrt((T + 1 - 2 * h + h * (h - 1) / T) / T)
    p = 2 * stats.t.sf(abs(hln), df=T - 1)
    return float(hln), float(p)


def metricas(df: pd.DataFrame) -> dict:
    e = df["pred"] - df["objetivo"]
    sse_rw = (df["objetivo"] ** 2).sum()
    acierto = (np.sign(df["pred"]) == np.sign(df["objetivo"]))[df["pred"] != 0].mean()
    perdida = ((df["pred"] - df["objetivo"]) ** 2 - df["objetivo"] ** 2).groupby(df["fecha"]).mean()
    dm, p = diebold_mariano(perdida.to_numpy())
    return dict(n=len(df), meses=df["fecha"].nunique(), rmse=float(np.sqrt((e ** 2).mean())),
                mae=float(e.abs().mean()), acierto_direccional=float(acierto) if pd.notna(acierto) else np.nan,
                r2_fuera_muestra=float(1 - (e ** 2).sum() / sse_rw) if sse_rw > 0 else np.nan,
                dm_vs_rw_cero=dm, dm_p_valor=p)


def main():
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument("--base", default=str(AQUI.parent / "datos" / "yahoo.duckdb"))
    pa.add_argument("--procesos", type=int, default=4)
    a = pa.parse_args()

    con = duckdb.connect(a.base)
    ser = con.execute("select * from series_diarias where ticker_yahoo not like '^%'").df()
    ser["fecha"] = pd.to_datetime(ser["fecha"])
    mods = con.execute("select * from arima_modelos").df()
    panel = panel_mensual(ser)
    datos = panel.dropna(subset=["objetivo"] + VARIABLES).copy()
    print(f"Panel: {len(panel)} filas accion-mes; con objetivo y variables: {len(datos)}")

    resultados, no_disp = [], []
    fases = [("validacion", FIN_ENTRENAMIENTO, datos["periodo"] == "entrenamiento"),
             ("prueba", CORTE, datos["periodo"].isin(["entrenamiento", "validacion"]))]
    for fase, fin_ajuste, mask_ent in fases:
        print(f"[{fase}] pronosticos ARIMA por origen (la parte lenta)...")
        ar = pronosticos_arima(ser, datos, mods, fin_ajuste, a.procesos)
        d = datos.merge(ar, on=["ticker_yahoo", "fecha"], how="left")
        ent, pru = d[mask_ent.values], d[d["periodo"] == fase].copy()
        pru["pred_rw_cero"] = 0.0
        media = ent.groupby("ticker_yahoo")["objetivo"].mean()
        pru["pred_rw_deriva"] = pru["ticker_yahoo"].map(media).fillna(ent["objetivo"].mean())
        pru["pred_arima_aic"], pru["pred_arima_bic"] = pru.get("AIC"), pru.get("BIC")
        ent_h = ent.dropna(subset=["AIC"])
        for nombre in ["random_forest", "xgboost", "hibrido_arima_mlp"]:
            base_ent = ent_h if nombre == "hibrido_arima_mlp" else ent
            base_pru = pru.dropna(subset=["AIC"]) if nombre == "hibrido_arima_mlp" else pru
            try:
                pru.loc[base_pru.index, f"pred_{nombre}"] = ajustar_y_predecir(nombre, base_ent, base_pru)
                print(f"[{fase}] {nombre}: listo")
            except Exception as e:  # p. ej. xgboost sin libomp: se registra y se sigue
                no_disp.append((fase, nombre, f"{type(e).__name__}: {e}"[:200]))
                print(f"[{fase}] {nombre}: no disponible ({type(e).__name__})")
        for nombre, f in [("lstm", lambda: predecir_lstm(ent, pru)), ("chronos", lambda: predecir_chronos(panel, pru))]:
            try:
                pru[f"pred_{nombre}"] = f()
            except Exception as e:
                no_disp.append((fase, nombre, f"{type(e).__name__}: {e}"[:200]))
        for nombre in ["timesfm", "moirai"]:
            no_disp.append((fase, nombre, "pendiente: requiere pesos de Hugging Face y GPU recomendada"))
        resultados.append(pru.assign(fase=fase))

    pr = pd.concat(resultados, ignore_index=True)
    cols_pred = [c for c in pr.columns if c.startswith("pred_")]
    largo = pr.melt(id_vars=["ticker_yahoo", "fecha", "fase", "objetivo"], value_vars=cols_pred,
                    var_name="modelo", value_name="pred").dropna(subset=["pred"])
    largo["modelo"] = largo["modelo"].str.replace("pred_", "", regex=False)

    comp = [dict(fase=f, modelo=m, **metricas(g)) for (f, m), g in largo.groupby(["fase", "modelo"])]
    comp = pd.DataFrame(comp)
    por_acc = [dict(fase=f, modelo=m, ticker_yahoo=t, n=len(g),
                    rmse=float(np.sqrt(((g.pred - g.objetivo) ** 2).mean())),
                    acierto_direccional=float((np.sign(g.pred) == np.sign(g.objetivo))[g.pred != 0].mean())
                    if (g.pred != 0).any() else np.nan)
               for (f, m, t), g in largo.groupby(["fase", "modelo", "ticker_yahoo"])]
    nd = pd.DataFrame(no_disp, columns=["fase", "modelo", "motivo"])

    for nombre, df in {"panel_mensual": panel.assign(mes=panel["mes"].astype(str)),
                       "pronosticos_mensuales": largo, "comparacion_modelos": comp,
                       "comparacion_por_accion": pd.DataFrame(por_acc), "modelos_no_disponibles": nd}.items():
        con.register("df", df)
        con.execute(f"create or replace table {nombre} as select * from df")
        con.unregister("df")
    con.close()
    pd.set_option("display.width", 200)
    print(comp.sort_values(["fase", "rmse"]).round(4).to_string(index=False))
    print(nd.drop_duplicates("modelo").to_string(index=False))


if __name__ == "__main__":
    main()
