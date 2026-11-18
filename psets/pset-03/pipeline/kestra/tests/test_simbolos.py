import sys, unittest
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from extraer_cargar import normalizar, a_simbolo_yahoo, universo
class Simbolos(unittest.TestCase):
    def test_formatos_equivalentes(self):
        self.assertEqual({normalizar(x) for x in [' brk.b ','BRK/B','BRK-B']},{'BRK-B'})
    def test_equivalencia_respeta_fecha(self):
        eq=pd.DataFrame([{'ticker_antiguo':'OLD','ticker_yahoo':'NEW','valido_hasta':date(2020,1,1)}])
        self.assertEqual(a_simbolo_yahoo('OLD',date(2019,12,31),eq),'NEW')
        self.assertEqual(a_simbolo_yahoo('OLD',date(2020,1,1),eq),'OLD')
    def test_historico_incluye_miembro_que_sale(self):
        from unittest.mock import patch
        comp=pd.DataFrame({'FECHA':[date(2019,12,1),date(2020,2,1)],'TICKERS':['AAA,BBB','BBB,CCC']})
        with patch('extraer_cargar.leer_equivalencias',return_value=pd.DataFrame(columns=['ticker_antiguo','ticker_yahoo','valido_hasta'])):
            self.assertTrue({'AAA','BBB','CCC'}.issubset(universo(comp,date(2020,1,1),date(2020,3,1),'historico')))
if __name__=='__main__': unittest.main()
