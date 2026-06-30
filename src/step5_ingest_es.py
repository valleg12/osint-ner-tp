"""Étape 5 — Ingérer dans Elasticsearch (pour dashboards Kibana).

  - Déploiement du cluster : https://cloud.elastic.co (14 jours gratuits).
  - Modélise l'index (mapping : text, date, entités en keyword par type).
  - Ingère chaque article enrichi (slide étape 5).

Connexion via .env :
  - ES_CLOUD_ID + ES_API_KEY  (Elastic Cloud)         OU
  - ES_URL                    (cluster local docker)

Usage :
    python step5_ingest_es.py
    python step5_ingest_es.py --recreate   # supprime puis recrée l'index
"""

import argparse
import json
import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm

from config import ENRICHED

load_dotenv()

INDEX = os.getenv("ES_INDEX", "osint_articles")

MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "title": {"type": "text"},
            "date": {"type": "date"},
            "url": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "weapons": {"type": "keyword"},
            "mil_units": {"type": "keyword"},
            "mil_orgs": {"type": "keyword"},
            "n_entities": {"type": "integer"},
        }
    }
}


def connect() -> Elasticsearch:
    cloud_id = os.getenv("ES_CLOUD_ID")
    api_key = os.getenv("ES_API_KEY")
    url = os.getenv("ES_URL")
    if cloud_id and api_key:
        return Elasticsearch(cloud_id=cloud_id, api_key=api_key)
    if url:
        return Elasticsearch(url, api_key=api_key) if api_key else Elasticsearch(url)
    raise SystemExit(
        "Connexion ES manquante : renseignez ES_CLOUD_ID + ES_API_KEY (Elastic Cloud) "
        "ou ES_URL (local) dans .env (voir .env.example)."
    )


def actions(es_index: str):
    with open(ENRICHED, encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            yield {"_index": es_index, "_id": doc["id"], "_source": doc}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion Elasticsearch")
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    es = connect()
    print("Cluster :", es.info()["version"]["number"])

    if args.recreate and es.indices.exists(index=INDEX):
        es.indices.delete(index=INDEX)
        print(f"Index supprimé : {INDEX}")
    if not es.indices.exists(index=INDEX):
        es.indices.create(index=INDEX, **MAPPING)
        print(f"Index créé : {INDEX}")

    n_docs = sum(1 for _ in open(ENRICHED, encoding="utf-8"))
    ok, errors = helpers.bulk(
        es, tqdm(actions(INDEX), total=n_docs, desc="Ingestion"), raise_on_error=False
    )
    es.indices.refresh(index=INDEX)
    print(f"\nDocuments indexés : {ok}")
    if errors:
        print(f"Erreurs : {len(errors)} (ex. {errors[0]})")
    print(f"Index « {INDEX} » prêt — construisez vos dashboards dans Kibana.")
    print("Idées de visualisations (slide étape 5) :")
    print("  - Top WEAPON / MIL_UNIT / MIL_ORG  (agrégation terms)")
    print("  - Histogramme temporel des mentions (date_histogram sur 'date')")
    print("  - Co-occurrences d'entités / filtres par période")


if __name__ == "__main__":
    main()
