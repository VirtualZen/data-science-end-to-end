-- PSet 4: esquema PRODUCCION de PORTAFOLIO_P4 (predicciones servidas, monitoreo, alertas y reentrenamientos).
-- Se corre en Snowsight con ACCOUNTADMIN, despues de snowflake_setup.sql. No contiene credenciales.
-- CREATE OR REPLACE: volver a correrlo deja las cuatro tablas vacias, para repetir la simulacion desde cero.
USE ROLE ACCOUNTADMIN;
CREATE SCHEMA IF NOT EXISTS PORTAFOLIO_P4.PRODUCCION;
GRANT ALL ON SCHEMA PORTAFOLIO_P4.PRODUCCION TO ROLE PSET2_ROL;
GRANT ALL ON FUTURE TABLES IN SCHEMA PORTAFOLIO_P4.PRODUCCION TO ROLE PSET2_ROL;
USE ROLE PSET2_ROL;
USE WAREHOUSE PSET2_WH;

-- Una fila por accion y lote: lo que respondio la API (trazabilidad: version -> run_id -> snapshot de la OBT).
CREATE OR REPLACE TABLE PORTAFOLIO_P4.PRODUCCION.PREDICCIONES (
    ID_PREDICCION      VARCHAR(32)  NOT NULL PRIMARY KEY,
    ID_LOTE            VARCHAR(32)  NOT NULL,
    TIMESTAMP_UTC      TIMESTAMP_TZ NOT NULL,
    ANIO_MES           NUMBER(6)    NOT NULL,   -- cierre de mes de las entradas
    MES_OBJETIVO       VARCHAR(7)   NOT NULL,   -- mes que se predice
    ACCION_KEY         VARCHAR      NOT NULL,
    TICKER             VARCHAR,
    ENTRADAS           VARCHAR,                 -- JSON con las 33 features enviadas
    RETORNO_PREDICHO   FLOAT,
    DECISION           VARCHAR(12),
    PESO               FLOAT,
    DECISION_MANUAL    VARCHAR(12),             -- competidor B7 (operacion manual), en paralelo
    PESO_MANUAL        FLOAT,
    MODELO_NOMBRE      VARCHAR,
    MODELO_VERSION     VARCHAR,
    MODELO_ALIAS       VARCHAR,
    RUN_ID             VARCHAR(32),
    RESPALDO           BOOLEAN,
    USADO              VARCHAR,
    LATENCIA_MS        FLOAT,
    SINTETICO          BOOLEAN,                 -- lote de deriva inducida (docs/simulacion.md)
    HUELLA_OBT         VARCHAR(12)              -- md5[:12] del snapshot de OBT_ACCION_MES leido
);

-- Una fila por lote monitoreado: metricas de sistema, datos y modelo (METRICAS guarda el detalle en JSON).
CREATE OR REPLACE TABLE PORTAFOLIO_P4.PRODUCCION.MONITOREO (
    ANIO_MES               NUMBER(6) NOT NULL,
    TIMESTAMP_UTC          TIMESTAMP_TZ NOT NULL,
    MODELO_VERSION         VARCHAR,
    SINTETICO              BOOLEAN,
    N_ACCIONES             NUMBER,      -- elegibles del mes
    N_ENVIADAS             NUMBER,      -- sin nulos, enviadas a la API
    PCT_INVALIDAS          FLOAT,
    LATENCIA_P50_MS        FLOAT,       -- sistema: ventana desde el envio del lote
    LATENCIA_P95_MS        FLOAT,
    SOLICITUDES            NUMBER,
    ERRORES_4XX            NUMBER,
    ERRORES_5XX            NUMBER,
    PCT_NULOS_MAX          FLOAT,       -- datos
    N_FEATURES_FUERA_RANGO NUMBER,
    CATEGORIAS_NO_VISTAS   NUMBER,
    N_PSI_CRITICO          NUMBER,
    PSI_MAX                FLOAT,
    FEATURE_PSI_MAX        VARCHAR,
    Z_PRED_MEDIA           FLOAT,       -- modelo
    TASA_INCLUIR           FLOAT,
    MAE_ULTIMO             FLOAT,
    MAE_PENULTIMO          FLOAT,
    SHARPE_12              FLOAT,       -- negocio
    SHARPE_B5_12           FLOAT,
    SHARPE_MANUAL_12       FLOAT,       -- competidor B7
    RETORNO_MANUAL_ULTIMO  FLOAT,
    COINCIDEN_MANUAL       NUMBER,      -- acciones que incluyen el modelo y la operacion manual
    METRICAS               VARCHAR,     -- JSON con todas las metricas del lote
    DERIVA                 VARCHAR      -- JSON: una entrada por feature (nulos, fuera de rango, PSI, KS, chi2, z)
);

CREATE OR REPLACE TABLE PORTAFOLIO_P4.PRODUCCION.ALERTAS (
    ANIO_MES        NUMBER(6) NOT NULL,
    TIMESTAMP_UTC   TIMESTAMP_TZ NOT NULL,
    ID_ALERTA       VARCHAR(4),
    CAPA            VARCHAR,
    METRICA         VARCHAR,
    UMBRAL          VARCHAR,
    VENTANA         VARCHAR,
    SEVERIDAD       VARCHAR,
    QUIEN_LA_RECIBE VARCHAR,
    ACCION          VARCHAR,
    MODELO_VERSION  VARCHAR
);

CREATE OR REPLACE TABLE PORTAFOLIO_P4.PRODUCCION.REENTRENAMIENTOS (
    TIMESTAMP_UTC       TIMESTAMP_TZ NOT NULL,
    ANIO_MES_LLEGADA    NUMBER(6),
    DISPARADOR          VARCHAR,
    VERSION_CHAMPION    VARCHAR,
    VERSION_CHALLENGER  VARCHAR,
    RUN_ID_CHALLENGER   VARCHAR(32),
    HASTA_ANIO_MES      NUMBER(6),
    LOTES_EVALUACION    VARCHAR,
    MAE_CHAMPION        FLOAT,
    MAE_CHALLENGER      FLOAT,
    RETORNO_CHAMPION    FLOAT,
    RETORNO_CHALLENGER  FLOAT,
    PROMUEVE_REGLA      BOOLEAN,
    MOTIVO_REGLA        VARCHAR,
    APROBADO            BOOLEAN,
    APROBADO_POR        VARCHAR,
    MOTIVO_DECISION     VARCHAR
);
