"""Ejercicio 1: diagnostico de calidad de lecturas_sensores.csv.

Corre el script antes de tocar nada:

    python3 ejercicio1_diagnostico.py

Corre sin errores y sin los TODO resueltos. Fijate en que numeros y que
fechas salen asi, antes de completar cada TODO.
"""

import pandas as pd

datos = pd.read_csv("lecturas_sensores.csv")
print(f"Filas leidas: {len(datos)}")
print(datos)

print()
print("Paso 1: duplicados")
# DONE 1: cuenta las filas que repiten todas sus columnas y despues
# quitalas de datos.
duplicados = datos.duplicated().sum()
print(f"Filas duplicadas: {duplicados}")
datos = datos.drop_duplicates()
print(f"Filas despues de quitarlas: {len(datos)}")

print()
print("Paso 2: tipos y faltantes visibles")
print(datos.dtypes)
# DONE 2: cuenta los valores faltantes de cada columna.
faltantes = datos.isna().sum()
print(faltantes)

print()
print("Paso 3: faltantes disfrazados de texto")
# DONE 3: convierte temperatura a numero. Lo que no se pueda convertir
# tiene que quedar como faltante, no detener el script.
datos["temperatura_num"] = pd.to_numeric(datos["temperatura"], errors="coerce")
print(f"Temperaturas faltantes antes de convertir: {datos['temperatura'].isna().sum()}")
print(f"Temperaturas faltantes despues de convertir: {datos['temperatura_num'].isna().sum()}")

print()
print("Paso 4: fechas con dos formatos")


# DONE 4: si valor tiene "/", viene como dia/mes/anio; si no, como
# anio-mes-dia. Convierte cada caso con su formato explicito.
def normalizar_fecha(valor):
    formato = "%d/%m/%Y" if "/" in valor else "%Y-%m-%d"
    return pd.to_datetime(valor, format=formato)


datos["fecha_normalizada"] = datos["fecha"].apply(normalizar_fecha)
print(datos[["sensor_id", "fecha", "fecha_normalizada"]])

datos.to_csv("lecturas_limpias.csv", index=False)
print()
print(datos)
print(f"Guardado lecturas_limpias.csv con {len(datos)} filas.")
