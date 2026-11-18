"""Genera dbt/seeds/calendario_nyse.csv: los dias en que la NYSE abre, segun
pandas_market_calendars (feriados, cierres extraordinarios y medias jornadas).
dbt lo carga como seed; Silver lo usa para detectar faltantes (un fin de semana o un
feriado no es un dato faltante). Correr de nuevo una vez al anio para extender el rango.

Uso, desde psets/pset-03/pipeline/:   python scripts/generar_calendario_nyse.py [--hasta 2027-12-31]
"""
import argparse
from pathlib import Path

import pandas_market_calendars as mcal

p = argparse.ArgumentParser()
p.add_argument("--desde", default="2000-01-01")
p.add_argument("--hasta", default="2027-12-31")
a = p.parse_args()

nyse = mcal.get_calendar("NYSE")
s = nyse.schedule(start_date=a.desde, end_date=a.hasta)
salida = Path(__file__).resolve().parent.parent / "dbt" / "seeds" / "calendario_nyse.csv"
salida.parent.mkdir(parents=True, exist_ok=True)
dur = (s["market_close"] - s["market_open"]).dt.total_seconds() / 3600
out = s.assign(fecha=s.index.date, media_jornada=(dur < 6.4))[["fecha", "media_jornada"]]
out.to_csv(salida, index=False)
print(f"{len(out)} dias bursatiles de {a.desde} a {a.hasta} -> {salida}")
