"""API de service du modèle NER OSINT (étape 6 — déploiement).

Expose le modèle fine-tuné derrière une API REST :
  GET  /health          état du service et du modèle (sonde de disponibilité)
  GET  /metrics         métriques de monitoring (volumétrie, latence, entités par label)
  POST /extract         extrait WEAPON / MIL_UNIT / MIL_ORG d'un texte
  POST /extract/batch   même chose pour une liste de textes (max 100)

Lancement local :
    MODEL_PATH=output/model-best uvicorn src.api:app --port 8000
Documentation interactive : http://localhost:8000/docs
"""

import logging
import os
import time
from collections import Counter
from pathlib import Path

import spacy
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "output" / "model-best"))
LABELS = {"WEAPON": "weapons", "MIL_UNIT": "mil_units", "MIL_ORG": "mil_orgs"}
MAX_CHARS = 4000  # même borne que l'inférence batch (step4_infer.py)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("osint-ner-api")

app = FastAPI(
    title="OSINT-NER API",
    version="1.0.0",
    description="Extraction d'entités militaires (WEAPON, MIL_UNIT, MIL_ORG) par un modèle spaCy fine-tuné.",
)

_state = {"nlp": None, "loaded_at": None, "error": None}
_stats = {"requests": 0, "errors": 0, "texts": 0, "latency_ms_total": 0.0, "by_label": Counter()}


def get_nlp():
    """Charge le modèle une seule fois (paresseusement)."""
    if _state["nlp"] is None:
        try:
            _state["nlp"] = spacy.load(MODEL_PATH)
            _state["loaded_at"] = time.time()
            log.info("Modèle chargé depuis %s", MODEL_PATH)
        except OSError as exc:
            _state["error"] = str(exc)
            log.error("Échec du chargement du modèle : %s", exc)
            raise HTTPException(status_code=503, detail=f"Modèle indisponible : {MODEL_PATH}") from exc
    return _state["nlp"]


class TextIn(BaseModel):
    text: str = Field(..., min_length=1, examples=["The Defense Ministry said HIMARS launchers were destroyed."])


class BatchIn(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=100)


class Entity(BaseModel):
    text: str
    label: str
    start: int
    end: int


class ExtractOut(BaseModel):
    entities: list[Entity]
    weapons: list[str]
    mil_units: list[str]
    mil_orgs: list[str]
    n_entities: int


def _to_out(doc) -> ExtractOut:
    grouped = {field: [] for field in LABELS.values()}
    ents = []
    for ent in doc.ents:
        field = LABELS.get(ent.label_)
        if field is None:
            continue  # on ignore les labels génériques hérités d'en_core_web_sm
        ents.append(Entity(text=ent.text, label=ent.label_, start=ent.start_char, end=ent.end_char))
        grouped[field].append(ent.text.lower())
        _stats["by_label"][ent.label_] += 1
    return ExtractOut(entities=ents, n_entities=len(ents), **grouped)


def _timed(texts):
    t0 = time.perf_counter()
    _stats["requests"] += 1
    try:
        nlp = get_nlp()
        outs = [_to_out(d) for d in nlp.pipe([t[:MAX_CHARS] for t in texts])]
    except Exception:
        _stats["errors"] += 1
        raise
    ms = (time.perf_counter() - t0) * 1000
    _stats["texts"] += len(texts)
    _stats["latency_ms_total"] += ms
    log.info("extract n_texts=%d n_entities=%d latency_ms=%.1f", len(texts), sum(o.n_entities for o in outs), ms)
    return outs


@app.get("/health")
def health():
    ok = True
    try:
        get_nlp()
    except HTTPException:
        ok = False
    return {"status": "ok" if ok else "degraded", "model_path": str(MODEL_PATH), "model_loaded": ok}


@app.get("/metrics")
def metrics():
    n = _stats["requests"]
    return {
        "requests_total": n,
        "errors_total": _stats["errors"],
        "texts_total": _stats["texts"],
        "latency_ms_avg": round(_stats["latency_ms_total"] / n, 2) if n else 0.0,
        "entities_by_label": dict(_stats["by_label"]),
        "model_loaded_since_s": round(time.time() - _state["loaded_at"], 1) if _state["loaded_at"] else None,
    }


@app.post("/extract", response_model=ExtractOut)
def extract(body: TextIn):
    return _timed([body.text])[0]


@app.post("/extract/batch", response_model=list[ExtractOut])
def extract_batch(body: BatchIn):
    return _timed(body.texts)
