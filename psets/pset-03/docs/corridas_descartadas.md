# Corridas descartadas del experimento `portafolio-inversiones`

Ninguna corrida se borró ni se archivó. Las que no sirven como evidencia quedan en MLflow con el tag
`fase = descartada` y un tag `motivo`, y siguen en `docs/corridas.csv`. Para verlas en la interfaz:
`tags.fase = 'descartada'`. Para excluirlas de cualquier comparación: `tags.fase != 'descartada'`.

| Corrida | Modelo | Motivo | Reemplazo válido |
|---|---|---|---|
| `11ba2e86…` | M9_timesfm | Prueba de TimesFM con 500 filas (ver abajo) | `eff5db04…` |
| `636a13c6…` | M3_lightgbm | Corrida de prueba de la sección 4, con el pipeline previo a la versión final | `c106ba8c…` (candidato) |
| Copias más recientes de B1, B2 y B5 | B1_media, B2_rw_cero, referencia B5 | Registros duplicados, con las mismas métricas que la corrida original | La corrida más antigua de cada una |
| `c83f2159…`, `bfc6c247…` y 21 hijas | M3b_xgboost (tuning) | Tuning fallido (`FAILED`): dos procesos en paralelo escribían el mismo archivo temporal | Corrida padre `2dbac622…` con sus 30 hijas |

## La corrida inválida de TimesFM (`11ba2e86…`)

**Qué pasó**
1. Para medir la latencia, TimesFM se corrió primero como prueba con `--limite 500`, solo sobre 500 series. Esa prueba
   dejó `artefactos/fundacional_timesfm.parquet` con 500 pronósticos.
2. Al ejecutar `notebooks/03_baseline_candidatos.ipynb`, la celda de la sección 6.3 registra en MLflow todo
   fundacional cuyo parquet existe. Encontró el de la prueba y registró M9_timesfm con él (corrida `11ba2e86…`).
3. `registrar_fundacional` calcula las métricas solo sobre las filas que tienen pronóstico. Con una **cobertura de
   0,94 %** de las filas de validación, el MAE (0,0641) salió igual al de B1 y parecía el mejor fundacional, pero no
   era comparable con los demás modelos.

**Cómo se detectó.** La tabla de candidatos mostraba `cobertura = 0,0094` y 500 filas en el `.json` del artefacto,
frente a 58.627 de Chronos y Moirai.

**Cómo se corrigió**
1. TimesFM se volvió a correr completo, limitado a los meses de validación por su latencia (unos 110 ms por serie):
   `--desde 201612 --hasta 202311`. Resultado: 26.750 pronósticos en 2.883 s, sha256 `343ad46d…`
   (`artefactos/fundacional_timesfm.json`).
2. Se registró de nuevo con `python -m src.experimentos --modelos M9_timesfm`: corrida **`eff5db04…`**, MAE CV 0,0687,
   IC −0,011 y Sharpe neto 0,457. Esa corrida reemplaza a la anterior en `docs/candidatos.csv`.
3. La corrida `11ba2e86…` quedó con `fase = descartada` y su `motivo`.
4. `03_baseline_candidatos` se volvió a ejecutar con `REGISTRAR = False`: lee `docs/candidatos.csv` y su salida
   guardada ya muestra la corrida válida.

**Efecto en los resultados.** Ninguno en la selección: TimesFM no es ajustable (zero-shot), no entra al tuning y
su MAE válido (0,0687) no queda entre los finalistas. `05_seleccion` se ejecutó después del reemplazo y lee
`docs/candidatos.csv`, donde ya estaba la corrida válida.

**Prevención (pendiente para el PSet 4).** Que `registrar_fundacional` rechace un artefacto con cobertura menor al
95 % de las filas de validación, y que las pruebas con `--limite` escriban en un archivo distinto
(`fundacional_<modelo>_prueba.parquet`).
