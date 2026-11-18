"""Snapshot reproducible de las OBT; las credenciales se leen del entorno o .env local.

    uv run python -m src.datos                 # OBT_ACCION_MES -> data/obt.parquet
    uv run python -m src.datos --grano dia     # OBT_ACCION_DIA -> data/obt_dia.parquet

Solo SELECT. Cada Parquet lleva un .json con tabla, sha256, filas y columnas; cargar() rechaza
un snapshot modificado, duplicado o sin las columnas esperadas.
"""
import argparse, base64, hashlib, json, os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from .pipeline import OBT_MES, OBT_DIA

RAIZ = Path(__file__).resolve().parents[1]
# La OBT la construye el pipeline copiado en pipeline/ (base PORTAFOLIO_P3); la base
# PORTAFOLIO queda como la entregada en el PSet 2. Se elige con SNOWFLAKE_DATABASE.
GRANOS = {
    'mes': {'tabla': 'OBT_ACCION_MES', 'archivo': 'obt.parquet', 'clave': ['accion_key', 'anio_mes'],
            'columnas': OBT_MES},
    'dia': {'tabla': 'OBT_ACCION_DIA', 'archivo': 'obt_dia.parquet', 'clave': ['accion_key', 'fecha'],
            'columnas': OBT_DIA},
}


def tabla(grano='mes'):
    return f"{os.environ.get('SNOWFLAKE_DATABASE', 'PORTAFOLIO_P3')}.OBT.{GRANOS[grano]['tabla']}"


def _ruta(grano, ruta=None):
    return Path(ruta or RAIZ / 'data' / GRANOS[grano]['archivo'])


def exportar(destino=None, grano='mes'):
    import snowflake.connector
    if (RAIZ / '.env').exists():
        from dotenv import load_dotenv
        load_dotenv(RAIZ / '.env')
    g = GRANOS[grano]; TABLA = tabla(grano)
    destino = _ruta(grano, destino); destino.parent.mkdir(parents=True, exist_ok=True)
    orden = ', '.join(c.upper() for c in g['clave'])
    with snowflake.connector.connect(account=os.environ['SNOWFLAKE_ACCOUNT'], user=os.environ['SNOWFLAKE_USER'],
                                     private_key=base64.b64decode(os.environ['SNOWFLAKE_PRIVATE_KEY']),
                                     role=os.environ.get('SNOWFLAKE_ROLE', 'PSET2_ROL'),
                                     warehouse=os.environ.get('SNOWFLAKE_WAREHOUSE', 'PSET2_WH')) as con:
        with con.cursor() as cur:
            cur.execute(f'SELECT * FROM {TABLA} ORDER BY {orden}')
            try:   # la diaria tiene ~1,8 millones de filas: Arrow evita filas de Python una por una
                df = cur.fetch_pandas_all()
            except Exception:
                df = pd.DataFrame(cur.fetchall(), columns=[c[0] for c in cur.description])
    df.columns = [c.lower() for c in df.columns]
    falta = [c for c in g['columnas'] if c not in df.columns]
    if falta:
        raise ValueError(f'{TABLA} no tiene {len(falta)} columnas esperadas ({falta[:3]}...): reconstruir la OBT')
    df.to_parquet(destino, index=False)
    meta = {'tabla': TABLA, 'grano': grano, 'snapshot_utc': datetime.now(timezone.utc).isoformat(),
            'sha256': hashlib.sha256(destino.read_bytes()).hexdigest(), 'filas': len(df),
            'columnas': list(df), 'corte': '2023-12-31'}
    destino.with_suffix('.json').write_text(json.dumps(meta, indent=2)); return meta


def cargar(ruta=None, grano='mes'):
    g = GRANOS[grano]; ruta = _ruta(grano, ruta)
    meta = json.loads(ruta.with_suffix('.json').read_text())
    if hashlib.sha256(ruta.read_bytes()).hexdigest() != meta['sha256']:
        raise ValueError('Snapshot modificado; regenerar su procedencia')
    df = pd.read_parquet(ruta)
    if df.duplicated(g['clave']).any():
        raise ValueError(f'{g["tabla"]} duplicada en {g["clave"]}')
    falta = [c for c in g['columnas'] if c not in df.columns]
    if falta:
        raise ValueError(f'Snapshot anterior a F1: faltan {len(falta)} columnas ({falta[:3]}...). '
                         f'Regenerar con "uv run python -m src.datos --grano {grano}"')
    return df, meta


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--salida'); p.add_argument('--grano', choices=list(GRANOS), default='mes')
    a = p.parse_args(); print(json.dumps(exportar(a.salida, a.grano), indent=2))
