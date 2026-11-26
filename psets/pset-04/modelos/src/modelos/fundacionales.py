"""M8-M10: modelos fundacionales en zero-shot (fase pesada, una vez; resultado en artefactos/).

Contexto: los ultimos `contexto` retornos log diarios hasta el cierre del mes t (dias
observados). Pronostico: 21 dias; el retorno del mes es la suma de las medianas diarias y la
dispersion de los cuantiles da una medida de incertidumbre. Los modelos normalizan cada
ventana por su cuenta (escalado por instancia, al estilo RevIN), asi que no se ajusta ningun
escalador con datos futuros.

Riesgos documentados en docs/diseno_experimental.md:
  - Contaminacion: si el corpus de preentrenamiento incluye precios posteriores a 2023, el
    hold-out no es fuera de muestra para ese modelo. Revisar la ficha de cada modelo.
  - Latencia: se mide (ms por serie) y se registra en MLflow. Con rebalanceo mensual no es un
    cuello de botella; la destilacion solo vale la pena si se despliega en linea (PSet 4).
Paquetes (fuera del lock, chocan entre si): chronos-forecasting; timesfm; uni2ts (Moirai).
Instalar cada uno en su propio entorno o en Colab con !pip.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from ..entorno import dispositivo

CUANTILES = (0.1, 0.5, 0.9)


class Chronos:
    """amazon/chronos-bolt-small por defecto (rapido en CPU, mps y T4)."""

    def __init__(self, modelo: str = "amazon/chronos-bolt-small", contexto: int = 512, h: int = 21):
        from chronos import BaseChronosPipeline
        import torch
        disp = dispositivo()
        self.nombre, self.contexto, self.h = modelo, contexto, h
        self.pipe = BaseChronosPipeline.from_pretrained(
            modelo, device_map=disp, torch_dtype=torch.float32 if disp != "cuda" else torch.bfloat16)

    def pronosticar(self, ventanas: list[np.ndarray]) -> np.ndarray:
        import torch
        ctx = [torch.tensor(v[-self.contexto:], dtype=torch.float32) for v in ventanas]
        q, _ = self.pipe.predict_quantiles(ctx, prediction_length=self.h, quantile_levels=list(CUANTILES))
        return q.float().cpu().numpy()                      # (series, h, cuantiles)


class TimesFM:
    """google/timesfm-2.5-200m-pytorch (paquete timesfm >= 2, extra [torch])."""

    def __init__(self, modelo: str = "google/timesfm-2.5-200m-pytorch", contexto: int = 512, h: int = 21):
        import timesfm
        import torch
        torch.set_float32_matmul_precision("high")
        self.nombre, self.contexto, self.h = modelo, contexto, h
        self.m = timesfm.TimesFM_2p5_200M_torch.from_pretrained(modelo)
        self.m.compile(timesfm.ForecastConfig(
            max_context=contexto, max_horizon=64, normalize_inputs=True, use_continuous_quantile_head=True,
            force_flip_invariance=True, infer_is_positive=False, fix_quantile_crossing=True))

    def pronosticar(self, ventanas: list[np.ndarray]) -> np.ndarray:
        _, q = self.m.forecast(horizon=self.h, inputs=[v[-self.contexto:].astype(np.float32) for v in ventanas])
        q = np.asarray(q)                                    # (series, h, 10): media y deciles 0,1..0,9
        return np.stack([q[:, :, 1], q[:, :, 5], q[:, :, 9]], axis=-1)


class Moirai:
    """Salesforce/moirai-2.0-R-small (uni2ts desde GitHub; usa predictores de GluonTS)."""

    def __init__(self, modelo: str = "Salesforce/moirai-2.0-R-small", contexto: int = 512, h: int = 21,
                 lote: int = 128):
        from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module
        self.nombre, self.contexto, self.h = modelo, contexto, h
        self.predictor = Moirai2Forecast(
            module=Moirai2Module.from_pretrained(modelo), prediction_length=h, context_length=contexto,
            target_dim=1, feat_dynamic_real_dim=0, past_feat_dynamic_real_dim=0).create_predictor(batch_size=lote)

    def pronosticar(self, ventanas: list[np.ndarray]) -> np.ndarray:
        inicio = pd.Period("2000-01-03", freq="D")           # la fecha no se usa: solo la serie
        datos = [{"target": v[-self.contexto:].astype(np.float32), "start": inicio} for v in ventanas]
        salida = []
        for f in self.predictor.predict(datos):
            salida.append(np.stack([f.quantile(q) for q in CUANTILES], axis=-1))
        return np.asarray(salida)                            # (series, h, cuantiles)


MODELOS = {"chronos": Chronos, "timesfm": TimesFM, "moirai": Moirai}


def origenes_desde(obt: pd.DataFrame, diaria: pd.DataFrame) -> pd.DataFrame:
    """Un origen por fila elegible de la OBT: el ultimo dia con cotizacion de la accion en su mes."""
    ultimo = (diaria.assign(anio_mes=pd.to_datetime(diaria["fecha"]).dt.strftime("%Y%m").astype(int))
              .groupby(["accion_key", "anio_mes"])["fecha"].max().rename("fecha_origen").reset_index())
    return obt[["accion_key", "anio_mes"]].merge(ultimo, on=["accion_key", "anio_mes"], how="inner")


def pronosticos_mensuales(modelo, diaria: pd.DataFrame, origenes: pd.DataFrame, lote: int = 256) -> pd.DataFrame:
    """Una fila por (accion_key, anio_mes): pronostico del mes (suma de cuantiles diarios),
    ancho 10-90 y latencia por serie. Solo usa retornos con fecha <= fecha_origen."""
    diaria = diaria[~diaria["imputado"].astype(bool)].sort_values(["accion_key", "fecha"])
    series = {k: (g["fecha"].to_numpy(), g["ret_log_diario"].to_numpy(dtype=float))
              for k, g in diaria.groupby("accion_key")}
    claves, ventanas = [], []
    for o in origenes.itertuples():
        f, r = series.get(o.accion_key, (None, None))
        if f is None:
            continue
        v = r[(f <= np.datetime64(o.fecha_origen)) & np.isfinite(r)][-getattr(modelo, "contexto", 512):]
        if len(v) >= 64:
            claves.append((o.accion_key, o.anio_mes))
            ventanas.append(v)
    filas, t0 = [], time.perf_counter()
    for i in range(0, len(ventanas), lote):
        q = modelo.pronosticar(ventanas[i:i + lote]).sum(axis=1)          # suma de 21 dias
        for (k, m), fila in zip(claves[i:i + lote], q):
            filas.append({"accion_key": k, "anio_mes": m, "pred": fila[1], "ancho_10_90": fila[2] - fila[0]})
    ms = 1000 * (time.perf_counter() - t0) / max(len(ventanas), 1)
    out = pd.DataFrame(filas)
    out.attrs["latencia_ms_por_serie"] = ms
    return out


if __name__ == "__main__":
    # Fase pesada, una vez por modelo y en su propio entorno (los paquetes chocan entre si). Ver README.
    import argparse, hashlib, json
    from pathlib import Path
    ap = argparse.ArgumentParser(description="Pronosticos zero-shot del mes siguiente para la OBT elegible")
    ap.add_argument("--modelo", choices=list(MODELOS), required=True)
    ap.add_argument("--lote", type=int, default=256)
    ap.add_argument("--limite", type=int, default=0, help="solo las primeras N filas (prueba rapida)")
    ap.add_argument("--desde", type=int, default=0, help="solo meses de decision >= AAAAMM (p. ej. 201612)")
    ap.add_argument("--hasta", type=int, default=0, help="solo meses de decision <= AAAAMM (p. ej. 202311)")
    a = ap.parse_args()
    raiz = Path(__file__).resolve().parents[2]
    obt = pd.read_parquet(raiz / "data/obt.parquet")
    obt = obt[obt["elegible"].fillna(False).astype(bool)]
    diaria = pd.read_parquet(raiz / "data/obt_dia.parquet",
                             columns=["accion_key", "fecha", "ret_log_diario", "imputado"])
    origenes = origenes_desde(obt, diaria)
    if a.desde:
        origenes = origenes[origenes["anio_mes"] >= a.desde]
    if a.hasta:
        origenes = origenes[origenes["anio_mes"] <= a.hasta]
    if a.limite:
        origenes = origenes.head(a.limite)
    t0 = time.perf_counter()
    modelo = MODELOS[a.modelo]()
    carga = time.perf_counter() - t0
    pred = pronosticos_mensuales(modelo, diaria, origenes, lote=a.lote)
    destino = raiz / "artefactos" / f"fundacional_{a.modelo}.parquet"
    destino.parent.mkdir(exist_ok=True)
    pred.to_parquet(destino, index=False)
    meta = {"modelo": a.modelo, "id": modelo.nombre, "desde": a.desde or None, "hasta": a.hasta or None, "contexto": modelo.contexto, "horizonte_dias": modelo.h,
            "filas": len(pred), "latencia_ms_por_serie": pred.attrs.get("latencia_ms_por_serie"),
            "segundos_carga": carga, "segundos_total": time.perf_counter() - t0,
            "sha256": hashlib.sha256(destino.read_bytes()).hexdigest()}
    destino.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
