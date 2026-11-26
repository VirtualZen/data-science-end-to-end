"""Primera carga sin intervencion manual (H12): con RAW vacia, el modo diario hace el historico.

Uso, desde psets/pset-03/pipeline/:   uv run python -m pytest -q kestra/tests
"""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import extraer_cargar as ec  # noqa: E402


class PrimeraCarga(unittest.TestCase):
    def test_tramos_por_anio_hasta_la_fecha(self):
        tramos = ec.tramos_historico(date(2026, 11, 17))
        self.assertEqual(len(tramos), 2026 - ec.ANIO_INICIO + 1)
        self.assertEqual(tramos[0], (date(ec.ANIO_INICIO, 1, 1), date(ec.ANIO_INICIO, 12, 31)))
        self.assertEqual(tramos[-1], (date(2026, 1, 1), date(2026, 11, 17)))

    def test_raw_vacia_hace_historico(self):
        with patch.object(ec, "raw_precios_vacia", return_value=True), patch.object(ec, "correr") as correr:
            ec.correr_diario(date(2026, 11, 17), False)
        modos = {c.args[0] for c in correr.call_args_list}
        self.assertEqual(modos, {"historico"})
        self.assertEqual(correr.call_count, 2026 - ec.ANIO_INICIO + 1)
        self.assertTrue(all(c.kwargs["incluir_referencias"] for c in correr.call_args_list))

    def test_raw_con_datos_hace_ventana_diaria(self):
        with patch.object(ec, "raw_precios_vacia", return_value=False), patch.object(ec, "correr") as correr:
            ec.correr_diario(date(2026, 11, 17), False)   # martes: sin referencias
        correr.assert_called_once_with("diario", date(2026, 11, 6), date(2026, 11, 17), False)

    def test_lunes_recarga_referencias(self):
        with patch.object(ec, "raw_precios_vacia", return_value=False), patch.object(ec, "correr") as correr:
            ec.correr_diario(date(2026, 11, 16), False)   # lunes
        self.assertTrue(correr.call_args.args[3])


if __name__ == "__main__":
    unittest.main()
