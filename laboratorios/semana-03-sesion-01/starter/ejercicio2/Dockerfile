# Ejercicio 2: imagen de resumir_clientes.py, con el mismo patron del
# Ejercicio 1. Corre bash comprobar.sh para revisar tu avance.

# DONE 1: imagen base, con la misma version de Python del Ejercicio 1.
FROM python:3.11-slim

# DONE 2: carpeta de trabajo, dependencias y codigo, en el orden que
# aprovecha la cache.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DONE 3: comando por defecto: python resumir_clientes.py
# Carpeta de datos: se monta como volumen (datos/ local -> /app/datos, donde la leen los scripts).
RUN mkdir -p /app/datos
VOLUME /app/datos

CMD ["python", "resumir_clientes.py"]