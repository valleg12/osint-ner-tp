# AI Deployment — Déploiement d'une solution d'IA

## Renseignement OSINT par NER militaire sur corpus TASS

**Auteur :** Victorien Alleg — MSc 2025-2026
**Dépôt GitHub :** https://github.com/valleg12/osint-ner-tp *(privé — ajouter l'intervenant en collaborateur)*

---

## 1. Objectif & pipeline

Construire une chaîne de traitement complète qui part de texte brut (corpus
d'articles de la rubrique « Guerre » de *tass.com*, format JSON) et aboutit à des
dashboards analytiques, afin de repérer des tendances de renseignement : quelles
armes sont citées, quelles unités et organisations apparaissent, et comment cela
évolue dans le temps.

```
data_set.json ─▶ 1. extraction ─▶ 2. annotation ─▶ 3. fine-tuning NER ─▶ 4. inférence ─┬▶ 6a. Elasticsearch
 (corpus TASS)     (texte propre)   (format spaCy)   (en_core_web_sm)      (entités)     └▶ 6b. dashboards Kibana
```

| Étape | Entrée → Sortie | Volume |
| ----- | --------------- | ------ |
| 1. Extraction | `data_set.json` → `corpus.jsonl` | 21 742 lus → **21 704 conservés** |
| 2. Annotation | `corpus.jsonl` → `annotations.json` (format spaCy) | 400 articles, 1 632 entités, offsets validés ✅ |
| 3. Fine-tuning | `annotations.json` → `model-best` | split 80/20, transfer learning |
| 4. Inférence | `model-best` → `enriched.jsonl` | **3 000 articles**, 13 502 entités |
| 5. Ingestion | `enriched.jsonl` → Elasticsearch + Kibana | index `osint_articles` |

**Période couverte par le corpus :** 2015-09-07 → 2025-10-26.

## 2. Choix de modélisation

- **Modèle de base : `en_core_web_sm`** (petit modèle anglais de spaCy, léger,
  rapide, déjà compétent sur les entités génériques). On fait du **transfer
  learning** (`[components.ner] source = "en_core_web_sm"`) plutôt que d'entraîner
  un NER vierge.
- **Schéma à 3 labels** : `WEAPON`, `MIL_UNIT`, `MIL_ORG` — assez expressif pour
  produire du renseignement utile, assez simple pour être annoté et entraîné dans
  le temps d'un TP.
- **NER plutôt que LLM en production** : coût/vitesse (des milliers d'articles en
  local sans appel API payant), **déterminisme** (même entrée → même sortie,
  crucial pour la traçabilité), sortie structurée native, souveraineté. Le LLM
  est réservé à la **pré-annotation** du dataset d'entraînement ; la validation
  humaine des offsets reste obligatoire.

## 3. Analyse des métriques (jeu de dev, 80/20)

| Label | Précision | Rappel | F1 |
| ----- | --------: | -----: | -: |
| **Global** | 0.980 | 0.966 | **0.973** |
| MIL_ORG | 0.991 | 0.991 | 0.991 |
| WEAPON | 0.991 | 0.986 | 0.988 |
| MIL_UNIT | 0.846 | 0.733 | 0.786 |

**Lecture.** Le modèle est très performant sur `WEAPON` et `MIL_ORG` (F1 ≈ 0.99) :
ce sont des entités à forte régularité lexicale (noms propres de systèmes
d'armes, dénominations officielles d'organisations) que le transfer learning
capte vite. `MIL_UNIT` est nettement plus faible (F1 0.79, rappel 0.73) : les
unités combattantes ont des frontières ambiguës (« an assault brigade », « the
company ») et un vocabulaire plus variable, ce qui correspond exactement aux
**limites attendues du NER** (contexte long, formulations ambiguës).

**Limite identifiée honnêtement.** L'entité la plus fréquente sous `MIL_UNIT` à
l'inférence est *« the company »* (111 occurrences) : c'est un **faux positif**
récurrent — « company » au sens générique est confondu avec l'unité militaire.
Piste d'amélioration : enrichir l'annotation avec des contre-exemples, ou exiger
un déterminant numéral/ordinal dans la règle d'annotation.

> Métriques reproductibles depuis `output/model-best/meta.json`.

## 4. Résultats d'inférence — que constate-t-on ?

Top entités extraites sur 3 000 articles :

| WEAPON | MIL_ORG | MIL_UNIT |
| ------ | ------- | -------- |
| missile (530) | defense ministry (899) | territorial defense brigade (49) |
| drones (475) | navy (260) | national guard brigade (26) |
| drone (470) | russian armed forces (217) | marine brigade (20) |
| artillery (465) | nato (180) | motorized infantry brigade (18) |
| himars (123) | general staff (91) | … |

**Tendances.**
- Le champ lexical est dominé par **drones + missiles + artillerie** : la guerre
  décrite par la source est avant tout une guerre de frappes à distance.
- `defense ministry` écrase tout (899) : signature d'un corpus **institutionnel**,
  fait de communiqués officiels — un signal du biais éditorial autant qu'un fait.
- Présence de matériels occidentaux nommés (`himars`) : la source met en avant
  l'armement adverse, cohérent avec un cadrage pro-russe.

## 5. Dashboards Kibana

> **À insérer : screenshots des dashboards** une fois le cluster Elastic Cloud
> déployé (`make step5`). Configuration prévue (mapping : entités en `keyword`,
> `date` en date) :

1. **Top WEAPON / MIL_UNIT / MIL_ORG** — 3 visualisations *Bar/Lens* en agrégation
   `terms` sur chaque champ keyword (top 15). *Pourquoi :* identifier d'un coup
   d'œil le matériel et les acteurs dominants.
2. **Histogramme temporel** — *date_histogram* sur `date` (intervalle mensuel),
   éventuellement empilé par label. *Pourquoi :* détecter les pics de mentions et
   les corréler à des événements.
3. **Co-occurrences** — table croisée WEAPON × MIL_UNIT (sub-aggregation `terms`).
   *Pourquoi :* relier un système d'arme à une unité qui l'emploie.
4. **Filtres par période** + recherche plein-texte sur `text`.

## 6. Note de renseignement (courte)

**Source & fiabilité.** Corpus issu de **TASS**, média d'État russe : biais
éditorial fort. On n'extrait pas « la vérité » mais **ce que la source affirme**.
La prédominance des communiqués du *defense ministry* confirme un cadrage
institutionnel à intégrer dans toute interprétation.

**Constats.** Sur la période 2015→2025, le discours de la source est centré sur
les **frappes à distance** (drones, missiles, artillerie) et relaie nommément
l'armement occidental (HIMARS). Les organisations de haut niveau (ministères,
états-majors, marine) structurent le récit, tandis que les unités combattantes
précises sont moins fréquemment nommées.

**Limites.** Biais de source ; entités sous-représentées ; faiblesse du NER sur
les unités (F1 0.79) et faux positifs génériques (« the company »). Les tendances
**suggèrent** une orientation du discours, elles ne prouvent pas un ordre de
bataille — tout constat doit être recoupé avec des sources indépendantes.
