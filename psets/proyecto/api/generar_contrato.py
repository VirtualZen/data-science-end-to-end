"""Genera api/contrato.json: el contrato de entrada de la API, calculado con los datos de entrenamiento.

El esquema de Pydantic (api/esquemas.py) coincide con la firma registrada en MLflow
(portafolio-inversiones-modelo, run f7596a565f8a458492057238f245cf89): las 33 columnas de la OBT
que usa el modelo + anio_mes. Las dos derivadas (dispersion_mes y mes_calendario_obj) no se piden:
la API las calcula con src.pipeline.derivar, igual que en el entrenamiento.

Rangos permitidos: [minimo - 0,5 * rango, maximo + 0,5 * rango] del entrenamiento (objetivos hasta
2023-12), con piso 0 en las variables que no pueden ser negativas. El margen deja pasar meses mas
extremos que los vistos (una crisis) y rechaza errores de unidad o de captura (p. ej. un retorno en
% en vez de log, 100 veces mayor). Lo que cae dentro del margen pero fuera del rango observado lo
cuenta el monitoreo como "fuera de rango" (seccion 6.1), no la API.

Uso, desde psets/pset-04/:
    uv run --project modelos python api/generar_contrato.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "modelos"))

from src.datos import cargar  # noqa: E402
from src.pipeline import FEATURES_OBT, TARGET, dividir, preparar  # noqa: E402

NO_NEGATIVAS = {"vol_21d", "vol_63d", "vol_apertura_21d", "vol_intradia_21d", "vol_parkinson_21d",
                "vol_garman_klass_21d", "volumen_prom_21d", "dolares_negociados_prom_21d", "obs_252d",
                "dias_negociados_mes", "rango_log_hl_mes", "rango_log_hl_prom_21d", "rango_log_hl_prom_63d"}
MARGEN = 0.5


def main() -> None:
    obt, meta = cargar()
    entrenamiento, _ = dividir(preparar(obt))
    rangos = {}
    for c in FEATURES_OBT:
        s = entrenamiento[c].astype(float)
        lo, hi = float(s.min()), float(s.max())
        ancho = hi - lo
        minimo = lo - MARGEN * ancho
        if c in NO_NEGATIVAS:
            minimo = max(0.0, minimo)
        rangos[c] = {"min": minimo, "max": hi + MARGEN * ancho, "min_observado": lo, "max_observado": hi,
                     "nulos_entrenamiento": int(s.isna().sum())}
    contrato = {
        "modelo": "portafolio-inversiones-modelo",
        "run_id_entrenamiento": "f7596a565f8a458492057238f245cf89",
        "fuente": {"tabla": meta["tabla"], "sha256": meta["sha256"], "filas": meta["filas"],
                   "filas_entrenamiento": int(len(entrenamiento)), "corte_objetivo": "2023-12"},
        "features": rangos,
        "margen": MARGEN,
        # B1 del PSet 3 (DummyRegressor(strategy='mean')): el retorno log promedio del entrenamiento.
        "respaldo_b1_media": float(entrenamiento[TARGET].mean()),
        "anio_mes": {"min": 201001, "max": 210012},
    }
    (AQUI / "contrato.json").write_text(json.dumps(contrato, indent=2, ensure_ascii=False) + "\n")
    print(f"contrato.json: {len(rangos)} features, B1 = {contrato['respaldo_b1_media']:.6f}, "
          f"fuente {meta['tabla']} ({meta['sha256'][:8]})")


if __name__ == "__main__":
    main()
