# Ejercicio 1: imagen de procesar.py.
# Este Dockerfile ya construye. Construyelo y correlo antes de tocar nada
# (los comandos estan en el README).

FROM python:3.11-slim
WORKDIR /app

# DONE 1: cambia una linea de procesar.py y vuelve a construir: pandas se
# instala otra vez. Reordena estas lineas para que un cambio en el codigo
# no repita la instalacion de dependencias.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# DONE 2: la imagen no dice que correr. Define el comando por defecto:
# python procesar.py

COPY . .

# Carpeta de datos: se monta como volumen (datos/ local -> /app/datos, donde la leen los scripts).
RUN mkdir -p /app/datos
VOLUME /app/datos

CMD ["python", "procesar.py"]