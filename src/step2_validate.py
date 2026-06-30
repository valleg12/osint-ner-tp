"""Étape 2c — Validation humaine des annotations (OBLIGATOIRE).

Slide : « Relisez un échantillon d'annotations à la main. Vérifiez que les
offsets correspondent bien au texte source. »

- Vérifie automatiquement que chaque (start, end) correspond à un span valide.
- Affiche un échantillon lisible (texte avec entités surlignées) pour relecture.

Usage :
    python step2_validate.py            # 10 exemples
    python step2_validate.py --sample 20
"""

import argparse
import json

from config import ANNOTATIONS, LABELS


def check_offsets(dataset) -> list[str]:
    """Renvoie la liste des erreurs d'offset / de label détectées."""
    errors = []
    for idx, (text, ann) in enumerate(dataset):
        for start, end, label in ann["entities"]:
            if label not in LABELS:
                errors.append(f"#{idx}: label inconnu '{label}'")
            if not (0 <= start < end <= len(text)):
                errors.append(f"#{idx}: offsets hors limites ({start},{end})")
                continue
            frag = text[start:end]
            if not frag.strip():
                errors.append(f"#{idx}: span vide à ({start},{end})")
    return errors


def highlight(text: str, entities: list) -> str:
    """Insère des marqueurs [ENTITÉ](LABEL) pour relecture visuelle."""
    out, last = [], 0
    for start, end, label in sorted(entities, key=lambda e: e[0]):
        out.append(text[last:start])
        out.append(f"[{text[start:end]}]({label})")
        last = end
    out.append(text[last:])
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validation des annotations")
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    with open(ANNOTATIONS, encoding="utf-8") as f:
        dataset = json.load(f)

    errors = check_offsets(dataset)
    print("=" * 70)
    print(f"Contrôle automatique des offsets sur {len(dataset)} articles")
    print("=" * 70)
    if errors:
        print(f"❌ {len(errors)} erreur(s) :")
        for e in errors[:20]:
            print("   -", e)
    else:
        print("✅ Tous les offsets correspondent au texte source.")

    print(f"\nÉchantillon ({args.sample} articles avec entités) — à relire :\n")
    shown = 0
    for text, ann in dataset:
        if not ann["entities"]:
            continue
        print("-" * 70)
        print(highlight(text[:400], [e for e in ann["entities"] if e[1] <= 400]))
        shown += 1
        if shown >= args.sample:
            break


if __name__ == "__main__":
    main()
