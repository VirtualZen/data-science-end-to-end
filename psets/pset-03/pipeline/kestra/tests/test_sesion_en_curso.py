"""La ingesta no guarda la sesion de hoy mientras la bolsa siga abierta (H15).

Uso, desde psets/pset-03/pipeline/:   uv run python -m pytest -q kestra/tests
"""
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from extraer_cargar import quitar_sesion_en_curso, ultima_sesion_cerrada  # noqa: E402

# 17-nov-2026 en Nueva York es EST (UTC-5): 16:30 NY = 21:30 UTC.
ANTES_DEL_CIERRE = datetime(2026, 11, 17, 17, 34, tzinfo=timezone.utc)   # 12:34 NY (ejecucion 6ZVfwqea)
DESPUES_DEL_CIERRE = datetime(2026, 11, 17, 23, 30, tzinfo=timezone.utc)  # 18:30 NY (trigger)
MADRUGADA_UTC = datetime(2026, 11, 18, 2, 0, tzinfo=timezone.utc)         # 21:00 NY del 17


class SesionEnCurso(unittest.TestCase):
    def test_ultima_sesion_cerrada(self):
        self.assertEqual(ultima_sesion_cerrada(ANTES_DEL_CIERRE), date(2026, 11, 16))
        self.assertEqual(ultima_sesion_cerrada(DESPUES_DEL_CIERRE), date(2026, 11, 17))
        # En UTC ya es el 18, pero en Nueva York sigue siendo el 17 despues del cierre.
        self.assertEqual(ultima_sesion_cerrada(MADRUGADA_UTC), date(2026, 11, 17))

    def test_hora_sin_zona_se_toma_como_utc(self):
        self.assertEqual(ultima_sesion_cerrada(ANTES_DEL_CIERRE.replace(tzinfo=None)), date(2026, 11, 16))

    def test_quita_solo_la_fila_de_hoy_antes_del_cierre(self):
        precios = pd.DataFrame({"TICKER": ["AAA"] * 3,
                                "FECHA": [date(2026, 11, 13), date(2026, 11, 16), date(2026, 11, 17)],
                                "CLOSE": [10.0, 11.0, 12.0]})
        quedan, quitadas = quitar_sesion_en_curso(precios, ANTES_DEL_CIERRE)
        self.assertEqual(quitadas, 1)
        self.assertEqual(list(quedan["FECHA"]), [date(2026, 11, 13), date(2026, 11, 16)])
        quedan, quitadas = quitar_sesion_en_curso(precios, DESPUES_DEL_CIERRE)
        self.assertEqual(quitadas, 0)
        self.assertEqual(len(quedan), 3)

    def test_vacio(self):
        quedan, quitadas = quitar_sesion_en_curso(pd.DataFrame(), ANTES_DEL_CIERRE)
        self.assertTrue(quedan.empty)
        self.assertEqual(quitadas, 0)


if __name__ == "__main__":
    unittest.main()
