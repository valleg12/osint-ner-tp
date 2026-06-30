.PHONY: install step1 step2 validate step3 train step4 step5 pipeline clean

PY := .venv/bin/python
SPACY := .venv/bin/python -m spacy

install:                ## Crée le venv et installe les dépendances + modèle de base
	python3 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt
	$(SPACY) download en_core_web_sm

step1:                  ## Étape 1 — extraction du texte
	cd src && ../$(PY) step1_extract.py

step2:                  ## Étape 2 — annotation (LLM si clé, sinon hors-ligne)
	cd src && ../$(PY) step2_annotate.py --limit 300

validate:               ## Étape 2c — validation des offsets + échantillon
	cd src && ../$(PY) step2_validate.py

step3:                  ## Étape 3a/3b — split + DocBin + config.cfg
	cd src && ../$(PY) step3_prepare_spacy.py

train:                  ## Étape 3c — entraînement (sauvegarde output/model-best)
	$(SPACY) train configs/config.cfg \
		--output ./output \
		--paths.train data/processed/train.spacy \
		--paths.dev data/processed/dev.spacy

step4:                  ## Étape 4 — inférence sur le corpus
	cd src && ../$(PY) step4_infer.py --limit 3000

step5:                  ## Étape 5 — ingestion Elasticsearch
	cd src && ../$(PY) step5_ingest_es.py --recreate

pipeline: step1 step2 validate step3 train step4   ## Tout sauf l'ingestion ES

clean:                  ## Nettoie les artefacts générés
	rm -rf data/processed/*.jsonl data/processed/*.json data/processed/*.spacy
	rm -rf output configs/config.cfg
