"""Envia un aviso por correo con el resultado de un script del pipeline (Success o Fail).

Usa las mismas credenciales que el flow de avisos de Kestra, desde pipeline/.env:
  AVISO_CORREO      cuenta de Gmail que envia y recibe
  AVISO_CLAVE_APP   contrasena de aplicacion de Google
Si faltan, avisa por pantalla y termina sin error (el aviso nunca hace fallar al script).

Uso, desde psets/pset-03/pipeline/ (solo biblioteca estandar, sirve python3 del sistema):
  python3 scripts/notificar.py Success reconstruir_obt "transformar 2RSq...: SUCCESS"
  python3 scripts/notificar.py Fail reconstruir_obt "paso 3/5: transformar FAILED"
Para pruebas: AVISO_SMTP_HOST, AVISO_SMTP_PUERTO y AVISO_SMTP_SSL=0 cambian el servidor.
"""
from __future__ import annotations

import os
import smtplib
import socket
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def leer_env(ruta: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            if "=" in linea and not linea.lstrip().startswith("#"):
                clave, _, valor = linea.partition("=")
                valores[clave.strip()] = valor.strip()
    return valores


def mensaje(estado: str, tarea: str, detalle: str, correo: str) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = f"{estado}: {tarea}"
    m["From"] = correo
    m["To"] = correo
    m.set_content(f"{estado}: {tarea}\n\n{detalle}\n\nEquipo: {socket.gethostname()}\n"
                  f"Hora: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
                  f"Carpeta: {RAIZ}\n")
    return m


def enviar(estado: str, tarea: str, detalle: str) -> bool:
    env = {**leer_env(RAIZ / ".env"), **os.environ}
    correo, clave = env.get("AVISO_CORREO", ""), env.get("AVISO_CLAVE_APP", "")
    if not correo or not clave:
        print("Aviso no enviado: faltan AVISO_CORREO o AVISO_CLAVE_APP en .env", file=sys.stderr)
        return False
    host = env.get("AVISO_SMTP_HOST", "smtp.gmail.com")
    puerto = int(env.get("AVISO_SMTP_PUERTO", "465"))
    con_ssl = env.get("AVISO_SMTP_SSL", "1") != "0"
    try:
        smtp = smtplib.SMTP_SSL(host, puerto, timeout=30) if con_ssl else smtplib.SMTP(host, puerto, timeout=30)
        with smtp:
            if con_ssl:
                smtp.login(correo, clave)
            smtp.send_message(mensaje(estado, tarea, detalle, correo))
    except (OSError, smtplib.SMTPException) as e:
        print(f"Aviso no enviado: {e}", file=sys.stderr)
        return False
    print(f"Aviso enviado: {estado}: {tarea}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("Success", "Fail"):
        sys.exit(__doc__)
    enviar(sys.argv[1], sys.argv[2], " ".join(sys.argv[3:]))
