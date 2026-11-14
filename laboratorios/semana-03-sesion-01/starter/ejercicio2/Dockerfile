# Ejercicio 2: imagen de resumir_clientes.py, con el mismo patron del
# Ejercicio 1. Corre bash comprobar.sh para revisar tu avance.

# TODO 1: imagen base, con la misma version de Python del Ejercicio 1.
FROM python:3.11-slim

# TODO 2: carpeta de trabajo, dependencias y codigo, en el orden que
# aprovecha la cache.
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# TODO 3: comando por defecto: python resumir_clientes.py
# Carpeta de datos: se monta como volumen (datos/ local -> /app/data-contenedor).
RUN mkdir -p /app/data-contenedor
VOLUME /app/data-contenedor

CMD ["python", "resumir_clientes.py"]