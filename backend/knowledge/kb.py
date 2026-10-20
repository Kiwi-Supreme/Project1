"""
knowledge/kb.py

The ONE place the application reads chemical knowledge from.  It loads the four
JSON files in chemical_knowledge/ and answers questions about them:

    elements.json          118 elements (mass, group, electronegativity, radii ...)
    molecules.json         the species the simulator can handle: atoms, molecules, ions
    force_parameters.json  the force-field parameters each species is simulated with
    interactions.json      kinds of intermolecular force + rules for combining species

The language layer (agent/) uses `find_mentions()` to identify substances in a
sentence; the planner uses `molecule()` / `model()` to get the properties that
configure the simulation.  Nothing here calls an LLM or invents a value: if a
property is not in the JSON files, the answer is "unknown".
"""

import json
import os
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KB_DIR = os.path.join(PROJECT_ROOT, "chemical_knowledge")

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁺⁻",
                            "0123456789+-")


def normalise_text(text: str) -> str:
    """H₂O -> H2O, Na⁺ -> Na+  (so formulas written with sub/superscripts match)."""
    return text.translate(_SUBSCRIPTS)


def _load(name):
    with open(os.path.join(KB_DIR, name), encoding="utf-8") as f:
        return json.load(f)


class UnknownSubstance(KeyError):
    pass


class KnowledgeBase:
    def __init__(self):
        self.elements = _load("elements.json")
        self.molecules = _load("molecules.json")
        fp = _load("force_parameters.json")
        self.models = fp["models"]
        self.reaxff = fp["reaxff"]
        self.force_meta = fp["_meta"]
        self.interactions = _load("interactions.json")
        self._element_by_name = {e["name"].lower(): e for e in self.elements.values()}
        # alias -> molecule id.  Short purely-alphabetic aliases ("he", "ar") are
        # excluded: they collide with ordinary English words.
        self._alias = {}
        for mid, m in self.molecules.items():
            for a in [mid.replace("_", " ")] + m["aliases"] + [m["formula"]]:
                a = normalise_text(a).lower()
                if a.isalpha() and len(a) < 4:
                    continue
                self._alias[a] = mid
        pats = sorted(self._alias, key=len, reverse=True)
        self._alias_re = re.compile(
            r"(?<![A-Za-z0-9])(" + "|".join(re.escape(p) for p in pats) + r")(?![A-Za-z0-9])", re.IGNORECASE)

    # ----------------------------------------------------------- lookups ----
    def molecule(self, mid: str) -> dict:
        try:
            return self.molecules[mid]
        except KeyError:
            raise UnknownSubstance(mid)

    def model(self, mid: str) -> dict:
        """The force-field model a species is simulated with (or None)."""
        key = self.molecules[mid].get("force_model")
        return self.models[key] if key else None

    def element(self, symbol: str) -> dict:
        return self.elements[symbol]

    def resolve(self, name: str):
        """Name / formula / alias -> molecule id, or None."""
        return self._alias.get(normalise_text(name).strip().lower())

    def simulatable_ids(self):
        return [m for m in self.molecules if self.molecules[m].get("force_model") or self.molecules[m].get("dissociates_into")]

    def find_mentions(self, text: str):
        """Find substances in free text.

        Returns (molecule_mentions, element_mentions), each a list of
        dicts {id|symbol, quote, start, end} in order of appearance.  Elements
        are only reported when they are NOT already covered by a molecule
        (e.g. 'carbon' is an element mention; 'hydrogen' is the molecule H2).
        """
        t = normalise_text(text)
        mols, taken = [], []
        for m in self._alias_re.finditer(t):
            mols.append({"id": self._alias[m.group(1).lower()], "quote": text[m.start():m.end()],
                         "start": m.start(), "end": m.end()})
            taken.append((m.start(), m.end()))
        elems = []
        for name, el in self._element_by_name.items():
            for m in re.finditer(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", t, re.IGNORECASE):
                if any(s <= m.start() < e for s, e in taken):
                    continue
                elems.append({"symbol": el["symbol"], "quote": text[m.start():m.end()], "start": m.start(), "end": m.end()})
        mols.sort(key=lambda d: d["start"])
        elems.sort(key=lambda d: d["start"])
        return mols, elems

    def suggestions(self):
        return [self.molecules[m]["name"] for m in self.simulatable_ids() if self.molecules[m].get("force_model")]


_kb = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
