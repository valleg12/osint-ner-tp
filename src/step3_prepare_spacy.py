"""Étape 3a/3b — Préparer l'entraînement spaCy.

  - Split train / dev (80 / 20) pour évaluer honnêtement (slide étape 3a).
  - Conversion des annotations en fichiers binaires .spacy via DocBin.
  - Génération de configs/config.cfg partant de en_core_web_sm (transfer learning,
    slide étape 3b : [components.ner] source = "en_core_web_sm").

L'entraînement lui-même (étape 3c) se lance ensuite avec :
    python -m spacy train configs/config.cfg \
        --output ./output --paths.train data/processed/train.spacy \
        --paths.dev data/processed/dev.spacy

Usage :
    python step3_prepare_spacy.py
"""

import json
import random

import spacy
from spacy.tokens import DocBin

from config import (
    ANNOTATIONS,
    BASE_MODEL,
    CONFIGS,
    DEV_SPACY,
    LABELS,
    TRAIN_SPACY,
)

SEED = 42
TRAIN_RATIO = 0.8


def to_docbin(nlp, dataset) -> tuple[DocBin, int, int]:
    """Construit un DocBin ; ignore les entités mal alignées sur les tokens."""
    db = DocBin()
    kept = dropped = 0
    for text, ann in dataset:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in ann["entities"]:
            span = doc.char_span(start, end, label=label, alignment_mode="contract")
            if span is None:
                dropped += 1
                continue
            ents.append(span)
            kept += 1
        # filtre_spans : retire les chevauchements résiduels
        doc.ents = spacy.util.filter_spans(ents)
        db.add(doc)
    return db, kept, dropped


def patch_config() -> None:
    """Génère config.cfg (NER) puis active le transfer learning depuis en_core_web_sm."""
    from spacy.cli.init_config import init_config
    from thinc.api import Config

    CONFIGS.mkdir(parents=True, exist_ok=True)
    cfg_path = CONFIGS / "config.cfg"

    # Équivalent de : spacy init config --lang en --pipeline ner
    config = init_config(lang="en", pipeline=["ner"], optimize="efficiency", gpu=False)

    # Transfer learning : on part du NER pré-entraîné plutôt que d'un NER vierge.
    config["components"]["ner"] = {"source": BASE_MODEL}
    # Chemins par défaut (surchargés par les flags --paths.* si besoin).
    config["paths"]["train"] = str(TRAIN_SPACY)
    config["paths"]["dev"] = str(DEV_SPACY)

    Config(config).to_disk(cfg_path)
    print(f"Config écrite : {cfg_path} (source = {BASE_MODEL})")


def main() -> None:
    with open(ANNOTATIONS, encoding="utf-8") as f:
        dataset = json.load(f)

    random.Random(SEED).shuffle(dataset)
    cut = int(len(dataset) * TRAIN_RATIO)
    train, dev = dataset[:cut], dataset[cut:]

    nlp = spacy.blank("en")
    train_db, tk, td = to_docbin(nlp, train)
    dev_db, dk, dd = to_docbin(nlp, dev)

    TRAIN_SPACY.parent.mkdir(parents=True, exist_ok=True)
    train_db.to_disk(TRAIN_SPACY)
    dev_db.to_disk(DEV_SPACY)

    print(f"Labels          : {', '.join(LABELS)}")
    print(f"Train           : {len(train)} docs, {tk} entités (ignorées : {td})")
    print(f"Dev             : {len(dev)} docs, {dk} entités (ignorées : {dd})")
    print(f"Fichiers .spacy : {TRAIN_SPACY} / {DEV_SPACY}")
    patch_config()


if __name__ == "__main__":
    main()
