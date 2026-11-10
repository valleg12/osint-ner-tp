"""Étape 1 — Extraire le texte.

Objectif : produire un corpus propre à partir de data_set.json.
  - Parser le JSON.
  - Isoler le champ texte (titre + corps).
  - Conserver le découpage par article (un objet JSON par ligne).
  - Nettoyage minimal (espaces superflus, caractères parasites).

Sortie : data/processed/corpus.jsonl
"""

import json
import re
from datetime import datetime, timezone

from config import CORPUS, DATA_PROC, RAW_DATASET

# Espaces multiples / sauts de ligne parasites
_WS = re.compile(r"\s+")


def clean(text: str) -> str:
    """Nettoyage minimal : normalise les espaces, retire les caractères de contrôle."""
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("​", "")
    text = _WS.sub(" ", text)
    return text.strip()


def build_text(article: dict) -> str:
    """Texte analysé = titre + corps (les entités apparaissent souvent dans le titre)."""
    title = clean(article.get("title", ""))
    body = clean(article.get("text", ""))
    if title and body:
        return f"{title}. {body}" if not title.endswith((".", "!", "?")) else f"{title} {body}"
    return body or title


def iso_date(ts) -> str | None:
    """Convertit le timestamp unix TASS en date ISO 8601 (UTC)."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError, TypeError):
        return None


def main() -> None:
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    with open(RAW_DATASET, encoding="utf-8") as f:
        articles = json.load(f)

    kept = skipped = 0
    with open(CORPUS, "w", encoding="utf-8") as out:
        for art in articles:
            text = build_text(art)
            if len(text) < 30:  # rejette les entrées vides / trop courtes
                skipped += 1
                continue
            record = {
                "id": art.get("id"),
                "text": text,
                "title": clean(art.get("title", "")),
                "date": iso_date(art.get("date")),
                "url": f"https://tass.com{art.get('link', '')}" if art.get("link") else None,
                "mark": art.get("mark"),
                "tags": art.get("tags") or [],
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1

    print(f"Articles lus      : {len(articles)}")
    print(f"Articles conservés : {kept}")
    print(f"Articles ignorés   : {skipped} (texte < 30 caractères)")
    print(f"Corpus écrit       : {CORPUS}")


if __name__ == "__main__":
    main()
