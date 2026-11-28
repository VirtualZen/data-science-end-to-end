"""Configuracion del despliegue: flows de Kestra, plantilla de variables, versiones fijadas y rollback.

Solo leen archivos del repositorio (pipeline/kestra/flows/, docker-compose.yml, .env.example,
requirements.txt y tests/fixtures/); no usan Kestra, MLflow ni Snowflake. Cada prueba atrapa un error
que ya ocurrio al levantar el proyecto (27-nov): flows rechazados por Kestra 2.0 con 422 (BOOLEAN, ForEach)
y el compose detenido por API_TOKEN ausente en la plantilla."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
FLOWS = sorted((RAIZ / "pipeline" / "kestra" / "flows").glob("*.yml"))

# Tipos de input y output que acepta Kestra 2.0 (BOOLEAN ya no existe: es BOOL).
TIPOS_KESTRA = {"STRING", "ENUM", "SELECT", "MULTISELECT", "INT", "FLOAT", "BOOL", "DATETIME", "DATE", "TIME",
                "DURATION", "FILE", "JSON", "URI", "SECRET", "ARRAY", "YAML", "EMAIL"}
# Tareas retiradas en Kestra 2.0 (ForEach se reemplaza por Loop).
TAREAS_RETIRADAS = {"io.kestra.plugin.core.flow.ForEach", "io.kestra.plugin.core.flow.EachSequential",
                    "io.kestra.plugin.core.flow.EachParallel", "io.kestra.core.tasks.flows.EachSequential"}
CRITICOS = ("scikit-learn", "mlflow", "lightgbm", "numpy", "pandas", "scipy", "skops", "fastapi", "pydantic")


def _flows() -> dict[str, dict]:
    return {f.stem: yaml.safe_load(f.read_text()) for f in FLOWS}


def _recorrer(nodo, ruta=""):
    """Todos los dicts del YAML con su ruta, para revisar tipos y tareas a cualquier profundidad."""
    if isinstance(nodo, dict):
        yield ruta, nodo
        for k, v in nodo.items():
            yield from _recorrer(v, f"{ruta}.{k}")
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from _recorrer(v, f"{ruta}[{i}]")


def test_flows_de_kestra_validos_para_la_version_2():
    """Tipos de inputs y outputs validos, sin tareas retiradas, ids unicos y subflows que existen."""
    flows = _flows()
    assert {"produccion_lotes", "monitoreo", "reentrenamiento"} <= set(flows)
    existentes = {(f["namespace"], f["id"]) for f in flows.values()}
    for nombre, flow in flows.items():
        assert flow["id"] == nombre, f"{nombre}.yml declara id {flow['id']}"
        ids = []
        for ruta, d in _recorrer(flow):
            tipo = d.get("type")
            if re.search(r"\.(inputs|outputs|onResume)\[\d+\]$", ruta):
                assert tipo in TIPOS_KESTRA, f"{nombre}{ruta}: tipo {tipo!r} no existe en Kestra 2.0"
            if isinstance(tipo, str) and tipo.startswith("io.kestra"):
                assert tipo not in TAREAS_RETIRADAS, f"{nombre}{ruta}: {tipo} se retiro en Kestra 2.0"
                if re.search(r"\.(tasks|then|else|errors|finally)\[\d+\]$", ruta):
                    assert "id" in d, f"{nombre}{ruta}: tarea sin id"
                    ids.append(d["id"])
                if tipo.endswith("core.flow.Subflow"):
                    assert (d["namespace"], d["flowId"]) in existentes, f"{nombre}{ruta}: subflow inexistente"
        assert len(ids) == len(set(ids)), f"{nombre}: ids de tarea repetidos"


def test_la_plantilla_de_variables_cubre_el_compose():
    """Toda variable obligatoria del compose (${VAR:?...}) esta en .env.example y en pipeline/.env.example,
    y la plantilla de la raiz no deja fuera ninguna de las de pipeline/ ni de modelos/. Sin valores secretos."""
    compose = (RAIZ / "docker-compose.yml").read_text()
    obligatorias = set(re.findall(r"\$\{([A-Z0-9_]+):\?", compose))
    assert "API_TOKEN" in obligatorias

    def variables(f: Path) -> dict[str, str]:
        return dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", f.read_text(), flags=re.M))

    raiz, pipeline, modelos = (variables(RAIZ / p) for p in
                               (".env.example", "pipeline/.env.example", "modelos/.env.example"))
    assert obligatorias <= set(raiz) and obligatorias <= set(pipeline)
    assert set(pipeline) <= set(raiz) and set(modelos) <= set(raiz)
    for nombre in ("API_TOKEN", "KESTRA_CLAVE", "KESTRA_DB_PASSWORD", "SNOWFLAKE_PRIVATE_KEY", "AVISO_CLAVE_APP"):
        assert raiz[nombre] == "" == pipeline[nombre], f"{nombre} debe ir vacio en la plantilla"


def test_versiones_del_modelo_iguales_en_api_entrenamiento_y_fixture():
    """La imagen de la API (api/requirements.txt), el entorno de entrenamiento y monitoreo
    (modelos/requirements.txt, que incluye el requirements.txt de la raiz) y el modelo guardado en
    tests/fixtures/ fijan las mismas versiones de las librerias que tocan la prediccion."""
    def pines(f: Path) -> dict[str, str]:
        return {n.lower(): v for n, v in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", f.read_text(), flags=re.M)}

    api, modelos = pines(RAIZ / "api" / "requirements.txt"), pines(RAIZ / "modelos" / "requirements.txt")
    fixture = pines(RAIZ / "tests" / "fixtures" / "modelo_champion" / "requirements.txt")
    assert "-r modelos/requirements.txt" in (RAIZ / "requirements.txt").read_text()
    for p in CRITICOS:
        assert api[p] == modelos[p], f"{p}: api {api[p]} vs modelos {modelos[p]}"
        if p in fixture:
            assert fixture[p] == api[p], f"{p}: fixture {fixture[p]} vs api {api[p]}"


def test_rollback_moviendo_la_referencia_sin_reconstruir(cliente, token, monkeypatch, tmp_path):
    """PDF 4: volver a la version anterior cambiando solo la referencia del modelo, y /modelo lo refleja.

    En produccion la API apunta a models:/portafolio-inversiones-modelo@champion y el rollback mueve el
    alias en el registro (docs/reentrenamiento.md). En CI no hay MLflow: se simula con MODELO_URI apuntando
    a dos copias del modelo con distinta version registrada. Mismo proceso, mismo /recargar, sin imagen nueva."""
    original = RAIZ / "tests" / "fixtures" / "modelo_champion"
    nueva = tmp_path / "version_2"
    shutil.copytree(original, nueva)
    mlmodel = nueva / "MLmodel"
    mlmodel.write_text(mlmodel.read_text().replace("version_registrada: '1'", "version_registrada: '2'"))

    monkeypatch.setenv("MODELO_URI", str(nueva))
    assert cliente.post("/recargar", headers=token).status_code == 200
    assert cliente.get("/modelo").json()["version"] == "2"

    monkeypatch.setenv("MODELO_URI", str(original))               # rollback
    assert cliente.post("/recargar", headers=token).status_code == 200
    assert cliente.get("/modelo").json()["version"] == "1"


def test_promover_exige_regla_y_aprobacion():
    """Auditoria H8: el flow de reentrenamiento promueve solo si la regla cuantitativa Y la persona lo aprueban."""
    flujo = yaml.safe_load((RAIZ / "pipeline" / "kestra" / "flows" / "reentrenamiento.yml").read_text())
    condicion = next(t for t in flujo["tasks"] if t["id"] == "si_aprobado")["condition"]
    assert "onResume.aprobado" in condicion and "outputs.entrenar.vars.promueve" in condicion and " and " in condicion


@pytest.mark.parametrize("aprobado,promueve", [(True, True), (True, False), (False, True), (False, False)])
def test_promocion_en_los_cuatro_casos(aprobado, promueve):
    """Segunda revision de Codex (H8): evalua la condicion del flow en los cuatro casos (aprobacion humana x regla).
    Solo el caso si/si entra a la rama que mueve @champion (monitoreo.produccion promover); los otros tres van a la rama
    que solo registra la decision y deja el champion como estaba."""
    flujo = yaml.safe_load((RAIZ / "pipeline" / "kestra" / "flows" / "reentrenamiento.yml").read_text())
    tarea = next(t for t in flujo["tasks"] if t["id"] == "si_aprobado")
    expresion = tarea["condition"].strip().removeprefix("{{").removesuffix("}}").strip()
    variables = {"outputs.aprobacion.onResume.aprobado": aprobado, "outputs.entrenar.vars.promueve": promueve}
    assert set(re.findall(r"[A-Za-z_][\w.]*", expresion)) == set(variables) | {"and"}
    for nombre, valor in variables.items():
        expresion = expresion.replace(nombre, str(valor))
    entra = eval(expresion, {"__builtins__": {}}, {})
    rama = tarea["then"] if entra else tarea["else"]
    mueve_champion = any("monitoreo.produccion promover" in " ".join(t.get("commands", [])) for t in rama)
    assert entra is (aprobado and promueve)
    assert mueve_champion is (aprobado and promueve)
