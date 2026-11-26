"""Estado y progreso de una ejecucion de Kestra, para los bucles de espera de los scripts.

Imprime el estado actual en stdout (para el `case` de bash) y, en stderr, una linea de progreso:

  [20:05:12] transformar RUNNING | inicio 20:01:03, van 4m 09s | tareas 1/2, en curso: spark_obt (intento 1)
             | esperado ~7m 30s (mediana de 5 exitosas): fin ~20:08:33, faltan ~3m 21s

La duracion esperada es la mediana de las ultimas ejecuciones SUCCESS del mismo flow (sin
ellas, solo se muestra lo transcurrido). Horas en la zona local de la maquina. Solo biblioteca
estandar: corre con el python3 del sistema, sin uv.

Uso:  python3 scripts/progreso_kestra.py <API> <usuario:clave> <id_ejecucion>
"""
from __future__ import annotations

import base64
import json
import re
import statistics
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

TERMINALES = {"SUCCESS", "FAILED", "KILLED", "WARNING", "CANCELLED"}


def duracion_iso(texto: str | None) -> float | None:
    """'PT1H7M19.9S' -> segundos."""
    if not texto:
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", texto)
    if not m:
        return None
    d, h, mi, s = (float(x) if x else 0.0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def fecha(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def legible(segundos: float) -> str:
    segundos = int(round(segundos))
    h, r = divmod(segundos, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def linea(ejecucion: dict, total_tareas: int | None, esperados: list[float], ahora: datetime) -> str:
    estado = ejecucion["state"]["current"]
    inicio = fecha(ejecucion["state"]["startDate"])
    van = (ahora - inicio).total_seconds()
    local = lambda t: t.astimezone().strftime("%H:%M:%S")
    partes = [f"[{local(ahora)}] {ejecucion.get('flowId', '?')} {estado}",
              f"inicio {local(inicio)}, van {legible(van)}"]
    tareas = ejecucion.get("taskRunList") or []
    if tareas:
        hechas = sum(t["state"]["current"] in TERMINALES for t in tareas)
        curso = [t for t in tareas if t["state"]["current"] not in TERMINALES]
        total = max(total_tareas or 0, len(tareas))
        texto = f"tareas {hechas}/{total}"
        if curso:
            t = curso[-1]
            texto += f", en curso: {t['taskId']} (intento {len(t.get('attempts') or []) or 1})"
        partes.append(texto)
    if esperados:
        med = statistics.median(esperados)
        fin = inicio + timedelta(seconds=med)
        falta = med - van
        cola = f"faltan ~{legible(falta)}" if falta >= 0 else f"va {legible(-falta)} sobre lo habitual"
        partes.append(f"esperado ~{legible(med)} (mediana de {len(esperados)} exitosas): "
                      f"fin ~{local(fin)}, {cola}")
    return " | ".join(partes)


def pedir(api: str, auth: str, ruta: str):
    req = urllib.request.Request(f"{api}{ruta}")
    req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> None:
    api, auth, ide = sys.argv[1:4]
    e = pedir(api, auth, f"/executions/{ide}")
    print(e["state"]["current"])
    try:
        ns, flow = e["namespace"], e["flowId"]
        total = len(pedir(api, auth, f"/flows/{ns}/{flow}").get("tasks") or []) or None
        previas = pedir(api, auth, f"/executions/search?namespace={ns}&flowId={flow}"
                                   f"&state=SUCCESS&size=20&sort=state.startDate:desc").get("results", [])
        # Filtro tambien aqui: la busqueda de Kestra puede traer ejecuciones de otros estados o
        # flows (durante un RETRYING la mediana salto de 3 min a 4 s).
        previas = [p for p in previas if p["id"] != ide and p.get("flowId") == flow
                   and p.get("namespace") == ns and p["state"]["current"] == "SUCCESS"]
        esperados = [d for d in (duracion_iso(p["state"].get("duration")) for p in previas) if d][:5]
        print(linea(e, total, esperados, datetime.now(timezone.utc)), file=sys.stderr)
    except Exception as err:  # el progreso es informativo: nunca debe cortar la espera
        print(f"[progreso no disponible: {err}]", file=sys.stderr)


if __name__ == "__main__":
    main()
