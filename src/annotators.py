"""Annotateurs pour l'étape 2 — produisent des entités (texte + label).

Deux stratégies :
  - OfflineAnnotator : gazetteer + regex, déterministe, sans clé API (fallback).
  - LLMAnnotator     : pré-annotation par Claude (slide « pré-annotation par LLM »).

Les deux renvoient une liste de spans {"text": ..., "label": ...}.
Le calcul des offsets exacts (et leur validation) est fait par resolve_offsets().
"""

from __future__ import annotations

import os
import re

from config import LABELS

# ---------------------------------------------------------------------------
# Résolution des offsets (commun aux deux annotateurs)
# ---------------------------------------------------------------------------

def resolve_offsets(text: str, spans: list[dict]) -> list[tuple[int, int, str]]:
    """Transforme des spans {text,label} en (start, end, label) NON chevauchants.

    On cherche chaque mention dans le texte source : c'est plus robuste que de
    demander des offsets entiers à un LLM. Les chevauchements sont écartés
    (spaCy refuse les entités qui se recouvrent).
    """
    occupied: list[tuple[int, int]] = []
    entities: list[tuple[int, int, str]] = []

    # Spans les plus longs d'abord : on privilégie « 58th Combined Arms Army »
    # à « Army » seul.
    for span in sorted(spans, key=lambda s: len(s.get("text", "")), reverse=True):
        frag = (span.get("text") or "").strip()
        label = span.get("label")
        if not frag or label not in LABELS:
            continue
        for m in re.finditer(re.escape(frag), text):
            start, end = m.start(), m.end()
            if any(start < o_end and end > o_start for o_start, o_end in occupied):
                continue  # chevauche une entité déjà placée
            occupied.append((start, end))
            entities.append((start, end, label))

    entities.sort(key=lambda e: e[0])
    return entities


# ---------------------------------------------------------------------------
# Annotateur hors-ligne (gazetteer + regex)
# ---------------------------------------------------------------------------

class OfflineAnnotator:
    """Bootstrap déterministe — utile pour faire tourner le pipeline sans LLM."""

    # Armes : noms propres de systèmes + noms communs de matériel
    WEAPON_TERMS = [
        "Burevestnik", "Kalibr", "Iskander", "Kinzhal", "Zircon", "Tsirkon",
        "Sarmat", "Topol", "Oreshnik", "Geran", "Geran-2", "Shahed", "Lancet",
        "Tornado", "Tornado-S", "Grad", "Smerch", "Uragan", "Solntsepek",
        "Tochka", "Tochka-U", "Bastion", "Pantsir", "Buk", "Tor", "S-300",
        "S-400", "S-500", "TOS-1", "Krasnopol", "Krasukha", "Su-34", "Su-35",
        "Su-57", "MiG-31", "Ka-52", "Mi-28", "T-72", "T-80", "T-90", "Armata",
        "HIMARS", "ATACMS", "Patriot", "Storm Shadow", "Javelin", "Bradley",
        "Leopard", "Abrams", "Bayraktar", "Switchblade", "Excalibur",
    ]
    WEAPON_NOUNS = [
        "missiles?", "cruise missiles?", "ballistic missiles?", "drones?",
        "loitering munitions?", "tanks?", "artillery", "howitzers?",
        "rocket launchers?", "multiple launch rocket systems?", "warheads?",
    ]

    # Unités combattantes (souvent précédées d'un ordinal / nombre)
    UNIT_RE = re.compile(
        r"\b(?:\d{1,4}(?:st|nd|rd|th)?\s+)?"
        r"(?:[A-Z][a-z]+\s+){0,3}"
        r"(?:brigade|battalion|regiment|division|corps|company|platoon|"
        r"airborne (?:brigade|division|regiment)|motorized rifle (?:brigade|division|regiment)|"
        r"tank (?:brigade|division|regiment)|combined arms army)\b",
        re.IGNORECASE,
    )

    # Organisations militaires de haut niveau
    ORG_TERMS = [
        "General Staff", "Defense Ministry", "Ministry of Defense",
        "Ministry of Defence", "Armed Forces", "Russian Armed Forces",
        "Ukrainian Armed Forces", "Armed Forces of Ukraine", "Aerospace Forces",
        "Airborne Forces", "Navy", "Black Sea Fleet", "Northern Fleet",
        "Pentagon", "NATO", "Wagner", "Wagner Group", "National Guard",
        "Western Military District", "Southern Military District", "Kremlin",
    ]

    def __init__(self) -> None:
        self._weapon_re = self._terms_re(self.WEAPON_TERMS)
        self._weapon_noun_re = re.compile(
            r"\b(" + "|".join(self.WEAPON_NOUNS) + r")\b", re.IGNORECASE
        )
        self._org_re = self._terms_re(self.ORG_TERMS)

    @staticmethod
    def _terms_re(terms: list[str]) -> re.Pattern:
        ordered = sorted(terms, key=len, reverse=True)
        return re.compile(r"\b(" + "|".join(re.escape(t) for t in ordered) + r")\b")

    def annotate(self, text: str) -> list[dict]:
        spans: list[dict] = []
        for m in self._weapon_re.finditer(text):
            spans.append({"text": m.group(0), "label": "WEAPON"})
        for m in self._weapon_noun_re.finditer(text):
            spans.append({"text": m.group(0), "label": "WEAPON"})
        for m in self.UNIT_RE.finditer(text):
            spans.append({"text": m.group(0).strip(), "label": "MIL_UNIT"})
        for m in self._org_re.finditer(text):
            spans.append({"text": m.group(0), "label": "MIL_ORG"})
        return spans


# ---------------------------------------------------------------------------
# Annotateur LLM (Claude)
# ---------------------------------------------------------------------------

PROMPT = """You are a Named Entity Recognition annotator for military OSINT.

Extract ONLY these three entity types from the text:
- WEAPON   : weapon systems and materiel (missiles, drones, tanks, artillery, launchers, named systems like "Kalibr", "HIMARS")
- MIL_UNIT : fighting units (brigades, battalions, regiments, divisions, corps — e.g. "58th Combined Arms Army")
- MIL_ORG  : high-level military organizations (general staffs, defense ministries, armed forces, fleets — e.g. "General Staff", "Black Sea Fleet")

Rules:
- Copy each entity span EXACTLY as it appears in the text (same casing, same words).
- Do not invent entities that are not present.
- Do not annotate countries, people, or cities.
- If a boundary is ambiguous, prefer the longest meaningful span and stay consistent.
- Return an empty list if there are no entities."""

SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "label": {"type": "string", "enum": LABELS},
                },
                "required": ["text", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entities"],
    "additionalProperties": False,
}


class LLMAnnotator:
    """Pré-annotation par Claude. Renvoie des spans {text,label} (offsets résolus après)."""

    def __init__(self, model: str | None = None) -> None:
        import anthropic  # import tardif : optionnel

        self.client = anthropic.Anthropic()
        self.model = model or os.getenv("ANNOTATION_MODEL", "claude-opus-4-8")

    def annotate(self, text: str) -> list[dict]:
        import json

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=PROMPT,
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        raw = next((b.text for b in resp.content if b.type == "text"), "{}")
        try:
            return json.loads(raw).get("entities", [])
        except json.JSONDecodeError:
            return []
