# OSINT-NER — Déploiement d'une solution d'IA (AI Deployment, MSc 2025-2026)

Chaîne de traitement complète qui part de **texte brut** (corpus d'articles
« Guerre » de [tass.com](https://tass.com), format JSON) et aboutit à des
**dashboards analytiques** de renseignement OSINT.

On entraîne un modèle **NER** (Named Entity Recognition) à reconnaître un schéma
militaire personnalisé, puis on indexe les entités extraites dans Elasticsearch
pour les visualiser dans Kibana.

> ⚠️ **Cadre OSINT.** TASS est un média d'État russe : les données portent un
> biais éditorial fort. On n'extrait jamais « la vérité », mais **ce qu'une
> source affirme**. La fiabilité et l'intention de la source font partie de
> l'analyse (voir la note de renseignement, [`docs/note_renseignement.md`](docs/note_renseignement.md)).

## Schéma d'annotation — 3 labels

| Label      | Définition                          | Exemples                                   |
| ---------- | ----------------------------------- | ------------------------------------------ |
| `WEAPON`   | systèmes et matériels               | missiles, blindés, drones, lance-roquettes |
| `MIL_UNIT` | unités combattantes                 | brigades, bataillons, régiments, divisions |
| `MIL_ORG`  | organisations de haut niveau        | états-majors, ministères, forces armées    |

## Pipeline

```
data_set.json ─▶ 1. extraction ─▶ 2. annotation ─▶ 3. fine-tuning NER ─▶ 4. inférence ─┬▶ 6a. Elasticsearch
  (corpus TASS)    (texte propre)   (format spaCy)   (en_core_web_sm)      (entités)     └▶ 6b. dashboards Kibana
```

## Stack & choix techniques

- **spaCy** + **`en_core_web_sm`** : petit modèle anglais, rapide, déjà compétent
  sur les entités génériques (PERSON, GPE, ORG). On fait du **transfer learning**
  plutôt que d'entraîner à zéro.
- **Pourquoi un NER et pas un LLM en production ?** coût/vitesse (des milliers
  d'articles en local, sans appel API payant), **déterminisme** (traçabilité du
  renseignement), sortie structurée native, souveraineté. Le LLM sert ici à
  **pré-annoter** le dataset d'entraînement.
- **Elasticsearch + Kibana** : recherche plein-texte, agrégations côté serveur
  (top entités, séries temporelles, co-occurrences), dashboards sans coder.

## Installation

```bash
make install     # crée .venv, installe les dépendances et en_core_web_sm
cp .env.example .env   # puis renseigner les clés (optionnel pour 1→4)
```

> Python 3.10+ requis. Sans Make : `python3 -m venv .venv && .venv/bin/pip
> install -r requirements.txt && .venv/bin/python -m spacy download en_core_web_sm`.

## Lancer le pipeline

```bash
make step1       # Étape 1 — extraction : data/processed/corpus.jsonl
make step2       # Étape 2 — annotation : data/processed/annotations.json
make validate    # Étape 2c — contrôle des offsets + relecture
make step3       # Étape 3 — split train/dev + .spacy + configs/config.cfg
make train       # Étape 3c — entraînement : output/model-best
make step4       # Étape 4 — inférence : data/processed/enriched.jsonl
make step5       # Étape 5 — ingestion Elasticsearch (nécessite .env)
```

Ou tout d'un coup (sauf ES) : `make pipeline`.

### Étape 2 — annotation : LLM ou hors-ligne

- **Avec `ANTHROPIC_API_KEY`** dans `.env` → pré-annotation par **Claude**
  (`claude-opus-4-8` par défaut, configurable via `ANNOTATION_MODEL`). Prompt
  strict imposant les 3 labels et une sortie structurée.
- **Sans clé** → annotateur **hors-ligne** (gazetteer + regex), déterministe :
  le pipeline tourne de bout en bout sans dépendance externe.

Dans les deux cas, les **offsets sont recalculés et validés** sur le texte source
(`make validate`) — la validation humaine reste obligatoire (relecture d'un
échantillon).

### Étape 5 — Elasticsearch & Kibana

1. Créer un déploiement sur <https://cloud.elastic.co> (14 jours gratuits).
2. Renseigner `ES_CLOUD_ID` + `ES_API_KEY` dans `.env`.
3. `make step5` crée l'index (mapping `text` / `date` / entités en `keyword`) et
   ingère `enriched.jsonl`.
4. Dans Kibana, créer une *data view* sur `osint_articles` puis les dashboards :
   - **Top WEAPON / MIL_UNIT / MIL_ORG** (agrégation *terms*)
   - **Histogramme temporel** des mentions (*date_histogram* sur `date`)
   - **Co-occurrences** d'entités, **filtres** par période

## Arborescence

```
src/
  config.py            # chemins, labels, modèle de base
  step1_extract.py     # JSON brut -> corpus.jsonl
  annotators.py        # annotateurs LLM (Claude) + hors-ligne
  step2_annotate.py    # corpus -> annotations.json (format spaCy)
  step2_validate.py    # contrôle des offsets + relecture
  step3_prepare_spacy.py  # split + DocBin + config.cfg (transfer learning)
  step4_infer.py       # model-best -> enriched.jsonl (entités par label)
  step5_ingest_es.py   # ingestion Elasticsearch
data/raw/data_set.json # corpus source (non commité)
data/processed/        # sorties intermédiaires
configs/config.cfg     # config spaCy générée (étape 3)
output/model-best/     # meilleur modèle (étape 3c)
docs/note_renseignement.md  # note de renseignement (livrable)
```

## Livrable attendu

Un PDF contenant : le lien GitHub du code, des screenshots des dashboards, une
analyse des métriques et des choix de dashboards, et une note de renseignement
courte (gabarit dans [`docs/note_renseignement.md`](docs/note_renseignement.md)).

## Déploiement — API REST, Docker, CI/CD

Le modèle fine-tuné est servi par une API **FastAPI** (`src/api.py`) :

| Méthode | Route | Rôle |
| ------- | ----- | ---- |
| GET | `/health` | disponibilité du service et du modèle |
| GET | `/metrics` | monitoring : requêtes, erreurs, latence, entités par label |
| POST | `/extract` | entités WEAPON / MIL_UNIT / MIL_ORG d'un texte |
| POST | `/extract/batch` | idem pour 1 à 100 textes |

```bash
pip install -r requirements-api.txt
make api                                  # = MODEL_PATH=output/model-best uvicorn src.api:app --port 8000
# documentation interactive : http://localhost:8000/docs
docker build -t osint-ner-api . && docker run -p 8000:8000 -v "$PWD/output/model-best:/model" osint-ner-api
```

**CI (GitHub Actions, `.github/workflows/ci.yml`)** : à chaque push, `ruff` (lint) → `pytest` (6 tests du
contrat de l'API, avec un mini-modèle à règles puisque le modèle entraîné n'est pas versionné) → `docker build`.
