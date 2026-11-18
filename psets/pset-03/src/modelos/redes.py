"""M7: red hibrida ARIMA-GARCH + LSTM en PyTorch Lightning (grupo uv "redes").

Entrada por fila (accion, mes t):
  secuencia  ultimos L dias hasta el cierre de t de OBT_ACCION_DIA: ret_log_diario,
             ret_log_intradia, ret_log_nocturno, rango_log_hl y los residuos estandarizados
             del GARCH filtrado con parametros de Y-1 (src/modelos/series.py)
  estaticas  coeficientes ARIMA-GARCH del anio, varianza condicional y pronosticos (mismo modulo)
             mas las variables de OBT_ACCION_MES ya en rango transversal
Salida: retorno log del mes siguiente (perdida Huber: colas gruesas) o su rango transversal.

La normalizacion (media y desviacion por canal) se calcula SOLO con la ventana de
entrenamiento y se guarda con el modelo. Early stopping con los ultimos 12 meses de la
ventana de entrenamiento (no con la validacion de la ventana walk-forward).

Dispositivo: entorno.dispositivo() -> cuda en Colab, mps en la Mac M4, cpu en otro caso.
En mps se usa float32 (mps no soporta float64).
"""
from __future__ import annotations

import numpy as np

from ..entorno import SEMILLA, dispositivo


def _torch():
    try:
        import torch
        import lightning as L
    except ImportError as e:
        raise ImportError("Instala el grupo de redes: uv sync --group redes") from e
    return torch, L


def construir_modulo(canales: int, estaticas: int, oculto: int = 32, capas: int = 1,
                     abandono: float = 0.2, tasa: float = 1e-3, peso_l2: float = 1e-4, delta_huber: float = 0.05):
    torch, L = _torch()
    nn = torch.nn

    class LstmHibrida(L.LightningModule):
        def __init__(self):
            super().__init__()
            self.save_hyperparameters({"canales": canales, "estaticas": estaticas, "oculto": oculto,
                                       "capas": capas, "abandono": abandono, "tasa": tasa,
                                       "peso_l2": peso_l2, "delta_huber": delta_huber})
            self.lstm = nn.LSTM(canales, oculto, num_layers=capas, batch_first=True,
                                dropout=abandono if capas > 1 else 0.0)
            self.cabeza = nn.Sequential(nn.Linear(oculto + estaticas, oculto), nn.ReLU(),
                                        nn.Dropout(abandono), nn.Linear(oculto, 1))
            self.perdida = nn.HuberLoss(delta=delta_huber)

        def forward(self, secuencia, est):
            _, (h, _) = self.lstm(secuencia)
            return self.cabeza(torch.cat([h[-1], est], dim=1)).squeeze(1)

        def _paso(self, lote, etapa):
            sec, est, y = lote
            loss = self.perdida(self(sec, est), y)
            self.log(f"{etapa}_perdida", loss, prog_bar=True, on_epoch=True, on_step=False)
            return loss

        def training_step(self, lote, _):
            return self._paso(lote, "entrenamiento")

        def validation_step(self, lote, _):
            return self._paso(lote, "validacion")

        def configure_optimizers(self):
            return torch.optim.AdamW(self.parameters(), lr=tasa, weight_decay=peso_l2)

    return LstmHibrida()


def entrenar(sec_ent, est_ent, y_ent, sec_val, est_val, y_val, epocas: int = 30, lote: int = 1024,
             paciencia: int = 5, ruta_pesos=None, **hiper):
    """Devuelve (modelo, historia). historia = perdidas por epoca para las curvas de aprendizaje."""
    torch, L = _torch()
    from lightning.pytorch.callbacks import Callback, EarlyStopping
    L.seed_everything(SEMILLA, workers=True)
    t = lambda a: torch.as_tensor(np.asarray(a, dtype=np.float32))
    dl = lambda s, e, y, mezclar: torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(t(s), t(e), t(y)), batch_size=lote, shuffle=mezclar, num_workers=0)
    historia = []

    class Historia(Callback):
        def on_validation_epoch_end(self, trainer, pl_module):
            m = trainer.callback_metrics
            if "entrenamiento_perdida" in m:
                historia.append({"epoca": trainer.current_epoch,
                                 "entrenamiento": float(m["entrenamiento_perdida"]),
                                 "validacion": float(m["validacion_perdida"])})

    modelo = construir_modulo(sec_ent.shape[2], est_ent.shape[1], **hiper)
    acel = {"cuda": "gpu", "mps": "mps"}.get(dispositivo(), "cpu")
    trainer = L.Trainer(max_epochs=epocas, accelerator=acel, devices=1, deterministic=acel != "mps",
                        callbacks=[EarlyStopping("validacion_perdida", patience=paciencia), Historia()],
                        enable_checkpointing=False, logger=False, enable_progress_bar=False)
    trainer.fit(modelo, dl(sec_ent, est_ent, y_ent, True), dl(sec_val, est_val, y_val, False))
    if ruta_pesos is not None:
        torch.save(modelo.state_dict(), ruta_pesos)
    return modelo, historia


def predecir(modelo, sec, est, lote: int = 4096) -> np.ndarray:
    torch, _ = _torch()
    modelo.eval()
    disp = next(modelo.parameters()).device
    out = []
    with torch.no_grad():
        for i in range(0, len(sec), lote):
            s = torch.as_tensor(np.asarray(sec[i:i + lote], dtype=np.float32), device=disp)
            e = torch.as_tensor(np.asarray(est[i:i + lote], dtype=np.float32), device=disp)
            out.append(modelo(s, e).cpu().numpy())
    return np.concatenate(out) if out else np.empty(0)
