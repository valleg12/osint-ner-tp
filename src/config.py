"""Configuration centrale du pipeline OSINT-NER.

Schéma d'annotation (3 labels) — voir slides « Notre schéma : 3 labels » :
  - WEAPON   : systèmes et matériels (missiles, blindés, drones, lance-roquettes)
  - MIL_UNIT : unités combattantes (brigades, bataillons, régiments, divisions)
  - MIL_ORG  : organisations de haut niveau (états-majors, ministères, forces armées)
"""

from pathlib import Path

# --- Arborescence ---
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
CONFIGS = ROOT / "configs"
OUTPUT = ROOT / "output"

# --- Fichiers du pipeline ---
RAW_DATASET = DATA_RAW / "data_set.json"          # corpus source (TASS)
CORPUS = DATA_PROC / "corpus.jsonl"               # étape 1 : texte propre + métadonnées
ANNOTATIONS = DATA_PROC / "annotations.json"      # étape 2 : format spaCy
TRAIN_SPACY = DATA_PROC / "train.spacy"           # étape 3 : DocBin train
DEV_SPACY = DATA_PROC / "dev.spacy"               # étape 3 : DocBin dev
ENRICHED = DATA_PROC / "enriched.jsonl"           # étape 4 : articles + entités
MODEL_BEST = OUTPUT / "model-best"                # étape 3 : meilleur modèle

# --- Schéma NER ---
LABELS = ["WEAPON", "MIL_UNIT", "MIL_ORG"]

# --- Modèle de base (transfer learning) ---
BASE_MODEL = "en_core_web_sm"
