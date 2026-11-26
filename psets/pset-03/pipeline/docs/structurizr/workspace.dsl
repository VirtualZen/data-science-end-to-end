// Modelo C4 del pipeline copiado al PSet 3 (psets/pset-03/pipeline, base PORTAFOLIO_P3).
// Diferencias con el PSet 2: base PORTAFOLIO_P3, imagenes pset3-*, avisos por correo,
// primera carga automatica, CALIDAD ampliada, 17 controles en la OBT, OBT diaria y pruebas de Spark.
// ver_diagramas.sh abre la UI (Structurizr Lite) y exportar_diagramas.sh exporta con el CLI.
workspace "Pipeline de datos del portafolio de inversiones (PSet 3)" "PSet 3 · MSDS 6003 · Allan Paul Gómez Ehmig (00351916)" {

    model {
        asesor = person "Asesor de inversiones" "Usuario de la herramienta: revisa ejecuciones y avisos, y consume la OBT (snapshot) para la decisión mensual."

        yahoo = softwareSystem "Yahoo Finance" "Precios diarios OHLCV y cierre ajustado (API no oficial, vía yfinance): acciones, ^GSPC, ^NYA, ^IRX." "Externo"
        github = softwareSystem "GitHub (fuentes de referencia)" "Composición histórica del S&P 500 (chinobing) y listados de bolsa (rreichel3)." "Externo"
        gmail = softwareSystem "Gmail (SMTP)" "Envía los avisos Success / Fail al correo del asesor (contraseña de aplicación, secreto AVISO_CLAVE_APP)." "Externo"
        modelado = softwareSystem "Modelado del PSet 3" "psets/pset-03: src/datos.py exporta la OBT a data/obt.parquet (sha256); notebooks, MLflow y Model Registry." "Interno"

        pipeline = softwareSystem "Pipeline de datos del portafolio" "ELT reproducible: Fuente → Kestra → Raw → dbt → Bronze → Silver → Gold → Spark → OBT, en PORTAFOLIO_P3." {
            kestra = container "Kestra" "Orquestación: ingesta_diaria (L–V 18:30 NY, retries, recuperación; con RAW vacía hace el histórico desde 2010), backfill_historico (recarga por año), transformar y avisos (usfq.avisos)." "Kestra 2.0.7 · Docker · UI :8090"
            postgres = container "Postgres" "Estado interno de Kestra (flows, ejecuciones, colas)." "PostgreSQL 18 · Docker" "BaseDatos"
            ingesta = container "Tarea de ingesta" "extraer_cargar.py: descarga precios, composición y listados; traduce símbolos con equivalencias_tickers; no guarda la sesión en curso; carga a RAW (append-only, con lote)." "Python 3.11 · imagen pset3-ingesta"
            dbt = container "Tarea dbt" "dbt build: Bronze (staging), Silver (calendario NYSE, imputación de huecos cortos, retornos, membresía), Gold (dos hechos y tres dimensiones) y CALIDAD (dq_metricas, dq_huecos_por_ticker, dq_universo_por_fecha); tests de integridad y negocio." "dbt Core + dbt-snowflake · imagen pset3-dbt"
            spark = container "Driver Spark / tarea OBT" "construir_obt.py: lee Gold, construye acción por mes, verifica 17 controles (incluye mercado del mes siguiente solo con meses cerrados) y escribe OBT." "Spark 3.5.3 · pset3-spark · tarea efímera"
            master = container "spark-master" "Coordina los recursos del clúster; servicio persistente de Compose." "Spark 3.5.3 · RPC :7077 · UI :8081"
            worker = container "spark-worker" "Ejecuta las tareas distribuidas; ofrece 2 GB al ejecutor." "Spark 3.5.3 · pset3-spark"
            reconstruir = container "reconstruir_obt.sh" "Script del asesor: pruebas (ingesta y Spark en Docker), imágenes, transformar con etiqueta origen=manual, evidencias, snapshot y aviso final." "bash · uv · Docker" "Script"
            snowflake = container "Snowflake · base PORTAFOLIO_P3" "Esquemas RAW, BRONZE, SILVER, GOLD, OBT y CALIDAD. Bodega PSET2_WH (XSMALL, autosuspensión). La base PORTAFOLIO del PSet 2 no se modifica." "SaaS" "BaseDatos"
        }

        asesor -> kestra "Supervisa ejecuciones; lanza recargas puntuales" "UI en localhost:8090"
        asesor -> reconstruir "Reconstruye la OBT tras un cambio del pipeline"
        reconstruir -> kestra "Sube flows y lanza transformar" "API REST"
        reconstruir -> gmail "Envía Success / Fail del script" "notificar.py, SMTPS"
        kestra -> postgres "Guarda su estado en"
        kestra -> ingesta "Ejecuta como contenedor de tarea (trigger L–V 18:30 NY; reintentos exponenciales)"
        kestra -> dbt "Ejecuta al terminar la ingesta (subflow transformar)"
        kestra -> spark "Ejecuta spark-submit tras dbt"
        kestra -> gmail "Envía Success / Fail al terminar cada ingesta (flow avisos)" "MailExecution, SMTPS"
        gmail -> asesor "Entrega los avisos"
        ingesta -> yahoo "Descarga OHLCV diario (yfinance, por lotes con reintentos)"
        ingesta -> github "Descarga composición histórica y listados de bolsa"
        ingesta -> snowflake "Carga RAW con write_pandas (append-only + bitácora)"
        dbt -> snowflake "Transforma RAW → BRONZE → SILVER → GOLD y calcula CALIDAD"
        spark -> master "Solicita recursos del clúster" "spark://spark-master:7077"
        master -> worker "Asigna ejecutores"
        spark -> worker "Coordina tareas y resultados"
        worker -> snowflake "Lee y escribe particiones mediante el conector Snowflake"
        spark -> snowflake "Lee GOLD y escribe OBT.OBT_ACCION_MES, OBT.OBT_ACCION_DIA y VALIDACION_OBT"
        modelado -> snowflake "Exporta la OBT con SELECT (snapshot con sha256)"
        asesor -> snowflake "Consulta la OBT y las métricas de calidad" "Snowsight"
    }

    views {
        systemContext pipeline "contexto" "Nivel 1: el pipeline, su usuario, las fuentes, los avisos y el modelado del PSet 3." {
            include *
            autoLayout lr
        }

        container pipeline "contenedores" "Nivel 2: servicios persistentes, tareas efímeras, script de reconstrucción y Snowflake SaaS." {
            include *
            autoLayout lr
        }

        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Externo" {
                background #999999
                color #ffffff
            }
            element "Interno" {
                background #6b8e23
                color #ffffff
            }
            element "Script" {
                background #7a7a7a
                color #ffffff
            }
            element "BaseDatos" {
                shape Cylinder
                background #2a6a4f
                color #ffffff
            }
        }
    }
}
