"""Esquemas de entrada y salida de la API (Pydantic), iguales a la firma registrada en MLflow.

La entrada es el lote del mes: las acciones candidatas de un mismo anio_mes. El modelo lo necesita
completo porque su primer paso (RangoTransversal) convierte cada variable en su percentil dentro del
mes y src.pipeline.derivar calcula dispersion_mes con todas las acciones del mes. Con una sola accion
la prediccion es valida pero degenerada (todos los percentiles iguales): sirve para probar el
contrato, no para decidir.

Cada feature es obligatoria, numerica, finita y dentro de su rango permitido (api/contrato.json,
generado con api/generar_contrato.py desde el entrenamiento). Un campo faltante, de otro tipo, fuera
de rango, o que no esta en la firma devuelve 422 con el nombre del campo (FastAPI lo arma con los
errores de Pydantic). La categoria del modelo es el mes calendario del objetivo, que sale de anio_mes:
un mes fuera de 1-12 es una categoria desconocida y tambien da 422.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator

CONTRATO = json.loads((Path(__file__).resolve().parent / "contrato.json").read_text())
FEATURES_ENTRADA = list(CONTRATO["features"])          # 33, en el orden de la firma


def _campo(rango: dict):
    return (float, Field(..., ge=rango["min"], le=rango["max"], strict=True, allow_inf_nan=False))


_Features = create_model(
    "_Features",
    __config__=ConfigDict(extra="forbid"),
    **{nombre: _campo(r) for nombre, r in CONTRATO["features"].items()},
)


class AccionEntrada(_Features):
    """Una accion candidata del mes: identificadores + las 33 columnas de la OBT que usa el modelo."""
    accion_key: str = Field(..., min_length=1, max_length=64)
    ticker: str = Field(..., min_length=1, max_length=12)


class PeticionPrediccion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anio_mes: int = Field(..., strict=True, ge=CONTRATO["anio_mes"]["min"], le=CONTRATO["anio_mes"]["max"],
                          description="Mes de cierre de los datos (AAAAMM); el objetivo es el mes siguiente.")
    acciones: list[AccionEntrada] = Field(..., min_length=1, max_length=2000)
    n: int = Field(10, strict=True, ge=1, le=50, description="Acciones del portafolio (regla del PSet 1: 10).")
    tope_percentil: float = Field(0.80, gt=0, le=1, allow_inf_nan=False,
                                  description="Se excluyen las acciones con vol_63d sobre este percentil del mes.")

    @field_validator("anio_mes")
    @classmethod
    def _mes_valido(cls, v: int) -> int:
        if not 1 <= v % 100 <= 12:
            raise ValueError(f"mes {v % 100} desconocido: anio_mes debe ser AAAAMM con mes de 01 a 12")
        return v

    @model_validator(mode="after")
    def _sin_repetidas(self):
        claves = [a.accion_key for a in self.acciones]
        if len(claves) != len(set(claves)):
            raise ValueError("accion_key repetida en el lote: cada accion va una sola vez por mes")
        return self


class AccionSalida(BaseModel):
    id_prediccion: str
    accion_key: str
    ticker: str
    retorno_predicho: float = Field(..., description="Retorno log predicho del mes siguiente.")
    decision: Literal["incluir", "no incluir"]
    peso: float = Field(..., description="Fraccion del capital (1/vol, suma 1 entre las incluidas); 0 si no se incluye.")
    sharpe_12m: float | None = Field(None, description="Puntaje de la operacion manual (B7): Sharpe de 12 meses.")
    decision_operacion_manual: Literal["incluir", "no incluir"] = Field(
        ..., description="Lo que haria la operacion manual (competidor B7) con la misma regla de riesgo.")
    peso_operacion_manual: float


class InfoModelo(BaseModel):
    nombre: str
    version: str | None
    alias: str | None
    run_id: str | None
    uri: str
    respaldo: bool = Field(..., description="True si responde la linea base y no el modelo.")
    motivo_respaldo: str | None = None


class RespuestaPrediccion(BaseModel):
    id_lote: str
    anio_mes: int
    mes_objetivo: str
    modelo: InfoModelo
    usado: str = Field(..., description="'modelo' o el nombre de la linea base de respaldo.")
    n_incluidas: int
    n_coinciden_operacion_manual: int = Field(..., description="Acciones incluidas por el modelo y por la operacion manual.")
    acciones: list[AccionSalida]
    latencia_ms: float
    registrado: bool = Field(True, description="Si cada prediccion quedo en el registro local (JSONL). El registro oficial en Snowflake (PREDICCIONES) lo escribe produccion_lotes con esta respuesta; false = revisar el log y /metricas.")
