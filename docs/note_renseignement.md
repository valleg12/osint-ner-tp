# Note de renseignement (gabarit)

> À compléter après l'analyse des dashboards. Garder le cadre OSINT en tête :
> source = **TASS** (média d'État russe), biais éditorial fort. On rapporte ce
> que la source affirme, pas une vérité établie.

## 1. Contexte & source
- Corpus : rubrique « Guerre » de tass.com, anglais, format JSON.
- Période couverte : _(min → max des dates)_.
- Volume analysé : _(nb d'articles, nb d'entités extraites)_.
- **Fiabilité / intention** : source étatique → cadrage favorable à la partie russe.

## 2. Méthode
- NER fine-tuné (spaCy, transfer learning depuis `en_core_web_sm`), 3 labels
  (WEAPON, MIL_UNIT, MIL_ORG). Annotation : _(LLM Claude / hors-ligne)_.
- Métriques dev (étape 3c) : Précision _…_, Rappel _…_, F1 _…_ (`output/model-best/meta.json`).

## 3. Constats (tendances)
- **Armes les plus citées** : _(top WEAPON)_ — interprétation.
- **Unités / organisations** : _(top MIL_UNIT / MIL_ORG)_.
- **Évolution temporelle** : _(pics, corrélation avec des événements)_.
- **Co-occurrences notables** : _(arme ↔ unité, arme ↔ lieu)_.

## 4. Limites & biais
- Biais éditorial de la source ; entités absentes / sous-représentées.
- Limites du NER : contexte long, coréférence, formulations ambiguës.

## 5. Conclusion
- Ce que les données **suggèrent** (et non prouvent), pistes de recoupement.
