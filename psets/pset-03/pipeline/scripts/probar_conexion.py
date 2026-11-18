"""Prueba la conexion a Snowflake con las credenciales de .env (usuario de servicio y
llave privada). Verifica bodega, base, esquemas y tablas RAW creadas por setup.sql.

Uso, desde psets/pset-03/pipeline/:
  uv sync
  uv run python scripts/probar_conexion.py
"""
from pathlib import Path
import base64

import snowflake.connector

env = {}
for linea in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in linea and not linea.lstrip().startswith("#"):
        k, _, v = linea.partition("=")
        env[k.strip()] = v.strip()

llave = env.get("SNOWFLAKE_PRIVATE_KEY", "")
if not llave:
    raise SystemExit("SNOWFLAKE_PRIVATE_KEY vacia en .env: corre antes scripts/preparar_env.sh")

con = snowflake.connector.connect(
    account=env["SNOWFLAKE_ACCOUNT"],
    user=env["SNOWFLAKE_USER"],
    private_key=base64.b64decode(llave),
    role=env.get("SNOWFLAKE_ROLE", "PSET2_ROL"),
    warehouse=env.get("SNOWFLAKE_WAREHOUSE", "PSET2_WH"),
    database=env.get("SNOWFLAKE_DATABASE", "PORTAFOLIO_P3"),
    schema="RAW",
    application="pset3_prueba",
)
cur = con.cursor()
print("Conectado como:", cur.execute(
    "select current_user(), current_role(), current_warehouse(), current_database()").fetchone())
esquemas = [r[1] for r in cur.execute("show schemas in database PORTAFOLIO_P3").fetchall()]
print("Esquemas:", sorted(set(esquemas) & {"RAW", "BRONZE", "SILVER", "GOLD", "OBT", "CALIDAD"}))
tablas = [r[1] for r in cur.execute("show tables in schema PORTAFOLIO_P3.RAW").fetchall()]
print("Tablas RAW:", sorted(tablas))
con.close()
print("Conexion OK: setup.sql quedo bien aplicado.")
