# Semana 3, Sesión 1: cómo correr los ejercicios

Los dos ejercicios se construyen y se corren con Docker, **desde la carpeta de cada ejercicio**. Los scripts leen y
escriben en `datos/` (dentro del contenedor, `/app/datos`), así que el `docker run` siempre lleva el volumen
`-v $(pwd)/datos:/app/datos`.

## Por qué hace falta `-v $(pwd)/datos:/app/datos`

- `.dockerignore` excluye `datos/`, así que la imagen **no trae los CSV**.
- Sin el volumen, el contenedor no encuentra la entrada y falla:
  `FileNotFoundError: [Errno 2] No such file or directory: 'datos/ventas.csv'`.
- `$(pwd)/datos` es la carpeta `datos/` del ejercicio en tu máquina; `/app/datos` es donde el script la espera dentro del
  contenedor (`WORKDIR /app` + la ruta relativa `datos/`).
- Con el volumen, el script lee la entrada de tu carpeta y el resultado **queda en tu carpeta**, no se pierde al
  terminar el contenedor.
- El `VOLUME /app/datos` de los Dockerfile y el `docker-compose.yml` del ejercicio 2 usan la misma ruta
  (`/app/datos`), asi que el `docker run -v` de arriba y `docker compose up` montan la carpeta en el mismo lugar.

## Ejercicio 1: `procesar.py`

```bash
cd laboratorios/semana-03-sesion-01/starter/ejercicio1
docker build -t procesar-ventas .
docker run --rm -v $(pwd)/datos:/app/datos procesar-ventas
```

- Lee `datos/ventas.csv` y guarda `datos/resumen_ventas.csv` (total por producto).
- Salida esperada: la versión de Python y de pandas, y el resumen: monitor 409.99, teclado 117.50, mouse 33.50.

## Ejercicio 2: `resumir_clientes.py` y `contar_filas.py`

```bash
cd laboratorios/semana-03-sesion-01/starter/ejercicio2
docker build -t resumir-clientes .
```

**TODO 4: el `CMD` por defecto (`resumir_clientes.py`), con volumen**

```bash
docker run --rm -v $(pwd)/datos:/app/datos resumir-clientes
```

- Lee `datos/clientes.csv` y guarda `datos/clientes_por_ciudad.csv` (Cuenca 2, Guayaquil 2, Quito 4).

**TODO 5: la misma imagen, otro comando, sin volver a construir**

```bash
docker run --rm -v $(pwd)/datos:/app/datos resumir-clientes python contar_filas.py
```

- Lo que escribes después del nombre de la imagen reemplaza el `CMD`.
- Lee `datos/clientes.csv` y guarda `datos/conteo.txt` con el total de clientes (`8`).

**Comprobación**

```bash
bash comprobar.sh
```

Debe imprimir `TODO 1: OK` hasta `TODO 5: OK`. Los TODO 4 y 5 comprueban que existan `datos/clientes_por_ciudad.csv` y
`datos/conteo.txt`.

## Notas

- Corre cada bloque desde su carpeta: `$(pwd)` debe ser la carpeta del ejercicio.
- `--rm` borra el contenedor al terminar; los resultados se conservan porque están en tu carpeta `datos/`.
- Si cambias un script y vuelves a construir, la capa de `pip install` se reutiliza de la cache, porque
  `requirements.txt` se copia antes que el código.
