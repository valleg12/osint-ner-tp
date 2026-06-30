"""Étape 2 — Annoter le corpus (format spaCy).

Objectif : produire annotations.json au format spaCy :
    [
      ["The brigade fired Kalibr missiles.",
       {"entities": [[4, 11, "MIL_UNIT"], [18, 24, "WEAPON"]]}],
      ...
    ]

Stratégie (slide « pré-annotation par LLM ») :
  - Si ANTHROPIC_API_KEY est défini -> pré-annotation par Claude.
  - Sinon -> annotateur hors-ligne déterministe (gazetteer + regex).
  Dans les deux cas, les offsets sont recalculés et validés sur le texte source
  (slide « Validation humaine : vérifiez que les offsets correspondent »).

Usage :
    python step2_annotate.py --limit 300          # nombre d'articles à annoter
    python step2_annotate.py --limit 300 --offline # force le mode hors-ligne
"""

import argparse
import json
import os

from dotenv import load_dotenv

from annotators import LLMAnnotator, OfflineAnnotator, resolve_offsets
from config import ANNOTATIONS, CORPUS, DATA_PROC

load_dotenv()

# Limite la longueur envoyée à l'annotateur (les 1ers paragraphes suffisent et
# contiennent l'essentiel des entités ; réduit le coût LLM).
MAX_CHARS = 1500


def load_corpus(limit: int) -> list[dict]:
    records = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
            if len(records) >= limit:
                break
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotation du corpus (format spaCy)")
    parser.add_argument("--limit", type=int, default=300, help="nb d'articles à annoter")
    parser.add_argument("--offline", action="store_true", help="force l'annotateur hors-ligne")
    args = parser.parse_args()

    DATA_PROC.mkdir(parents=True, exist_ok=True)

    use_llm = not args.offline and bool(os.getenv("ANTHROPIC_API_KEY"))
    if use_llm:
        print(f"Mode : pré-annotation LLM ({os.getenv('ANNOTATION_MODEL', 'claude-opus-4-8')})")
        annotator = LLMAnnotator()
    else:
        reason = "forcé" if args.offline else "pas de ANTHROPIC_API_KEY"
        print(f"Mode : annotateur hors-ligne (gazetteer + regex) [{reason}]")
        annotator = OfflineAnnotator()

    records = load_corpus(args.limit)
    dataset = []
    n_entities = 0

    for i, rec in enumerate(records, 1):
        text = rec["text"][:MAX_CHARS]
        try:
            spans = annotator.annotate(text)
        except Exception as exc:  # ne pas perdre tout le run sur une erreur API
            print(f"  [!] article {rec.get('id')} : {exc}")
            continue
        entities = resolve_offsets(text, spans)
        n_entities += len(entities)
        dataset.append([text, {"entities": [list(e) for e in entities]}])
        if i % 25 == 0:
            print(f"  {i}/{len(records)} articles annotés…")

    with open(ANNOTATIONS, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    docs_with_ents = sum(1 for _, a in dataset if a["entities"])
    print(f"\nArticles annotés      : {len(dataset)}")
    print(f"Articles avec entités : {docs_with_ents}")
    print(f"Entités totales       : {n_entities}")
    print(f"Annotations écrites   : {ANNOTATIONS}")
    print("\n⚠️  Validation humaine OBLIGATOIRE : relisez un échantillon avec")
    print("    python step2_validate.py")


if __name__ == "__main__":
    main()
