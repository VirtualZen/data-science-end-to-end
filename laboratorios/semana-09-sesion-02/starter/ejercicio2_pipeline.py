"""Ejercicio 2: el pipeline completo de viajes_features.csv.

Corre el script con:

    python3 ejercicio2_pipeline.py

Al final se imprime una comprobacion por cada TODO. No la modifiques:
cuando las cinco digan OK, pasa a las preguntas del README.
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

viajes = pd.read_csv("viajes_features.csv")

NUMERICAS = ["distancia_km", "pasajeros"]
YA_LISTAS = ["hora_sin", "hora_cos", "es_fin_de_semana", "es_hora_pico", "es_tarifa_fija"]
CATEGORICAS = ["zona_origen", "zona_destino", "metodo_pago"]

X = viajes[NUMERICAS + YA_LISTAS + CATEGORICAS]
y = viajes["tarifa"]

# DONE 1: divide X e y en entrenamiento (80%) y prueba (20%), con
# random_state=42.
X_ent, X_prueba, y_ent, y_prueba = train_test_split(X, y, test_size=0.2, random_state=42)

# DONE 2: arma un Pipeline para las columnas NUMERICAS (imputar con la
# mediana, despues escalar) y otro para las CATEGORICAS (imputar con el
# valor mas frecuente, despues OneHotEncoder con handle_unknown="ignore" y
# sparse_output=False). Juntalos en un ColumnTransformer llamado
# preparacion, con las columnas YA_LISTAS pasando sin cambios
# ("passthrough").
numericas = Pipeline([
    ("imputar", SimpleImputer(strategy="median")),
    ("escalar", StandardScaler()),
])
categoricas = Pipeline([
    ("imputar", SimpleImputer(strategy="most_frequent")),
    ("codificar", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
])
preparacion = ColumnTransformer([
    ("numericas", numericas, NUMERICAS),
    ("categoricas", categoricas, CATEGORICAS),
    ("ya_listas", "passthrough", YA_LISTAS),
])

# DONE 3: aprende la preparacion solo con entrenamiento y transforma
# entrenamiento y prueba. Imprime cuantas columnas quedan.
X_ent_listo = preparacion.fit_transform(X_ent)
X_prueba_listo = preparacion.transform(X_prueba)
print("Columnas despues de preparar:", X_ent_listo.shape[1])

# DONE 4: medianas_aprendidas, las medianas que aprendio el imputador de
# numericas (atributo statistics_). Imprimelas junto a las medianas de
# entrenamiento y las de todo el dataset.
medianas_aprendidas = preparacion.named_transformers_["numericas"].named_steps["imputar"].statistics_
print("Medianas aprendidas:      ", medianas_aprendidas)
print("Medianas de entrenamiento:", X_ent[NUMERICAS].median().values)
print("Medianas de todo el set:  ", X[NUMERICAS].median().values)

# DONE 5: transforma el viaje nuevo de abajo, que sale de una zona que el
# entrenamiento nunca vio, y guarda en zona_origen_en_1 cuantas columnas
# de zona_origen quedan en 1.
nuevo = pd.DataFrame([{
    "distancia_km": 9.0, "pasajeros": 1, "hora_sin": 0.5, "hora_cos": -0.866,
    "es_fin_de_semana": 0, "es_hora_pico": 1, "es_tarifa_fija": 0,
    "zona_origen": "Bronx", "zona_destino": "Midtown", "metodo_pago": "tarjeta",
}])
nuevo_listo = pd.DataFrame(preparacion.transform(nuevo), columns=preparacion.get_feature_names_out())
columnas_origen = [c for c in nuevo_listo.columns if c.startswith("categoricas__zona_origen_")]
zona_origen_en_1 = int(nuevo_listo[columnas_origen].sum(axis=1).iloc[0])
print("Columnas de zona_origen en 1 para el viaje desde el Bronx:", zona_origen_en_1)


def comprobar(numero, condicion):
    if condicion:
        print(f"TODO {numero}: OK")
    else:
        print(f"TODO {numero}: revisa")


print()
print("Comprobacion")
comprobar(1, X_ent is not None and len(X_ent) == 2380 and len(X_prueba) == 595)
comprobar(2, isinstance(preparacion, ColumnTransformer) and len(preparacion.transformers) == 3)
comprobar(3, X_ent_listo is not None and X_ent_listo.shape[1] == 25 and X_prueba_listo.shape[0] == 595)
comprobar(4, medianas_aprendidas is not None and X_ent is not None
          and np.allclose(medianas_aprendidas, X_ent[NUMERICAS].median().values))
comprobar(5, zona_origen_en_1 == 0)
