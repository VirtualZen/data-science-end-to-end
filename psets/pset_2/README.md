# PSet 2: Pipeline de datos del portafolio de inversiones

Allan Paul Gómez Ehmig · 00351916 · MSDS 6003 Fundamentos de Ciencia de Datos (USFQ)

Pipeline ELT reproducible para el proyecto del PSet 1 (Idea 3: portafolio de acciones del S&P 500 que cotizan en la NYSE, con rebalanceo mensual):

```
Fuente → Kestra → Raw → dbt → Bronze → dbt → Silver → dbt → Gold → Spark → OBT   (Snowflake)
```

- **Fuentes** (públicas, sin credenciales): precios diarios de Yahoo Finance (`yfinance`) para las acciones que alguna vez estuvieron en el S&P 500 y para `^GSPC`, `^NYA` e `^IRX`; composición histórica del S&P 500 ([hanshof/sp500_constituents](https://github.com/hanshof/sp500_constituents)); listados y bolsa de cada símbolo ([Nasdaq Trader](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)).
- **Destino**: Snowflake, base `PORTAFOLIO`, con un esquema por capa: `RAW`, `BRONZE`, `SILVER`, `GOLD`, `OBT` y `CALIDAD`.
- **Documento técnico**: [`docs/PSet2_memo_Gomez_Ehmig.pdf`](docs/PSet2_memo_Gomez_Ehmig.pdf). Diagramas: [arquitectura](docs/arquitectura.png) y [modelo dimensional](docs/modelo_dimensional.png).
- Diferencias con `psets/pset-02/README.md`: ver [`disclaimer.txt`](disclaimer.txt).

## Estructura

```
pset_2/
├── docker-compose.yml        Kestra + Postgres, Spark (maestro y trabajador), imágenes de tareas
├── .env.example              variables necesarias (copiar como .env; .env no se sube)
├── README.md
├── disclaimer.txt
├── scripts/preparar_env.sh   arma los secretos de Kestra a partir de .env
├── kestra/
│   ├── Dockerfile, requirements.txt   imagen pset2-ingesta
│   ├── scripts/extraer_cargar.py      extracción y carga a RAW (modos diario e histórico)
│   ├── flows/                         ingesta_diaria, backfill_historico, transformar
│   ├── sql/snowflake_setup.sql        bodega, base, esquemas, rol, usuario y tablas RAW
│   └── subir_flows.sh                 crea o actualiza los flows por la API de Kestra
├── dbt/                      proyecto dbt (Bronze, Silver, Gold, CALIDAD) + tests; imagen pset2-dbt
├── spark/                    imagen pset2-spark (con el conector de Snowflake) y jobs/construir_obt.py
├── docs/                     memo, diagramas y fuentes de los diagramas (.dot)
└── pruebas_locales/          prueba del código con DuckDB y Spark local, sin Snowflake
```

## Requisitos

- Docker con Docker Compose v2.24 o superior.
- Una cuenta de Snowflake (la prueba gratuita de 30 días sirve: https://signup.snowflake.com/).
- `openssl` para generar el par de llaves.

## Cómo correr el pipeline

Todos los comandos se corren desde `psets/pset_2/`.

### 1. Variables de entorno

```bash
cp .env.example .env
```

Completa `SNOWFLAKE_ACCOUNT` con el identificador de tu cuenta (Snowsight → menú de la cuenta → *Account* → *Account identifier*, formato `ORGANIZACION-CUENTA`). Los demás valores ya coinciden con lo que crea el paso 3.

### 2. Par de llaves para el usuario de servicio

El usuario del pipeline es de tipo `SERVICE`: no usa contraseña, se autentica con un par de llaves.

```bash
mkdir -p secrets
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out secrets/snowflake_llave.p8 -nocrypt
openssl rsa -in secrets/snowflake_llave.p8 -pubout -out secrets/snowflake_llave.pub
grep -v -- '-----' secrets/snowflake_llave.pub | tr -d '\n'; echo   # llave pública en una línea
```

`secrets/` está en `.gitignore`: la llave privada nunca se sube.

### 3. Objetos en Snowflake

En Snowsight, abre una hoja de trabajo SQL, pega [`kestra/sql/snowflake_setup.sql`](kestra/sql/snowflake_setup.sql), reemplaza `<LLAVE_PUBLICA>` con la línea del paso anterior y ejecútalo completo con el rol `ACCOUNTADMIN`. Crea la bodega `PSET2_WH` (XSMALL, se suspende a los 60 s), la base `PORTAFOLIO` con sus seis esquemas, el rol `PSET2_ROL`, el usuario `PSET2_SERVICIO` y las tablas de `RAW`.

### 4. Secretos para Kestra

```bash
bash scripts/preparar_env.sh
```

Copia la llave privada a `SNOWFLAKE_PRIVATE_KEY` en `.env` (para dbt, Spark y la ingesta) y crea `.env_encoded`, donde cada variable va como `SECRET_<NOMBRE>` en base64; así lee Kestra los secretos con `{{ secret('...') }}`. Ninguno de los dos archivos se sube.

### 5. Infraestructura

```bash
docker compose --profile herramientas build    # imágenes pset2-ingesta, pset2-dbt y pset2-spark
docker compose up -d                           # postgres, kestra, spark-master y spark-worker
```

- Kestra: http://localhost:8080 (usuario y clave de `.env`: `KESTRA_USUARIO` y `KESTRA_CLAVE`).
- Spark: http://localhost:8081

Si la construcción de `pset2-spark` falla al descargar el conector de Maven, cambia las versiones con `--build-arg SPARK_SNOWFLAKE_VERSION=... --build-arg SNOWFLAKE_JDBC_VERSION=...`.

### 6. Flows de Kestra

```bash
bash kestra/subir_flows.sh
```

Crea (o actualiza) tres flows en el namespace `usfq.portafolio`:

| Flow | Qué hace | Cuándo corre |
|---|---|---|
| `backfill_historico` | Carga `RAW` año por año (inputs `anio_desde` y `anio_hasta`, por defecto 2010 a 2026) y al final llama a `transformar` | A mano, una vez |
| `ingesta_diaria` | Carga los últimos ~7 días hábiles (los lunes, también composición y listados) y llama a `transformar` | Lunes a viernes, 18:30 hora de Nueva York |
| `transformar` | `dbt build` (modelos y tests) y después el job de Spark que escribe la OBT | Lo llaman los otros dos |

### 7. Primera carga (backfill)

En la UI de Kestra: *Flows* → `usfq.portafolio.backfill_historico` → *Execute*. O por API:

```bash
curl -u admin@kestra.io:Admin1234 -X POST \
  http://localhost:8080/api/v1/main/executions/usfq.portafolio/backfill_historico \
  -F anio_desde=2010 -F anio_hasta=2026
```

Al terminar, `RAW` tiene el histórico y `transformar` ya construyó Bronze, Silver, Gold, `CALIDAD.DQ_METRICAS` y `OBT.OBT_ACCION_MES`. Desde ahí, `ingesta_diaria` corre sola. Para reprocesar un día puntual, ejecuta `ingesta_diaria` con el input `fecha`; para un rango de días programados que se perdieron, usa *Triggers* → `cierre_nyse` → *Backfill executions*.

### 8. Correr dbt o Spark a mano (opcional)

```bash
docker compose --profile herramientas run --rm dbt dbt build --target snowflake
docker compose --profile herramientas run --rm dbt dbt source freshness --target snowflake
docker compose --profile herramientas run --rm spark-job
```

### 9. Verificar en Snowflake

```sql
select * from PORTAFOLIO.CALIDAD.DQ_METRICAS order by dimension, metrica;
select * from PORTAFOLIO.OBT.VALIDACION_OBT;
select conjunto, count(*), count_if(elegible) from PORTAFOLIO.OBT.OBT_ACCION_MES group by 1;
```

## Probar el código sin Snowflake

`pruebas_locales/` carga en DuckDB una muestra real pequeña: la composición completa del S&P 500, ORCL, UBER y VST, y VTI y QQQ como sustitutos de los índices. Con eso corre el mismo proyecto dbt (target `local`) y el job de Spark en modo local. Sirve solo para verificar el código; no son los datos del proyecto.

```bash
pip install dbt-duckdb duckdb pandas pyarrow "pyspark==3.5.3"   # requiere Java 17
python pruebas_locales/cargar_muestra.py
(cd dbt && DBT_PROFILES_DIR=. dbt build --target local --vars '{exigir_tasa_libre_riesgo: false}')
python pruebas_locales/probar_spark_local.py
```

Resultado esperado: dbt termina con `PASS=76 WARN=1 ERROR=0`. La advertencia es `assert_cobertura_sp500_por_dia`, porque la muestra solo tiene 3 acciones. Spark imprime 11 controles `[OK]` y escribe la OBT con 330 filas.

## Batch o streaming

El pipeline es batch: una corrida por día hábil después del cierre. La decisión que habilita (qué acciones tener el mes siguiente) se toma una vez al mes con precios de cierre, así que un dato con horas o un día de antigüedad no le quita valor. Ver la sección 6 del memo.

## Seguridad

No se sube ninguna contraseña, token, llave ni dato: `.env`, `.env_encoded`, `secrets/`, `*.p8`, los artefactos de dbt y las bases de prueba están en `.gitignore`. Las credenciales llegan a los contenedores como variables de entorno (desde `.env`) o como secretos de Kestra (desde `.env_encoded`).
