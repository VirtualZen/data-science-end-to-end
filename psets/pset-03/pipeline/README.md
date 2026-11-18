# Pipeline de datos para el PSet 3 (copia de `psets/pset-02/`)

El PSet 2 ya se entregó y `psets/pset-02/` no se modifica. Esta carpeta es una copia
de su pipeline (Fuente → Kestra → RAW → dbt Bronze/Silver/Gold → Spark → OBT en
Snowflake) para volver a correrlo con los cambios que pida el PSet 3, sin tocar lo
entregado. La explicación completa de cada capa está en
[`../../pset-02/README.md`](../../pset-02/README.md); aquí solo va lo que cambia.

## Qué cambia frente a `pset-02`

| | `psets/pset-02` (entregado) | `psets/pset-03/pipeline` |
|---|---|---|
| Base de Snowflake | `PORTAFOLIO` | `PORTAFOLIO_P3` (mismos seis esquemas) |
| Bodega, rol y usuario | `PSET2_WH`, `PSET2_ROL`, `PSET2_SERVICIO` | los mismos (misma llave) |
| Proyecto de Compose | `pset2` | `pset3-pipeline` (Postgres y Kestra con volúmenes propios) |
| Imágenes y red | `pset2-ingesta`, `pset2-dbt`, `pset2-spark`, `pset2_red` | `pset3-ingesta`, `pset3-dbt`, `pset3-spark`, `pset3_red` |
| Proyecto uv | `pset-02-pipeline` | `pset-03-pipeline` (mismas versiones) |
| No se copió | — | `docs/` (evidencias del PSet 2), memo, ZIP de entrega, PDF y rúbrica |

Los scripts escriben sus evidencias nuevas en `docs/corrida/` y `docs/calidad/` de
esta carpeta. La OBT nueva la lee `../src/datos.py` (`SNOWFLAKE_DATABASE`, por
defecto `PORTAFOLIO_P3`).

No levantes este Compose a la vez que el de `pset-02` (usan los mismos puertos) ni a
la vez que MLflow de `pset-03` con la memoria disponible: hubo un OOM de Kestra.

## Cómo correrlo

Todos los comandos, desde `psets/pset-03/pipeline/`.

1. **Credenciales.** Reutiliza las del PSet 2 (no se suben a git):
   ```bash
   cp -R ../../pset-02/secrets .
   cp ../../pset-02/.env .env
   ```
   En `.env`, cambia `SNOWFLAKE_DATABASE=PORTAFOLIO` por `SNOWFLAKE_DATABASE=PORTAFOLIO_P3`.
   Para partir de cero, sigue los pasos 1 y 2 del README del PSet 2 con `.env.example`.
2. **Base nueva en Snowflake.** En Snowsight, con `ACCOUNTADMIN`, ejecuta
   [`kestra/sql/snowflake_setup.sql`](kestra/sql/snowflake_setup.sql). Crea
   `PORTAFOLIO_P3`, sus esquemas, los permisos para `PSET2_ROL` y las tablas de `RAW`.
   La bodega, el rol y el usuario ya existen (`IF NOT EXISTS`), así que no cambia la
   llave; `<LLAVE_PUBLICA>` solo se usa en una cuenta nueva.
3. **Secretos para Kestra:** `bash scripts/preparar_env.sh`
4. **Infraestructura:**
   ```bash
   docker compose --profile herramientas build
   docker compose up -d
   bash kestra/subir_flows.sh
   ```
   Kestra: http://localhost:8090 · Spark: http://localhost:8081
5. **Carga completa:** no requiere paso manual. Si `RAW.PRECIOS_DIARIOS` esta vacia, la primera
   `ingesta_diaria` (programada o lanzada a mano) carga el historico desde 2010 anio por anio
   (~20 minutos) y luego llama a `transformar` (dbt build + Spark → OBT). Para recargar un rango
   de anios sigue disponible `usfq.portafolio.backfill_historico`.
6. **Evidencias (opcional):** `uv sync --group dev` y luego
   `uv run python scripts/exportar_metricas.py` y `uv run python scripts/verificar_snowflake.py`.
7. **Apagar antes de MLflow:** `docker compose down` (sin `-v` para conservar el estado de Kestra).
8. **Snapshot para los notebooks**, desde `psets/pset-03/`: `uv run python -m src.datos`.

## Reconstruir la OBT despues de un cambio

```bash
bash scripts/reconstruir_obt.sh
```

Corre las pruebas (ingesta con uv; Spark en su imagen), reconstruye las imagenes, levanta
Compose, sube los flows, ejecuta `transformar` (dbt build + Spark) hasta que termine,
exporta las evidencias a `docs/corrida/`, baja Compose (sin `-v`) y genera el snapshot de
`../data/obt.parquet`. No lanza la ingesta de Yahoo.

Avisos: al terminar manda `Success: reconstruir_obt` o `Fail: reconstruir_obt` con el paso que
fallo (`scripts/notificar.py`, mismas credenciales `AVISO_*` de `.env`). Ademas lanza
`transformar` con la etiqueta `origen=manual`, y el flow de avisos manda su propio correo.

La ingesta no guarda la sesion del dia si corre con la bolsa abierta (antes de las 16:30 de
Nueva York): ese precio es intradia, no el cierre. La trae la siguiente corrida.

## Probar la orquestacion (reintentos, avisos y cron)

```bash
bash scripts/probar_ingesta_y_reintentos.sh
```

Lanza una `ingesta_diaria` manual (debe terminar en SUCCESS), otra con `simular_falla=true`
(4 intentos con espera exponencial, `registrar_falla` y aviso "Fail"; ~15 minutos) y, si aun no
son las 18:45 de Nueva York, espera la ingesta del trigger de las 18:30 (`ESPERAR_CRON=0` la
omite). Guarda `docs/corrida/kestra_pruebas.json` y `kestra_estados.json`.

## Avisos por correo

El flow `usfq.avisos.avisos` (`kestra/flows/avisos.yml`) envía un correo al terminar cada
ejecución de `ingesta_diaria` o `backfill_historico`, y de `transformar` cuando se lanza a mano
con la etiqueta `origen=manual`. El asunto empieza con `Success` o `Fail`.

1. En `.env`, completa `AVISO_CORREO` (cuenta de Gmail) y `AVISO_CLAVE_APP` (contraseña de
   aplicación de Google: Cuenta de Google → Seguridad → Verificación en dos pasos →
   Contraseñas de aplicaciones).
2. `bash scripts/preparar_env.sh`
3. `docker compose up -d --force-recreate kestra` (Kestra lee los secretos al arrancar).
4. `bash kestra/subir_flows.sh`

Solo avisa mientras el Compose esté levantado.

## Pruebas

```bash
uv sync --group dev
uv run pytest kestra/tests spark/tests      # los de Spark se saltan sin pyspark o sin Java
```

Las pruebas de Spark también corren dentro de la imagen de Spark, sin Java ni pyspark en
tu equipo. Antes de pytest comprueba que pyspark y Java existen, así que no se saltan:

```bash
docker compose --profile pruebas run --rm --build spark-pruebas
```

`spark/Dockerfile` tiene tres etapas: `base` (Spark + jars de Snowflake), `pruebas`
(base + pytest + jobs/ + tests/) y `runtime` (base + jobs/, la que usan maestro,
trabajador y `spark-job`). Los jars se bajan con `spark/descargar_jars.py` a un cache de
BuildKit y pytest con el cache de pip, así que los rebuilds no vuelven a descargarlos;
cambiar `jobs/` o `tests/` solo rehace la última capa.
