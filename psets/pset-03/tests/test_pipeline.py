import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from sklearn.dummy import DummyRegressor
from src.pipeline import dividir, pliegues, crear_pipeline, interpolar_huecos, derivar, FEATURES, FEATURES_LINEALES, NUMERICAS, CATEGORICAS
import numpy as np
class Temporal(unittest.TestCase):
    def test_objetivo_cruza_corte(self):
        d=pd.DataFrame({'mes_objetivo':pd.PeriodIndex(['2023-12','2024-01'],freq='M')})
        a,b=dividir(d); self.assertEqual(len(a),1); self.assertEqual(len(b),1)
    def test_meses_no_se_mezclan(self):
        meses=pd.period_range('2010-01',periods=40,freq='M')
        d=pd.DataFrame({'anio_mes':[int(m.strftime('%Y%m')) for m in meses for _ in range(3)]})
        for tr,va in pliegues(d,n_splits=3,meses_validacion=6):
            self.assertLess(d.iloc[tr].anio_mes.max(),d.iloc[va].anio_mes.min())
            self.assertFalse(set(d.iloc[tr].anio_mes)&set(d.iloc[va].anio_mes))
    def test_imputador_no_ve_prueba(self):
        X=pd.DataFrame({c:[1.,2.,None] for c in NUMERICAS}).assign(mes_calendario_obj=[1,5,12]); p=crear_pipeline(DummyRegressor()); p.fit(X,[0,1,0])
        med=p.named_steps['preparar'].named_transformers_['numericas'].named_steps['imputar'].statistics_.copy()
        p.predict(pd.DataFrame({c:[1e9,None] for c in NUMERICAS}).assign(mes_calendario_obj=[3,4]))
        self.assertTrue((med==1.5).all())
        self.assertTrue((med==p.named_steps['preparar'].named_transformers_['numericas'].named_steps['imputar'].statistics_).all())
    def test_interpola_solo_huecos_intermedios(self):
        d=pd.DataFrame({'accion_key':[1]*5+[2]*2,'anio_mes':[201001,201002,201003,201004,201005,201001,201002],
                        'vol_21d':[np.nan,1.,np.nan,3.,np.nan,5.,np.nan]})
        r=interpolar_huecos(d,['vol_21d']).set_index(['accion_key','anio_mes']).vol_21d
        self.assertEqual(r[(1,201003)],2.)
        self.assertTrue(np.isnan(r[(1,201001)]) and np.isnan(r[(1,201005)]) and np.isnan(r[(2,201002)]))
    def test_interpolacion_no_cruza_el_corte(self):
        d=pd.DataFrame({'accion_key':[1]*3,'anio_mes':[202310,202311,202312],'vol_21d':[1.,np.nan,3.],
                        'mes_objetivo':pd.PeriodIndex(['2023-11','2023-12','2024-01'],freq='M')})
        a,b=dividir(d)
        self.assertTrue(np.isnan(a.set_index('anio_mes').vol_21d[202311]))
    def test_dispersion_solo_usa_el_mes(self):
        d=pd.DataFrame({'anio_mes':[202001]*3+[202002]*2,'ret_log_mes':[0.,.1,.2,5.,7.]})
        r=derivar(d)
        self.assertAlmostEqual(r.dispersion_mes.iloc[0],0.1)
        self.assertAlmostEqual(r.dispersion_mes.iloc[3],np.std([5.,7.],ddof=1))
    def test_mes_calendario_del_objetivo(self):
        r=derivar(pd.DataFrame({'anio_mes':[202012,202101],'ret_log_mes':[0.,0.]}))
        self.assertEqual(list(r.mes_calendario_obj),[1,2])
    def test_one_hot_fijo_enero_referencia_y_desconocido_falla(self):
        from src.pipeline import preparacion
        X=pd.DataFrame({c:[0.,1.] for c in NUMERICAS}).assign(mes_calendario_obj=[1,2])
        ct=preparacion().fit(X); Z=pd.DataFrame(ct.transform(X),columns=ct.get_feature_names_out())
        self.assertEqual(Z.shape[1],len(NUMERICAS)+11)
        self.assertEqual(Z.filter(like='mes_calendario').iloc[0].sum(),0)   # enero = todo 0
        with self.assertRaises(ValueError):
            ct.transform(X.assign(mes_calendario_obj=[13,1]))
    def test_pliegues_son_timeseriessplit_de_7_anios(self):
        meses=pd.period_range('2010-11','2023-12',freq='M')
        d=pd.DataFrame({'mes_objetivo':[m for m in meses for _ in range(2)]})
        cv=pliegues(d); self.assertEqual(len(cv),7)
        mo=d.mes_objetivo
        for k,(it,iv) in enumerate(cv):
            self.assertEqual(str(mo.iloc[iv].min()),f'{2017+k}-01'); self.assertEqual(str(mo.iloc[iv].max()),f'{2017+k}-12')
            self.assertEqual(mo.iloc[it].max(),mo.iloc[iv].min()-2)          # gap de 1 mes
            self.assertEqual(str(mo.iloc[it].min()),'2010-11')               # ventana expansiva
    def test_lineales_sin_redundantes(self):
        self.assertEqual(len(FEATURES)-len(FEATURES_LINEALES),4)
        self.assertEqual(len(FEATURES),35); self.assertEqual(CATEGORICAS,['mes_calendario_obj'])
    def test_validar_devuelve_metricas_usuales(self):
        from src.pipeline import validar, metricas_regresion, PUNTAJES
        from sklearn.linear_model import Ridge
        rng=np.random.default_rng(0); meses=pd.period_range('2010-11','2023-12',freq='M')
        d=pd.DataFrame({'mes_objetivo':[m for m in meses for _ in range(5)]})
        for c in NUMERICAS: d[c]=rng.normal(size=len(d))
        d['mes_calendario_obj']=d.mes_objetivo.dt.month; d['ret_log_mes_siguiente']=rng.normal(size=len(d))
        r=validar(Ridge(),d)
        for m in PUNTAJES: self.assertIn(f'{m}_cv_media',r)
        self.assertGreater(r['mae_cv_media'],0); self.assertGreater(r['max_error_cv_media'],r['mae_cv_media'])
        h=metricas_regresion([0.1,-0.2,0.3],[0.05,-0.1,-0.1])
        self.assertAlmostEqual(h['acierto_direccional'],2/3); self.assertEqual(set(h),set(PUNTAJES))
if __name__=='__main__': unittest.main()
