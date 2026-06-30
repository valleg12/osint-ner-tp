"""Étape 4 — Inférer sur les articles.

Objectif : appliquer le modèle fine-tuné à une partie du corpus et regrouper
les entités par label (slide étape 5 : « regroupez les entités par label »).

Sortie : data/processed/enriched.jsonl — un article enrichi par ligne :
    {
      "id": ..., "text": ..., "title": ..., "date": ..., "url": ..., "tags": [...],
      "weapons": [...], "mil_units": [...], "mil_orgs": [...],
      "n_entities": N
    }

Usage :
    python step4_infer.py --limit 3000
"""

import argparse
import json
from collections import Counter

import spacy

from config import CORPUS, ENRICHED, MODEL_BEST

LABEL_TO_FIELD = {"WEAPON": "weapons", "MIL_UNIT": "mil_units", "MIL_ORG": "mil_orgs"}
MAX_CHARS = 4000  # borne le texte analysé par article


def main() -> None:
    parser = argparse.ArgumentParser(description="Inférence NER sur le corpus")
    parser.add_argument("--limit", type=int, default=3000)
    args = parser.parse_args()

    if not MODEL_BEST.exists():
        raise SystemExit(
            f"Modèle introuvable : {MODEL_BEST}\n"
            "Entraînez-le d'abord (étape 3c) — voir le README / Makefile."
        )

    nlp = spacy.load(MODEL_BEST)

    records = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
            if len(records) >= args.limit:
                break

    texts = [r["text"][:MAX_CHARS] for r in records]
    label_counts: Counter = Counter()
    top_entities: Counter = Counter()
    n_with_ents = 0

    with open(ENRICHED, "w", encoding="utf-8") as out:
        for rec, doc in zip(records, nlp.pipe(texts, batch_size=64)):
            grouped: dict[str, list[str]] = {"weapons": [], "mil_units": [], "mil_orgs": []}
            for ent in doc.ents:
                field = LABEL_TO_FIELD.get(ent.label_)
                if not field:
                    continue
                grouped[field].append(ent.text)
                label_counts[ent.label_] += 1
                top_entities[(ent.label_, ent.text.lower())] += 1
            # dédoublonne en gardant l'ordre
            for k in grouped:
                grouped[k] = list(dict.fromkeys(grouped[k]))
            n_ent = sum(len(v) for v in grouped.values())
            if n_ent:
                n_with_ents += 1
            out.write(json.dumps({
                "id": rec["id"], "text": rec["text"], "title": rec["title"],
                "date": rec["date"], "url": rec["url"], "tags": rec["tags"],
                **grouped, "n_entities": n_ent,
            }, ensure_ascii=False) + "\n")

    print(f"Articles traités       : {len(records)}")
    print(f"Articles avec entités  : {n_with_ents}")
    print(f"Entités par label      : {dict(label_counts)}")
    print(f"Sortie enrichie        : {ENRICHED}")
    print("\nTop 10 entités (— Que constatez-vous ? slide étape 4) :")
    for (label, text), n in top_entities.most_common(10):
        print(f"   {n:4d}  {label:9s} {text}")


if __name__ == "__main__":
    main()
