"""Validacion temporal walk-forward por anio calendario, con embargo y verificacion de fuga.

Convencion de la OBT: la fila del mes m tiene variables con datos hasta el cierre de m y su
objetivo es el retorno del mes m+1 (mes_objetivo). Todo se ordena por mes_objetivo.

Ventana k (expansiva por defecto):
  validacion     filas con mes_objetivo en el anio V_k (12 meses)
  entrenamiento  filas con mes_objetivo <= primer mes de V_k - 1 - embargo
El embargo de 1 mes descarta el mes cuyo objetivo es el mes de las primeras variables de
validacion: las ventanas moviles de 21-252 dias de ambas filas se solapan (correlacion serial).
Con ventana fija (ventana_meses) se usan solo los ultimos ventana_meses de entrenamiento.

Prohibido: KFold aleatorio o GroupKFold por accion (mezclan meses futuros en entrenamiento).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CORTE_DESARROLLO = pd.Period("2023-12", freq="M")   # ultimo mes_objetivo de desarrollo (PSet 1)


@dataclass(frozen=True)
class Ventana:
    nombre: str
    inicio_entrenamiento: pd.Period
    fin_entrenamiento: pd.Period      # ultimo mes_objetivo usado para ajustar
    inicio_validacion: pd.Period
    fin_validacion: pd.Period


def mes_objetivo(d: pd.DataFrame) -> pd.PeriodIndex:
    if "mes_objetivo" in d:
        return pd.PeriodIndex(d["mes_objetivo"], freq="M")
    return pd.PeriodIndex(d["anio_mes"].astype(str), freq="M") + 1


def ventanas_walk_forward(anios_validacion=range(2017, 2024), embargo: int = 1,
                          ventana_meses: int | None = None,
                          inicio_datos: pd.Period = pd.Period("2011-01", freq="M")) -> list[Ventana]:
    """Una ventana por anio de validacion. Por defecto 2017-2023: 7 ventanas expansivas."""
    out = []
    for anio in anios_validacion:
        ini_v = pd.Period(f"{anio}-01", freq="M")
        fin_v = min(pd.Period(f"{anio}-12", freq="M"), CORTE_DESARROLLO)
        fin_e = ini_v - 1 - embargo
        ini_e = inicio_datos if ventana_meses is None else max(inicio_datos, fin_e - ventana_meses + 1)
        if fin_v > CORTE_DESARROLLO:
            raise ValueError("La validacion no puede usar objetivos del hold-out (desde 2024-01)")
        out.append(Ventana(f"wf_{anio}", ini_e, fin_e, ini_v, fin_v))
    return out


def indices(d: pd.DataFrame, v: Ventana) -> tuple[np.ndarray, np.ndarray]:
    mo = mes_objetivo(d)
    it = np.flatnonzero((mo >= v.inicio_entrenamiento) & (mo <= v.fin_entrenamiento))
    iv = np.flatnonzero((mo >= v.inicio_validacion) & (mo <= v.fin_validacion))
    verificar_sin_fuga(d, it, iv)
    return it, iv


def pliegues_walk_forward(d: pd.DataFrame, **kw):
    """Los pliegues oficiales son src.pipeline.pliegues (TimeSeriesSplit sobre meses). Este generador
    se conserva para ventanas a medida (p. ej. ventana fija con ventana_meses)."""
    for v in ventanas_walk_forward(**kw):
        it, iv = indices(d, v)
        if len(it) and len(iv):
            yield it, iv


def verificar_sin_fuga(d: pd.DataFrame, it: np.ndarray, iv: np.ndarray) -> None:
    """Falla si algun objetivo de entrenamiento se conoce despues de las primeras variables de validacion."""
    if not len(it) or not len(iv):
        return
    mo = mes_objetivo(d)
    ultimo_objetivo_ent = mo[it].max()
    primer_mes_variables_val = mo[iv].min() - 1
    if ultimo_objetivo_ent >= primer_mes_variables_val + 1:
        raise AssertionError(f"Fuga: objetivo de entrenamiento {ultimo_objetivo_ent} >= "
                             f"mes de validacion {primer_mes_variables_val + 1}")
    if mo[iv].max() > CORTE_DESARROLLO:
        raise AssertionError("Fuga: la validacion toca el hold-out")


def dividir_holdout(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Desarrollo (objetivos hasta 2023-12) y hold-out (desde 2024-01), que se usa una sola vez."""
    mo = mes_objetivo(d)
    return d[mo <= CORTE_DESARROLLO].copy(), d[mo > CORTE_DESARROLLO].copy()
