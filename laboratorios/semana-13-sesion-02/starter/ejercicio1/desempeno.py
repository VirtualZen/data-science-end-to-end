"""El desempeno del modelo en produccion: une cada prediccion guardada con
la tarifa que se cobro, y calcula el error por semana.

    python desempeno.py
"""

import os
import sys

import pandas as pd

MAE_REFERENCIA = 1.17  # el error en prueba con que se aprobo la version 1

if not os.path.exists("predicciones.jsonl"):
    sys.exit("No hay predicciones.jsonl: el servicio no esta guardando sus predicciones.")

predicciones = pd.read_json("predicciones.jsonl", lines=True)
cobros = pd.read_csv("cobros.csv")

# DONE 4: une predicciones y cobros por id_prediccion (pd.merge), calcula el
# error absoluto de cada viaje, agrega la columna "semana" con el lunes de
# la semana del viaje (fecha_hora_inicio.dt.to_period("W").dt.start_time.dt.date),
# y agrupa por semana: "viajes" (cuantos) y "mae" (el promedio del error).
unidos = pd.merge(predicciones, cobros, on="id_prediccion")
unidos["error"] = (unidos["tarifa_estimada"] - unidos["tarifa_cobrada"]).abs()
unidos["semana"] = pd.to_datetime(unidos["fecha_hora_inicio"]).dt.to_period("W").dt.start_time.dt.date
por_semana = unidos.groupby("semana").agg(viajes=("error", "size"), mae=("error", "mean"))

por_semana["veces_la_referencia"] = (por_semana["mae"] / MAE_REFERENCIA).round(2)
print(por_semana.to_string())
