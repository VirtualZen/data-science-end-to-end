"""El modelo servido reproduce la metrica registrada del champion sobre el hold-out guardado en fixtures.

Tolerancia 1e-6 en MAE: el PSet 3 reprodujo el valor exacto (0,0673399888) con la misma version de
LightGBM; 1e-6 es cuatro ordenes de magnitud menor que la desviacion del MAE entre pliegues (~0,016), de
modo que solo absorbe diferencias de redondeo entre plataformas (x86 en CI, ARM en el Mac) y cualquier
cambio real del modelo o de la preparacion la rompe."""
from __future__ import annotations

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from src.pipeline import FEATURES, TARGET

FIJAS = Path(__file__).resolve().parent / "fixtures"
MAE_REGISTRADO = 0.0673399888
TOLERANCIA = 1e-6


def test_reproduce_mae_holdout():
    modelo = mlflow.sklearn.load_model(str(FIJAS / "modelo_champion"))
    h = pd.read_parquet(FIJAS / "holdout.parquet")
    assert len(h) == 11326
    mae = float(np.mean(np.abs(h[TARGET] - modelo.predict(h[FEATURES + ["anio_mes"]]))))
    assert abs(mae - MAE_REGISTRADO) < TOLERANCIA, mae


def test_api_predice_igual_que_el_modelo(cliente, lote):
    """La API (validacion + derivar + modelo) da lo mismo que el modelo directo sobre las mismas filas."""
    from src.pipeline import derivar
    modelo = mlflow.sklearn.load_model(str(FIJAS / "modelo_champion"))
    d = pd.DataFrame(lote["acciones"])
    d["anio_mes"] = lote["anio_mes"]
    directo = modelo.predict(derivar(d)[FEATURES + ["anio_mes"]])
    api = [a["retorno_predicho"] for a in cliente.post("/predecir", json=lote).json()["acciones"]]
    assert np.allclose(api, directo, atol=1e-12)


def test_firma_mlflow_coincide_con_el_contrato_de_la_api():
    """PDF 2: el esquema de Pydantic coincide con la firma registrada en MLflow (nombres, orden, tipos).

    La API pide las 33 columnas de la OBT y anio_mes; las derivadas (dispersion_mes, mes_calendario_obj) las
    calcula src.pipeline.derivar, como en el entrenamiento. Si alguien reentrena con otras columnas o
    regenera api/contrato.json desde otra corrida, esta prueba falla antes de que la API acepte entradas
    que el modelo no espera."""
    from mlflow.models import Model
    from mlflow.types import DataType

    from api.esquemas import CONTRATO, FEATURES_ENTRADA, AccionEntrada, PeticionPrediccion
    from src.pipeline import DERIVADAS

    modelo = Model.load(str(FIJAS / "modelo_champion"))
    firma = {c.name: c for c in modelo.signature.inputs.inputs}
    assert set(FEATURES_ENTRADA) == set(firma) - set(DERIVADAS) - {"anio_mes"}
    assert [c for c in firma if c in FEATURES_ENTRADA] == FEATURES_ENTRADA
    assert all(firma[c].type == DataType.double and firma[c].required for c in FEATURES_ENTRADA)
    assert set(FEATURES_ENTRADA) <= set(AccionEntrada.model_fields)
    assert "anio_mes" in PeticionPrediccion.model_fields
    assert CONTRATO["run_id_entrenamiento"] == modelo.metadata["run_id_registrado"]
