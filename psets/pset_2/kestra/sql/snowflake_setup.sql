-- Configuracion inicial de Snowflake para el PSet 2. Se corre una sola vez, en una
-- hoja de trabajo de Snowsight, con el rol ACCOUNTADMIN.
-- Antes: genera el par de llaves (ver README, paso 2) y pega la llave PUBLICA en
-- <LLAVE_PUBLICA>, sin las lineas BEGIN/END y sin saltos de linea.

USE ROLE ACCOUNTADMIN;

-- Bodega de computo pequena que se suspende sola (cuida los creditos de prueba).
CREATE WAREHOUSE IF NOT EXISTS PSET2_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS PORTAFOLIO;

-- Una capa por esquema: Raw (lo que llega de la fuente), Bronze, Silver, Gold (dbt),
-- OBT (Spark) y CALIDAD (metricas de calidad que calcula dbt).
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.RAW;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.BRONZE;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.SILVER;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.GOLD;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.OBT;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO.CALIDAD;

-- Rol y usuario de servicio del pipeline (sin contrasena: par de llaves).
CREATE ROLE IF NOT EXISTS PSET2_ROL;
GRANT USAGE ON WAREHOUSE PSET2_WH TO ROLE PSET2_ROL;
GRANT USAGE ON DATABASE PORTAFOLIO TO ROLE PSET2_ROL;
GRANT ALL ON ALL SCHEMAS IN DATABASE PORTAFOLIO TO ROLE PSET2_ROL;
GRANT ALL ON FUTURE TABLES IN DATABASE PORTAFOLIO TO ROLE PSET2_ROL;
GRANT ALL ON FUTURE VIEWS IN DATABASE PORTAFOLIO TO ROLE PSET2_ROL;

CREATE USER IF NOT EXISTS PSET2_SERVICIO
  TYPE = SERVICE
  DEFAULT_ROLE = PSET2_ROL
  DEFAULT_WAREHOUSE = PSET2_WH
  DEFAULT_NAMESPACE = PORTAFOLIO.RAW
  RSA_PUBLIC_KEY = '<LLAVE_PUBLICA>';
GRANT ROLE PSET2_ROL TO USER PSET2_SERVICIO;
-- Para ver las tablas desde tu propio usuario en Snowsight:
GRANT ROLE PSET2_ROL TO ROLE ACCOUNTADMIN;

-- Tablas Raw. Guardan los datos tal como llegan: solo se agregan filas (append-only),
-- con el lote y la hora de carga. Los duplicados por re-ingesta o backfill se
-- resuelven en Bronze, que conserva la carga mas reciente de cada clave.
USE ROLE PSET2_ROL;
USE WAREHOUSE PSET2_WH;
USE SCHEMA PORTAFOLIO.RAW;

CREATE TABLE IF NOT EXISTS PRECIOS_DIARIOS (
    TICKER       VARCHAR,          -- simbolo tal como se pidio a Yahoo (BRK-B, ^GSPC)
    FECHA        DATE,
    OPEN         FLOAT,
    HIGH         FLOAT,
    LOW          FLOAT,
    CLOSE        FLOAT,
    ADJ_CLOSE    FLOAT,            -- cierre ajustado por splits y dividendos
    VOLUME       FLOAT,
    FUENTE       VARCHAR,
    LOTE_ID      VARCHAR,
    INGESTA_TS   TIMESTAMP_NTZ
);

CREATE TABLE IF NOT EXISTS COMPOSICION_SP500 (
    FECHA        DATE,             -- fecha de la foto de la composicion
    TICKERS      VARCHAR,          -- lista separada por comas, tal como viene
    FUENTE       VARCHAR,
    LOTE_ID      VARCHAR,
    INGESTA_TS   TIMESTAMP_NTZ
);

CREATE TABLE IF NOT EXISTS LISTADOS_BOLSA (
    SIMBOLO        VARCHAR,
    NOMBRE         VARCHAR,
    CODIGO_BOLSA   VARCHAR,        -- N=NYSE, A=NYSE American, P=NYSE Arca, Z=Cboe, V=IEX, Q=Nasdaq
    ES_ETF         VARCHAR,
    ES_PRUEBA      VARCHAR,
    ARCHIVO        VARCHAR,        -- otherlisted.txt o nasdaqlisted.txt
    FUENTE         VARCHAR,
    LOTE_ID        VARCHAR,
    INGESTA_TS     TIMESTAMP_NTZ
);

-- Bitacora de cada carga: cuantas filas trajo cada simbolo y si fallo.
CREATE TABLE IF NOT EXISTS INGESTA_LOG (
    LOTE_ID      VARCHAR,
    TICKER       VARCHAR,
    FECHA_DESDE  DATE,
    FECHA_HASTA  DATE,
    FILAS        NUMBER,
    ESTADO       VARCHAR,          -- OK, SIN_DATOS, ERROR
    DETALLE      VARCHAR,
    INGESTA_TS   TIMESTAMP_NTZ
);
