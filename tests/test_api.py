"""Tests de l'API.

Le vrai modèle (output/model-best) n'est pas versionné : la CI construit un
mini-modèle à règles qui produit les mêmes labels, pour tester le contrat de l'API.
"""

import importlib
import sys
from pathlib import Path

import pytest
import spacy
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    model_dir = tmp_path_factory.mktemp("model")
    nlp = spacy.blank("en")
    ruler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns([
        {"label": "WEAPON", "pattern": "HIMARS"},
        {"label": "MIL_ORG", "pattern": [{"LOWER": "defense"}, {"LOWER": "ministry"}]},
        {"label": "MIL_UNIT", "pattern": [{"LOWER": "marine"}, {"LOWER": "brigade"}]},
        {"label": "GPE", "pattern": "Russia"},
    ])
    nlp.to_disk(model_dir)
    import os
    os.environ["MODEL_PATH"] = str(model_dir)
    import src.api as api
    importlib.reload(api)
    return TestClient(api.app)


TEXT = "Russia's Defense Ministry said a marine brigade destroyed two HIMARS launchers."


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_extract_groups_entities(client):
    r = client.post("/extract", json={"text": TEXT})
    assert r.status_code == 200
    body = r.json()
    assert body["weapons"] == ["himars"]
    assert body["mil_orgs"] == ["defense ministry"]
    assert body["mil_units"] == ["marine brigade"]
    assert body["n_entities"] == 3  # GPE ignoré : seuls les 3 labels métier sont exposés


def test_offsets_point_to_text(client):
    ent = client.post("/extract", json={"text": TEXT}).json()["entities"][0]
    assert TEXT[ent["start"]:ent["end"]] == ent["text"]


def test_batch(client):
    r = client.post("/extract/batch", json={"texts": [TEXT, "Nothing military here."]})
    assert r.status_code == 200
    assert [o["n_entities"] for o in r.json()] == [3, 0]


def test_validation_errors(client):
    assert client.post("/extract", json={"text": ""}).status_code == 422
    assert client.post("/extract/batch", json={"texts": []}).status_code == 422


def test_metrics_track_traffic(client):
    m = client.get("/metrics").json()
    assert m["requests_total"] >= 3
    assert m["entities_by_label"]["WEAPON"] >= 1
    assert m["latency_ms_avg"] > 0
