"""API de prediccion del portafolio (PSet 4, seccion 2).

Endpoints:
    GET  /salud      estado del servicio y si el modelo cargo
    GET  /modelo     nombre, version, alias y run_id del modelo en uso
    POST /predecir   lote del mes -> retorno predicho, decision (incluir / no incluir), peso, version e id
    GET  /metricas   latencia p50/p95, errores 4xx/5xx, volumen, distribucion de predicciones y decisiones
    POST /recargar   vuelve a resolver el alias en el registro (version nueva sin reconstruir la imagen)
    POST /respaldo   interruptor: usar la linea base en vez del modelo (seccion 8.4)
/recargar y /respaldo piden el encabezado X-Token igual a la variable API_TOKEN.

El modelo se carga desde el Model Registry de MLflow: models:/portafolio-inversiones-modelo@champion
(MODELO_URI lo cambia; en CI apunta a la copia de tests/fixtures/). Las features derivadas y la
decision usan las mismas funciones del modelado, importadas: src.pipeline.derivar (dispersion_mes y
mes del objetivo) y src.negocio.pesos_mes (regla del PSet 1: fuera el 20 % mas volatil del mes, las
10 de mayor prediccion, pesos 1/vol). El tope de volatilidad del portafolio (1,35 x S&P 500, con
covarianzas diarias) no se aplica aqui: necesita la OBT diaria y lo aplica la simulacion por lotes.

Si el modelo no carga, o el interruptor esta activo, responde la linea base del PSet 3: retorno B1
(media del entrenamiento) y decision B5 (todo el universo candidato con igual peso, la referencia de
negocio), e indica en la respuesta que uso el respaldo.

Registro (auditoria H3): el registro oficial es la tabla PREDICCIONES de Snowflake, que escribe el flow
produccion_lotes (monitoreo.produccion lote) con la respuesta de cada lote (patron batch). Ademas, cada prediccion se
agrega a REGISTRO_PREDICCIONES (JSONL local) con su id, hora, entradas, salida, version, run_id y latencia; las
llamadas sueltas a /predecir (fuera de produccion_lotes) quedan solo ahi. Si ese registro falla, la respuesta trae
registrado=false y /metricas cuenta registro_fallido: el fallo no es silencioso.

Uso local, desde psets/pset-04/:
    uv run --project api uvicorn api.main:app --port 8000
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

AQUI = Path(__file__).resolve().parent
# src/ del modelado: en el contenedor esta junto a api/; en el repo, en ../modelos/src.
for raiz in (AQUI.parent, AQUI.parent / "modelos"):
    if (raiz / "src" / "pipeline.py").exists():
        sys.path.insert(0, str(raiz))
        break

from src.negocio import pesos_mes  # noqa: E402
from src.operacion_manual import seleccion_mes, sharpe_12m  # noqa: E402
from src.pipeline import FEATURES, derivar  # noqa: E402

from .esquemas import (CONTRATO, FEATURES_ENTRADA, AccionSalida, InfoModelo,  # noqa: E402
                       PeticionPrediccion, RespuestaPrediccion)

log = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

NOMBRE = os.environ.get("MODELO_NOMBRE", "portafolio-inversiones-modelo")
ALIAS = os.environ.get("MODELO_ALIAS", "champion")
COLUMNAS_MODELO = FEATURES + ["anio_mes"]          # 36: la firma registrada en MLflow
RESPALDO_B1 = float(CONTRATO["respaldo_b1_media"])
NOMBRE_RESPALDO = "respaldo: B1 media (retorno) + B5 universo con igual peso (decision)"


def _uri() -> str:
    return os.environ.get("MODELO_URI") or f"models:/{NOMBRE}@{ALIAS}"


class Estado:
    """Modelo en memoria, su informacion y el interruptor de respaldo."""

    def __init__(self) -> None:
        self.modelo = None
        self.info = InfoModelo(nombre=NOMBRE, version=None, alias=None, run_id=None, uri=_uri(), respaldo=True,
                               motivo_respaldo="el modelo aun no carga")
        self.interruptor = os.environ.get("USAR_RESPALDO", "0").lower() in ("1", "true", "si", "yes")
        self.bloqueo = threading.Lock()

    def cargar(self) -> None:
        import mlflow
        from mlflow import MlflowClient

        uri = _uri()
        try:
            inicio = time.perf_counter()
            version = alias = None
            fija = uri                       # referencia inmutable que se carga (auditoria H5)
            if uri.startswith("models:/"):
                # El alias es mutable: se resuelve UNA vez a un numero de version y todo (artefacto, firma,
                # run_id) se lee de models:/<nombre>/<version>. Si el alias se mueve durante la carga, la
                # API queda con una version coherente y la siguiente /recargar toma la nueva.
                nombre_ref = uri.removeprefix("models:/")
                cliente = MlflowClient()
                if "@" in nombre_ref:
                    nombre, alias = nombre_ref.split("@", 1)
                    mv = cliente.get_model_version_by_alias(nombre, alias)
                else:
                    nombre, _ = nombre_ref.split("/", 1)
                    mv = cliente.get_model_version(nombre, _)
                version, run_id = str(mv.version), mv.run_id
                fija = f"models:/{nombre}/{mv.version}"
            modelo = mlflow.sklearn.load_model(fija)
            if not uri.startswith("models:/"):
                # Copia local (tests/fixtures/ en CI, sin MLflow): run_id y version registrados en sus metadatos.
                mlmodel = mlflow.models.Model.load(fija)
                extra = mlmodel.metadata or {}
                run_id = mlmodel.run_id or extra.get("run_id_registrado")
                version = extra.get("version_registrada")
            info = InfoModelo(nombre=NOMBRE, version=version, alias=alias, run_id=run_id, uri=uri,
                              respaldo=self.interruptor,
                              motivo_respaldo="interruptor activo" if self.interruptor else None)
            with self.bloqueo:
                # Un solo intercambio: modelo e info siempre van juntos (ver vigente()).
                self.modelo, self.info = modelo, info
            log.info("Modelo cargado de %s (version %s, run %s) en %.1f s", uri, version, run_id,
                     time.perf_counter() - inicio)
        except Exception as e:  # el servicio sigue arriba con el respaldo
            log.exception("No se pudo cargar %s", uri)
            with self.bloqueo:
                if self.modelo is None:
                    self.info = InfoModelo(nombre=NOMBRE, version=None, alias=None, run_id=None, uri=uri,
                                           respaldo=True, motivo_respaldo=f"el modelo no carga: {type(e).__name__}")
            raise

    @property
    def usa_respaldo(self) -> bool:
        return self.interruptor or self.modelo is None

    def vigente(self):
        """Par (modelo, info) leido bajo el mismo bloqueo: la prediccion y la version que se informa salen del mismo
        modelo aunque /recargar lo cambie a mitad de la peticion (auditoria H5)."""
        with self.bloqueo:
            return self.modelo, self.info

    def info_actual(self) -> InfoModelo:
        motivo = ("interruptor activo" if self.interruptor else self.info.motivo_respaldo if self.modelo is None
                  else None)
        return self.info.model_copy(update={"respaldo": self.usa_respaldo, "motivo_respaldo": motivo})


class Metricas:
    """Metricas de sistema y de modelo en memoria (ultimas 10.000 peticiones). Cada registro lleva su hora, asi
    que /metricas?desde=<ISO> resume solo una ventana (p. ej. la del lote que se esta monitoreando)."""

    def __init__(self, ventana: int = 10_000) -> None:
        self.peticiones = deque(maxlen=ventana)          # (hora, ruta, codigo, ms)
        self.predicciones = deque(maxlen=ventana)        # (hora, retorno)
        self.decisiones = deque(maxlen=ventana)          # (hora, decision)
        self.registro_fallido = 0                         # lotes que no se pudieron escribir en el JSONL
        self.inicio = datetime.now(timezone.utc)
        self.bloqueo = threading.Lock()

    def peticion(self, ruta: str, codigo: int, ms: float) -> None:
        with self.bloqueo:
            self.peticiones.append((datetime.now(timezone.utc), ruta, codigo, ms))

    def prediccion(self, retornos, decisiones) -> None:
        ahora = datetime.now(timezone.utc)
        with self.bloqueo:
            self.predicciones.extend((ahora, float(x)) for x in retornos)
            self.decisiones.extend((ahora, d) for d in decisiones)

    def resumen(self, desde: datetime | None = None) -> dict:
        desde = desde or self.inicio
        with self.bloqueo:
            pet = [p for p in self.peticiones if p[0] >= desde]
            pred = np.array([v for t, v in self.predicciones if t >= desde])
            dec = Counter(d for t, d in self.decisiones if t >= desde)
        # Latencia solo de /predecir respondidas: las 422 responden en ~1 ms y bajarian el p50.
        lat = np.array([ms for _, ruta, c, ms in pet if ruta == "/predecir" and c < 400])
        codigos = Counter(c for _, _, c, _ in pet)
        n_dec = sum(dec.values()) or 1
        pct = lambda a, q: float(np.percentile(a, q)) if len(a) else None
        return {
            "desde_utc": desde.isoformat(),
            "sistema": {
                "solicitudes": len(pet),
                "predecir_p50_ms": pct(lat, 50),
                "predecir_p95_ms": pct(lat, 95),
                "errores_4xx": sum(v for k, v in codigos.items() if 400 <= k < 500),
                "errores_5xx": sum(v for k, v in codigos.items() if k >= 500),
                "codigos": {str(k): v for k, v in sorted(codigos.items())},
                "registro_fallido": self.registro_fallido,
            },
            "modelo": {
                "predicciones": int(len(pred)),
                "retorno_predicho": {q: pct(pred, p) for q, p in (("p05", 5), ("p50", 50), ("p95", 95))},
                "tasa_decision": {k: v / n_dec for k, v in dec.items()},
            },
        }


ESTADO = Estado()
METRICAS = Metricas()
_bloqueo_registro = threading.Lock()


def _ruta_registro() -> Path:
    return Path(os.environ.get("REGISTRO_PREDICCIONES", AQUI / "registros" / "predicciones.jsonl"))


@asynccontextmanager
async def ciclo(_app: FastAPI):
    try:
        ESTADO.cargar()
    except Exception:
        log.warning("Arranca en modo respaldo: %s", ESTADO.info.motivo_respaldo)
    yield


app = FastAPI(title="API del portafolio de inversiones", version="1.0", lifespan=ciclo)


@app.middleware("http")
async def medir(request: Request, call_next):
    inicio = time.perf_counter()
    try:
        respuesta = await call_next(request)
    except Exception:
        METRICAS.peticion(request.url.path, 500, (time.perf_counter() - inicio) * 1000)
        raise
    METRICAS.peticion(request.url.path, respuesta.status_code, (time.perf_counter() - inicio) * 1000)
    return respuesta


@app.exception_handler(RequestValidationError)
async def entrada_invalida(_request: Request, exc: RequestValidationError):
    errores = jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})
    campos = sorted({".".join(str(p) for p in e["loc"] if p != "body") for e in errores})
    return JSONResponse(status_code=422, content={"mensaje": f"Entrada invalida en: {', '.join(campos)}",
                                                  "campos_invalidos": campos, "detail": errores})


def _token(x_token: str | None) -> None:
    esperado = os.environ.get("API_TOKEN")
    if not esperado or x_token != esperado:
        raise HTTPException(status_code=401, detail="X-Token invalido o API_TOKEN no definido")


@app.get("/salud")
def salud() -> dict:
    info = ESTADO.info_actual()
    return {"estado": "ok" if ESTADO.modelo is not None else "degradado", "modelo_cargado": ESTADO.modelo is not None,
            "respaldo": info.respaldo, "motivo_respaldo": info.motivo_respaldo, "version": info.version,
            "alias": info.alias}


@app.get("/modelo", response_model=InfoModelo)
def modelo() -> InfoModelo:
    return ESTADO.info_actual()


@app.get("/metricas")
def metricas(desde: datetime | None = None) -> dict:
    """Sin desde: todo lo registrado desde que arranco la API. Con desde (ISO 8601 con zona): solo esa ventana."""
    if desde is not None and desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)
    return METRICAS.resumen(desde)


@app.post("/recargar", response_model=InfoModelo)
def recargar(x_token: str | None = Header(default=None)) -> InfoModelo:
    _token(x_token)
    try:
        ESTADO.cargar()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No se pudo recargar {_uri()}: {type(e).__name__}: {e}")
    return ESTADO.info_actual()


@app.post("/respaldo", response_model=InfoModelo)
def respaldo(activar: bool, x_token: str | None = Header(default=None)) -> InfoModelo:
    _token(x_token)
    ESTADO.interruptor = activar
    log.warning("Interruptor de respaldo %s", "ACTIVADO" if activar else "desactivado")
    return ESTADO.info_actual()


def _predecir_modelo(d: pd.DataFrame) -> tuple[np.ndarray, "InfoModelo"]:
    modelo, info = ESTADO.vigente()
    return np.asarray(modelo.predict(d[COLUMNAS_MODELO]), dtype=float), info


@app.post("/predecir", response_model=RespuestaPrediccion)
def predecir(peticion: PeticionPrediccion) -> RespuestaPrediccion:
    inicio = time.perf_counter()
    id_lote = uuid.uuid4().hex
    d = pd.DataFrame([a.model_dump() for a in peticion.acciones])
    d["anio_mes"] = peticion.anio_mes
    d = derivar(d)                                         # dispersion_mes y mes_calendario_obj
    d[FEATURES_ENTRADA + ["dispersion_mes"]] = d[FEATURES_ENTRADA + ["dispersion_mes"]].astype(float)

    usado = "modelo"
    info_modelo = None
    if not ESTADO.usa_respaldo:
        try:
            d["pred"], info_modelo = _predecir_modelo(d)
        except Exception:
            log.exception("Fallo la prediccion del modelo; responde el respaldo")
            usado = NOMBRE_RESPALDO
    else:
        usado = NOMBRE_RESPALDO
    if usado == "modelo":
        w = pesos_mes(d, "pred", vol="vol_63d", n=peticion.n, tope_percentil=peticion.tope_percentil)
    else:
        d["pred"] = RESPALDO_B1
        w = pd.Series(1.0 / len(d), index=d["accion_key"])     # B5: todo el universo con igual peso
    info = ESTADO.info_actual()
    if usado == "modelo" and info_modelo is not None:
        info = info_modelo.model_copy(update={"respaldo": False, "motivo_respaldo": None})
    if usado != "modelo":
        info = info.model_copy(update={"respaldo": True,
                                       "motivo_respaldo": info.motivo_respaldo or "fallo la prediccion del modelo"})

    d["peso"] = d["accion_key"].map(w).fillna(0.0)
    d["decision"] = np.where(d["peso"] > 0, "incluir", "no incluir")
    # Competidor B7 en paralelo: no cambia lo que se propone, queda para comparar y auditar.
    wm = seleccion_mes(d, {"n": peticion.n, "tope_percentil": peticion.tope_percentil})
    d["sharpe_12m"] = sharpe_12m(d)
    d["peso_manual"] = d["accion_key"].map(wm).fillna(0.0)
    d["decision_manual"] = np.where(d["peso_manual"] > 0, "incluir", "no incluir")
    d["id_prediccion"] = [uuid.uuid4().hex for _ in range(len(d))]
    latencia = (time.perf_counter() - inicio) * 1000
    acciones = [AccionSalida(id_prediccion=r.id_prediccion, accion_key=r.accion_key, ticker=r.ticker,
                             retorno_predicho=float(r.pred), decision=r.decision, peso=float(r.peso),
                             sharpe_12m=None if pd.isna(r.sharpe_12m) else float(r.sharpe_12m),
                             decision_operacion_manual=r.decision_manual, peso_operacion_manual=float(r.peso_manual))
                for r in d.itertuples()]
    respuesta = RespuestaPrediccion(id_lote=id_lote, anio_mes=peticion.anio_mes,
                                    mes_objetivo=str(d["mes_objetivo"].iloc[0]), modelo=info, usado=usado,
                                    n_incluidas=int((d["peso"] > 0).sum()),
                                    n_coinciden_operacion_manual=int(((d["peso"] > 0) & (d["peso_manual"] > 0)).sum()),
                                    acciones=acciones,
                                    latencia_ms=round(latencia, 3))
    METRICAS.prediccion(d["pred"], d["decision"])
    if not _registrar(respuesta, d):
        with METRICAS.bloqueo:
            METRICAS.registro_fallido += 1
        respuesta = respuesta.model_copy(update={"registrado": False})
    return respuesta


def _registrar(respuesta: RespuestaPrediccion, d: pd.DataFrame) -> bool:
    """Una linea JSON por accion: lo que pide la tabla PREDICCIONES (id, hora, entradas, salida,
    version, run_id, latencia). Un fallo al escribir no tumba la prediccion, pero devuelve False: la respuesta lo
    informa (registrado=false) y /metricas lo cuenta."""
    ahora = datetime.now(timezone.utc).isoformat()
    m = respuesta.modelo
    try:
        ruta = _ruta_registro()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        entradas = d.set_index("id_prediccion")[FEATURES_ENTRADA].to_dict("index")
        with _bloqueo_registro, ruta.open("a") as f:
            for a in respuesta.acciones:
                f.write(json.dumps({
                    "id_prediccion": a.id_prediccion, "id_lote": respuesta.id_lote, "timestamp_utc": ahora,
                    "anio_mes": respuesta.anio_mes, "mes_objetivo": respuesta.mes_objetivo,
                    "accion_key": a.accion_key, "ticker": a.ticker, "entradas": entradas[a.id_prediccion],
                    "retorno_predicho": a.retorno_predicho, "decision": a.decision, "peso": a.peso,
                    "decision_operacion_manual": a.decision_operacion_manual,
                    "peso_operacion_manual": a.peso_operacion_manual,
                    "modelo_nombre": m.nombre, "modelo_version": m.version, "modelo_alias": m.alias,
                    "run_id": m.run_id, "respaldo": m.respaldo, "usado": respuesta.usado,
                    "latencia_ms": respuesta.latencia_ms,
                }) + "\n")
        return True
    except Exception:
        log.exception("No se pudo registrar la prediccion %s", respuesta.id_lote)
        return False
