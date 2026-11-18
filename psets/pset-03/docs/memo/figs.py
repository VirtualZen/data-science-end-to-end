import pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
S=str(Path(__file__).resolve().parents[1])  # docs/
c=pd.read_csv(f'{S}/candidatos.csv')
rows=[(r.modelo,'por defecto',r.mae_cv_media,r.mae_cv_std,r.negocio_sharpe_neto,r.familia) for r in c.itertuples()]
for m in ['M3_lightgbm','M3b_xgboost','M4_ridge']:
    t=pd.read_csv(f'{S}/tuning_{m}.csv').sort_values('mae_cv_media').iloc[0]
    rows.append((m+' (ajustado)','ajustado',t.mae_cv_media,t.mae_cv_std,t.negocio_sharpe_neto,t.familia))
d=pd.DataFrame(rows,columns=['modelo','version','mae','std','sharpe','familia']).sort_values('mae')
col={'linea_base':'#9aa0a6','fundacional':'#7b61ff','boosting':'#e8710a','lineal':'#1a73e8','bagging':'#188038','red_neuronal':'#d93025'}
fig,ax=plt.subplots(1,2,figsize=(11,4.2),sharey=True)
y=range(len(d))
ax[0].barh(y,d.mae,xerr=d['std'],color=[col[f] for f in d.familia],alpha=.85,error_kw=dict(lw=.8,capsize=2,ecolor='#555'))
ax[0].axvline(0.0641,ls='--',c='k',lw=1); ax[0].text(0.0645,-0.9,'B1 0,0641',fontsize=8)
ax[0].set_xlim(0.04,0.115); ax[0].set_ylim(len(d)-.5,-1.4); ax[0].set_title('MAE de CV (media ± desviación, 7 pliegues)',fontsize=10)
ax[0].set_yticks(list(y)); ax[0].set_yticklabels(d.modelo,fontsize=8)
s=d.sharpe.fillna(0)
ax[1].barh(y,s,color=[col[f] for f in d.familia],alpha=.85)
ax[1].axvline(0.5441,ls='--',c='k',lw=1); ax[1].text(0.548,-0.9,'B5 0,544',fontsize=8)
ax[1].set_title('Sharpe neto en CV (top-10, regla 1/vol, 15 pb)',fontsize=10)
for i,v in zip(y,d.sharpe):
    if pd.isna(v): ax[1].text(0.01,i,'sin regla de negocio',va='center',fontsize=7,color='#555')
for a in ax: a.grid(axis='x',alpha=.3); a.tick_params(axis='x',labelsize=8)
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=v,label=k) for k,v in col.items()],fontsize=8,loc='lower center',ncol=6,frameon=False)
plt.tight_layout(rect=(0,0.06,1,1)); plt.savefig(S+'/figuras/resultados_modelos.png',dpi=170)
h=pd.read_csv(f'{S}/holdout_finalistas.csv')
fig,ax=plt.subplots(1,2,figsize=(9,2.8))
lab=['Champion\nLightGBM','Challenger\nRidge','B1 media']; v=[h.mae_holdout[0],h.mae_holdout[1],0.0634]
ax[0].bar(lab,v,color=['#e8710a','#1a73e8','#9aa0a6']); ax[0].set_ylim(0.06,0.069); ax[0].set_title('MAE en hold-out (menor es mejor)',fontsize=10)
for i,x in enumerate(v): ax[0].text(i,x+.0002,f'{x:.4f}',ha='center',fontsize=8)
lab2=['Champion\nLightGBM','Challenger\nRidge','B5 universo','S&P 500']; v2=[h.negocio_sharpe_neto_holdout[0],h.negocio_sharpe_neto_holdout[1],0.6781,1.0990]
ax[1].bar(lab2,v2,color=['#e8710a','#1a73e8','#9aa0a6','#5f6368']); ax[1].axhline(0,c='k',lw=.6); ax[1].set_ylim(-0.2,1.28); ax[1].set_title('Sharpe neto en hold-out (mayor es mejor)',fontsize=10)
for i,x in enumerate(v2): ax[1].text(i,x+.02 if x>=0 else x-.13,f'{x:.2f}',ha='center',fontsize=8)
for a in ax: a.tick_params(labelsize=8)
plt.tight_layout(); plt.savefig(S+'/figuras/holdout.png',dpi=170)
print(d.round(4).to_string())
