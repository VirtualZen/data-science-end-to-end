"""Pasos de produccion que corre Kestra (contenedor pset4-produccion), uno por subcomando:

  lote         lee el lote del mes de la OBT (Snowflake), lo manda a POST /predecir y guarda PREDICCIONES
  monitorear   metricas del lote (sistema, datos, modelo) -> MONITOREO y ALERTAS; salida para Kestra
  reentrenar   challenger con la ventana expansiva de lotes etiquetados -> MLflow (@challenger) y REENTRENAMIENTOS
  decision     registra la aprobacion o el rechazo humano del challenger
  promover     mueve @champion a la version aprobada y pide a la API que recargue el alias
  revertir     vuelve @champion a @anterior (rollback) y recarga la API

Uso local, desde psets/pset-04/ (con pipeline/.env cargado y la API y MLflow arriba):
  uv run --project modelos python -m monitoreo.produccion lote --anio-mes 202505
Con --obt modelos/data/obt_p4.parquet se lee el snapshot en vez de Snowflake (y no se escribe en Snowflake:
las tablas van a docs/produccion/*.csv).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
for p in (RAIZ, RAIZ / "modelos"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.pipeline import FEATURES, FEATURES_OBT, dividir, preparar  # noqa: E402

from .alertas import evaluar  # noqa: E402
from .deriva import Referencia, ReferenciaSalida  # noqa: E402
from .simulacion import etiquetar, etiquetas, lote_del_mes, meses_produccion, metricas_lote  # noqa: E402

ESQUEMA = "PRODUCCION"
NOMBRE = "portafolio-inversiones-modelo"
SALIDA_LOCAL = Path(os.environ.get("PRODUCCION_LOCAL", RAIZ / "docs" / "produccion"))


# ------------------------------------------------------------------ E/S
def _conexion():
    import snowflake.connector
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"], user=os.environ["SNOWFLAKE_USER"],
        private_key=base64.b64decode(os.environ["SNOWFLAKE_PRIVATE_KEY"]),
        role=os.environ.get("SNOWFLAKE_ROLE", "PSET2_ROL"), warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "PSET2_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "PORTAFOLIO_P4"), schema=ESQUEMA)


def leer_obt(ruta: str | None) -> tuple[pd.DataFrame, str]:
    if ruta:
        obt = pd.read_parquet(ruta)
    else:
        with _conexion() as con, con.cursor() as cur:
            cur.execute("SELECT * FROM OBT.OBT_ACCION_MES ORDER BY ACCION_KEY, ANIO_MES")
            obt = cur.fetch_pandas_all()
        obt.columns = [c.lower() for c in obt.columns]
    huella = hashlib.md5(pd.util.hash_pandas_object(obt[["accion_key", "anio_mes"] + FEATURES_OBT], index=False)
                         .values.tobytes()).hexdigest()[:12]
    return obt, huella


def leer_tabla(tabla: str, local: bool, where: str = "") -> pd.DataFrame:
    if local:
        f = SALIDA_LOCAL / f"{tabla.lower()}.csv"
        return pd.read_csv(f) if f.exists() else pd.DataFrame()
    with _conexion() as con, con.cursor() as cur:
        cur.execute(f"SELECT * FROM {ESQUEMA}.{tabla} {where}")
        d = cur.fetch_pandas_all()
    d.columns = [c.lower() for c in d.columns]
    return d


def escribir(tabla: str, d: pd.DataFrame, local: bool, borrar_mes: int | None = None) -> None:
    """Agrega filas. Con borrar_mes primero borra las de ese anio_mes, aunque no haya filas nuevas: re-ejecutar un
    lote no duplica, y un reproceso sin alertas deja el lote sin alertas (ALERTAS es el estado vigente por lote; el
    historial de cada corrida queda en los logs de Kestra)."""
    if d.empty and borrar_mes is None:
        return
    if local:
        SALIDA_LOCAL.mkdir(parents=True, exist_ok=True)
        f = SALIDA_LOCAL / f"{tabla.lower()}.csv"
        previo = pd.read_csv(f) if f.exists() else pd.DataFrame()
        if borrar_mes is not None and len(previo):
            previo = previo[previo["anio_mes"] != borrar_mes]
        pd.concat([previo, d], ignore_index=True).to_csv(f, index=False)
        return
    from snowflake.connector.pandas_tools import write_pandas
    with _conexion() as con:
        if borrar_mes is not None:
            con.cursor().execute(f"DELETE FROM {ESQUEMA}.{tabla} WHERE ANIO_MES = %s", (borrar_mes,))
        if d.empty:
            return
        out = d.copy()
        out.columns = [c.upper() for c in out.columns]
        write_pandas(con, out, tabla, schema=ESQUEMA, quote_identifiers=False, use_logical_type=True)


def _http(metodo: str, url: str, cuerpo: dict | None = None, token: str | None = None) -> dict:
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    if token:
        req.add_header("X-Token", token)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _salida_kestra(**kw) -> None:
    print("::" + json.dumps({"outputs": kw}, default=str) + "::")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _datos(args):
    """OBT del cierre y entrenamiento del PSet 3 (dividir(preparar(...)), solo para la referencia de deriva y
    el reentrenamiento). Los lotes se arman con preparar_inferencia: sin objetivo ni meses posteriores."""
    obt, huella = leer_obt(args.obt)
    entrenamiento, _ = dividir(preparar(obt))
    return obt, huella, entrenamiento


# ------------------------------------------------------------------ subcomandos
def lote(args) -> None:
    obt, huella, _ = _datos(args)
    d = lote_del_mes(obt, args.anio_mes)
    if d.empty:
        raise SystemExit(f"La OBT no tiene acciones elegibles para {args.anio_mes}")
    validas = d.dropna(subset=FEATURES_OBT)
    peticion = {"anio_mes": int(args.anio_mes), "acciones": [
        {"accion_key": str(r.accion_key), "ticker": str(r.ticker), **{c: float(getattr(r, c)) for c in FEATURES_OBT}}
        for r in validas.itertuples()]}
    r = _http("POST", f"{args.api}/predecir", peticion)
    entradas = validas.set_index("accion_key")[FEATURES_OBT].to_dict("index")
    m = r["modelo"]
    filas = pd.DataFrame([{
        "id_prediccion": a["id_prediccion"], "id_lote": r["id_lote"], "timestamp_utc": _ahora(),
        "anio_mes": r["anio_mes"], "mes_objetivo": r["mes_objetivo"], "accion_key": a["accion_key"],
        "ticker": a["ticker"], "entradas": json.dumps(entradas[a["accion_key"]]),
        "retorno_predicho": a["retorno_predicho"], "decision": a["decision"], "peso": a["peso"],
        "decision_manual": a["decision_operacion_manual"], "peso_manual": a["peso_operacion_manual"],
        "modelo_nombre": m["nombre"], "modelo_version": m["version"], "modelo_alias": m["alias"],
        "run_id": m["run_id"], "respaldo": m["respaldo"], "usado": r["usado"], "latencia_ms": r["latencia_ms"],
        "sintetico": bool(d["sintetico"].any()), "huella_obt": huella} for a in r["acciones"]])
    filas["timestamp_utc"] = pd.to_datetime(filas["timestamp_utc"])
    escribir("PREDICCIONES", filas, args.obt is not None, borrar_mes=int(args.anio_mes))
    print(f"lote {args.anio_mes}: {len(filas)} predicciones (version {m['version']}, {r['n_incluidas']} incluidas, "
          f"{len(d) - len(validas)} filas con nulos no enviadas)")
    _salida_kestra(anio_mes=args.anio_mes, predicciones=len(filas), invalidas=len(d) - len(validas),
                   version=m["version"], respaldo=m["respaldo"])


def monitorear(args) -> None:
    obt, _, entrenamiento = _datos(args)
    local = args.obt is not None
    pred = leer_tabla("PREDICCIONES", local)
    pred = pred[pred["anio_mes"] <= args.anio_mes]
    if pred.empty or args.anio_mes not in set(pred["anio_mes"]):
        raise SystemExit(f"No hay predicciones del lote {args.anio_mes}: correr primero el subcomando lote")
    meses = sorted(int(x) for x in pred["anio_mes"].unique())
    e = etiquetas(obt)
    servidos = []
    for mes in meses:
        g = lote_del_mes(obt, mes)
        p = pred[pred["anio_mes"] == mes][["accion_key", "retorno_predicho", "peso", "decision", "modelo_version",
                                           "peso_manual", "decision_manual"]]
        servidos.append(g.merge(p.rename(columns={"retorno_predicho": "pred"}), on="accion_key", how="inner"))
    completo, lote_m = lote_del_mes(obt, args.anio_mes), servidos[-1]
    hist = etiquetar(pd.concat(servidos[:-1]), e) if len(servidos) > 1 else None
    import mlflow
    champion = mlflow.sklearn.load_model(f"models:/{NOMBRE}@champion")
    ref = Referencia(entrenamiento, FEATURES)
    salida = ReferenciaSalida(champion.predict(entrenamiento[FEATURES + ["anio_mes"]]),
                              entrenamiento["anio_mes"].to_numpy())
    # Sistema: ventana desde 30 s antes del envio del lote (timestamp de sus predicciones) hasta ahora.
    desde = (pd.to_datetime(pred.loc[pred["anio_mes"] == args.anio_mes, "timestamp_utc"], utc=True).min()
             - pd.Timedelta(seconds=30))
    sis = {"latencia_p50_ms": None, "latencia_p95_ms": None, "solicitudes": None, "errores_4xx": None,
           "errores_5xx": None}
    try:
        s = _http("GET", f"{args.api}/metricas?desde={desde.isoformat().replace('+00:00', 'Z')}")["sistema"]
        sis = {"latencia_p50_ms": s["predecir_p50_ms"], "latencia_p95_ms": s["predecir_p95_ms"],
               "solicitudes": s["solicitudes"], "errores_4xx": s["errores_4xx"], "errores_5xx": s["errores_5xx"]}
    except Exception as ex:  # el monitoreo de datos y modelo sigue aunque la API no conteste
        print(f"aviso: /metricas no respondio ({ex}); las metricas de sistema del lote quedan vacias")
    sis["pct_invalidas"] = 100 * (len(completo) - len(lote_m)) / max(len(completo), 1)
    ventana = pd.concat(servidos[-12:])
    m = metricas_lote(ref, salida, completo, lote_m, hist, ventana, sis)
    version = str(lote_m["modelo_version"].iloc[0])
    deriva = ref.evaluar(completo, ventana)
    ahora = pd.Timestamp.now(tz="UTC")
    fila = {k: m.get(k) for k in ("anio_mes", "n_acciones", "n_enviadas", "pct_invalidas", "latencia_p50_ms",
                                  "latencia_p95_ms", "solicitudes", "errores_4xx", "errores_5xx", "pct_nulos_max",
                                  "n_features_fuera_rango", "categorias_no_vistas", "n_psi_critico", "psi_max",
                                  "feature_psi_max", "z_pred_media", "tasa_incluir", "mae_ultimo", "mae_penultimo",
                                  "sharpe_12", "sharpe_b5_12", "sharpe_manual_12", "retorno_manual_ultimo",
                                  "coinciden_manual")}
    fila.update({"timestamp_utc": ahora, "modelo_version": version, "sintetico": m["sintetico"],
                 "metricas": json.dumps(m, default=float), "deriva": deriva.to_json(orient="records")})
    escribir("MONITOREO", pd.DataFrame([fila]), local, borrar_mes=int(args.anio_mes))
    alertas = pd.DataFrame([{**a, "timestamp_utc": ahora, "modelo_version": version} for a in evaluar(m)])
    escribir("ALERTAS", alertas, local, borrar_mes=int(args.anio_mes))
    ids = [] if alertas.empty else alertas["id_alerta"].tolist()
    criticas = [] if alertas.empty else alertas.loc[alertas["severidad"] == "critico", "id_alerta"].tolist()
    dispara, motivo = disparo(args.anio_mes, meses, local)
    print(f"lote {args.anio_mes}: alertas {ids or 'ninguna'}; MAE ultimo/penultimo = {m['mae_ultimo']}/{m['mae_penultimo']}; "
          f"reentrenar: {motivo or 'no'}")
    _salida_kestra(anio_mes=args.anio_mes, alertas=",".join(ids), criticas=",".join(criticas),
                   dispara_reentrenamiento=dispara, motivo=motivo or "", llegada=siguiente_mes(args.anio_mes),
                   version=version, resumen=f"Lote {args.anio_mes}: alertas {', '.join(ids) or 'ninguna'}")


def siguiente_mes(anio_mes: int) -> int:
    p = pd.Period(str(anio_mes), freq="M") + 1
    return p.year * 100 + p.month


def disparo(anio_mes: int, meses_servidos: list, local: bool) -> tuple[bool, str | None]:
    """Regla de reentrenamiento (la misma de monitoreo.simulacion), evaluada al cerrar el monitoreo del lote t;
    el challenger se entrena al llegar t+1 con las etiquetas que ya se conocen (lotes hasta t). Rendimiento: alguna A7 desde el ultimo reentrenamiento. Calendario: 12 lotes etiquetados desde el
    ultimo. Enfriamiento: al menos 3 lotes etiquetados nuevos desde el ultimo (para tener con que comparar).
    La deriva de datos (A4, A5) sola no dispara."""
    from .simulacion import CALENDARIO, ENFRIAMIENTO
    reent = leer_tabla("REENTRENAMIENTOS", local)
    llegada = siguiente_mes(anio_mes)
    ultimo = int(reent["anio_mes_llegada"].max()) if len(reent) else int(min(meses_servidos))
    etiquetados_desde = len([x for x in meses_servidos if ultimo <= x < llegada])
    if len(reent) and etiquetados_desde < ENFRIAMIENTO:
        return False, None
    al = leer_tabla("ALERTAS", local)
    a7 = len(al) and ((al["id_alerta"] == "A7") & (al["anio_mes"] >= ultimo) & (al["anio_mes"] <= anio_mes)).any()
    if a7:
        return True, "rendimiento (A7)"
    if etiquetados_desde >= CALENDARIO:
        return True, "calendario (12 lotes)"
    return False, None


def reentrenar(args) -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    from src.reentrenar import entrenar_y_comparar, registrar_challenger
    obt, huella, entrenamiento = _datos(args)
    e = etiquetas(obt)
    # Solo lotes cuyo objetivo ya llego: los anteriores a la llegada, tal como se sirvieron (sin objetivo ni
    # interpolacion con meses posteriores) unidos con su objetivo.
    nuevos = [etiquetar(lote_del_mes(obt, m), e) for m in meses_produccion(obt) if m < args.anio_mes_llegada]
    etiquetados = pd.concat([entrenamiento] + nuevos, ignore_index=True)
    cli = MlflowClient()
    mv = cli.get_model_version_by_alias(NOMBRE, "champion")
    champion = mlflow.sklearn.load_model(f"models:/{NOMBRE}@champion")
    challenger, comp = entrenar_y_comparar(champion, etiquetados)
    version = registrar_challenger(challenger, comp, args.motivo, huella, ejemplo=etiquetados)
    run_id = cli.get_model_version(NOMBRE, version).run_id
    fila = {"timestamp_utc": pd.Timestamp.now(tz="UTC"), "anio_mes_llegada": args.anio_mes_llegada,
            "disparador": args.motivo, "version_champion": mv.version, "version_challenger": version,
            "run_id_challenger": run_id, "hasta_anio_mes": comp.hasta_anio_mes,
            "lotes_evaluacion": ",".join(map(str, comp.lotes_evaluacion)), "mae_champion": comp.mae_champion,
            "mae_challenger": comp.mae_challenger, "retorno_champion": comp.retorno_champion,
            "retorno_challenger": comp.retorno_challenger, "promueve_regla": comp.promueve,
            "motivo_regla": comp.motivo, "aprobado": None, "aprobado_por": None, "motivo_decision": None}
    escribir("REENTRENAMIENTOS", pd.DataFrame([fila]), args.obt is not None)
    print(json.dumps(comp.como_dict(), default=str, indent=1))
    _salida_kestra(version_challenger=version, version_champion=mv.version, promueve=comp.promueve,
                   lotes_evaluacion=",".join(map(str, comp.lotes_evaluacion)),
                   motivo_regla=comp.motivo, mae_champion=round(comp.mae_champion, 5),
                   mae_challenger=round(comp.mae_challenger, 5),
                   retorno_champion=round(comp.retorno_champion, 4),
                   retorno_challenger=round(comp.retorno_challenger, 4))


def decision(args) -> None:
    """Deja constancia de la decision humana (tarea Pause de reentrenamiento.yml) en REENTRENAMIENTOS."""
    aprobado = args.aprobado.lower() in ("true", "1", "si", "yes")
    if args.obt is not None:
        f = SALIDA_LOCAL / "reentrenamientos.csv"
        d = pd.read_csv(f, dtype={"aprobado": object, "aprobado_por": object, "motivo_decision": object})
        d.loc[d["version_challenger"].astype(str) == str(args.version), ["aprobado", "aprobado_por", "motivo_decision"]] = [
            aprobado, args.por, args.motivo]
        d.to_csv(f, index=False)
    else:
        with _conexion() as con:
            con.cursor().execute(f"UPDATE {ESQUEMA}.REENTRENAMIENTOS SET APROBADO = %s, APROBADO_POR = %s, "
                                 "MOTIVO_DECISION = %s WHERE VERSION_CHALLENGER = %s",
                                 (aprobado, args.por, args.motivo, str(args.version)))
    print(f"challenger v{args.version}: {'APROBADO' if aprobado else 'rechazado'} por {args.por} ({args.motivo})")


def promover(args) -> None:
    from src.reentrenar import promover as mover
    r = mover(args.version)
    info = _http("POST", f"{args.api}/recargar", {}, os.environ.get("API_TOKEN"))
    print(f"@champion -> v{r['champion']} (anterior v{r['anterior']}); la API sirve v{info['version']}")
    _salida_kestra(**r, version_api=info["version"])


def revertir(args) -> None:
    from mlflow.tracking import MlflowClient
    c = MlflowClient()
    actual = c.get_model_version_by_alias(NOMBRE, "champion").version
    destino = args.version or c.get_model_version_by_alias(NOMBRE, "anterior").version
    c.set_registered_model_alias(NOMBRE, "anterior", actual)
    c.set_registered_model_alias(NOMBRE, "champion", destino)
    info = _http("POST", f"{args.api}/recargar", {}, os.environ.get("API_TOKEN"))
    print(f"rollback: @champion v{actual} -> v{destino}; la API sirve v{info['version']}")


def exportar(args) -> None:
    """Evidencia del PDF (seccion Repositorio) en docs/: predicciones.csv, monitoreo.csv y alertas.csv desde
    PORTAFOLIO_P4.PRODUCCION; corridas.csv con todas las corridas del experimento (mlflow.search_runs, incluidas
    las de reentrenamiento); reentrenamientos.csv con las corridas de fase=reentrenamiento, unidas por run_id a
    la decision humana de la tabla REENTRENAMIENTOS (aprobado, por quien y motivo)."""
    import mlflow
    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)
    for t in ("PREDICCIONES", "MONITOREO", "ALERTAS"):
        d = leer_tabla(t, False)
        d.sort_values([c for c in ("anio_mes", "timestamp_utc") if c in d][:1]).to_csv(
            destino / f"{t.lower()}.csv", index=False)
        print(f"{t}: {len(d)} filas -> {destino / (t.lower() + '.csv')}")
    corridas = mlflow.search_runs(experiment_names=[os.environ.get("MLFLOW_EXPERIMENT_NAME", "portafolio-inversiones")])
    corridas.to_csv(destino / "corridas.csv", index=False)
    print(f"corridas: {len(corridas)} filas -> {destino / 'corridas.csv'}")
    reent = corridas[corridas.get("tags.fase", pd.Series(dtype=str)) == "reentrenamiento"]
    decisiones = leer_tabla("REENTRENAMIENTOS", False).rename(columns={"run_id_challenger": "run_id"})
    reent = reent.merge(decisiones, on="run_id", how="left").sort_values("start_time")
    reent.to_csv(destino / "reentrenamientos.csv", index=False)
    print(f"reentrenamientos (fase=reentrenamiento + decision): {len(reent)} filas -> {destino / 'reentrenamientos.csv'}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--obt", help="snapshot parquet de OBT_ACCION_MES (sin Snowflake; escribe en docs/produccion/)")
    p.add_argument("--api", default=os.environ.get("API_URL", "http://api:8000"))
    sub = p.add_subparsers(dest="cmd", required=True)
    for nombre in ("lote", "monitorear"):
        s = sub.add_parser(nombre)
        s.add_argument("--anio-mes", type=int, required=True)
    s = sub.add_parser("reentrenar")
    s.add_argument("--anio-mes-llegada", type=int, required=True)
    s.add_argument("--motivo", default="rendimiento (A7)")
    s = sub.add_parser("promover")
    s.add_argument("--version", required=True)
    s = sub.add_parser("decision")
    s.add_argument("--version", required=True)
    s.add_argument("--aprobado", required=True)
    s.add_argument("--por", default="revisor")
    s.add_argument("--motivo", default="")
    s = sub.add_parser("exportar")
    s.add_argument("--destino", default=str(RAIZ / "docs"))
    s = sub.add_parser("revertir")
    s.add_argument("--version")
    args = p.parse_args()
    {"lote": lote, "monitorear": monitorear, "reentrenar": reentrenar, "promover": promover,
     "revertir": revertir, "decision": decision,
     "exportar": exportar}[args.cmd](args)


if __name__ == "__main__":
    main()
