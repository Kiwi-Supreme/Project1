"""
agent/llm.py

The optional language-model step.  A local model served by Ollama
(http://localhost:11434, nothing leaves the machine) reads the sentence and
returns a STRUCTURED draft: which substances, which quantities, with the exact
words of the sentence it took each from.

The model is an interpreter only.  It is never asked for, and never allowed to
supply, chemistry or physics:
  * every substance name must resolve in the chemical knowledge base,
  * every quantity must come with a unit and a `quote` that really occurs in
    the user's sentence (otherwise it is discarded),
  * the draft is then converted and range-checked by the same code path as
    the rule-based reading, so an invented value cannot reach the engine.

Enable with:   MD_LLM_MODEL=<ollama model name>   (and optionally MD_LLM_URL).
Without it -- or if the server is unreachable -- the rule-based reader is used.
"""

import json
import os
import urllib.request

from backend import units as U

SCHEMA = {
    "type": "object",
    "properties": {
        "substances": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "count": {"type": ["integer", "null"]}, "quote": {"type": "string"}},
            "required": ["name", "quote"]}},
        "temperature": {"type": ["object", "null"], "properties": {"value": {"type": "number"}, "unit": {"type": "string"}, "quote": {"type": "string"}}},
        "pressure": {"type": ["object", "null"], "properties": {"value": {"type": "number"}, "unit": {"type": "string"}, "quote": {"type": "string"}}},
        "duration": {"type": ["object", "null"], "properties": {"value": {"type": "number"}, "unit": {"type": "string"}, "quote": {"type": "string"}}},
        "box_length": {"type": ["object", "null"], "properties": {"value": {"type": "number"}, "unit": {"type": "string"}, "quote": {"type": "string"}}},
        "reactive": {"type": "boolean"},
    },
    "required": ["substances"],
}

SYSTEM = ("You convert a user's description of a molecular simulation into JSON. Copy only what the user wrote. "
          "For each substance give the name exactly as written, an integer count only if a number of particles is stated "
          "for it, and the quote. For temperature, pressure, duration and box_length give the number, its unit "
          "(K, C, atm, bar, ps, ns, nm, angstrom ...) and the quote. Set reactive=true only if the user asks for a chemical "
          "reaction. Do not add substances, numbers or chemistry that are not in the sentence. Use null when absent.")


def ollama_chat(text, model=None, url=None, timeout=25):
    """Ask the local model for a draft. Returns a dict or None if unavailable."""
    model = model or os.environ.get("MD_LLM_MODEL")
    if not model:
        return None
    url = (url or os.environ.get("MD_LLM_URL") or "http://localhost:11434").rstrip("/") + "/api/chat"
    body = {"model": model, "stream": False, "format": SCHEMA, "options": {"temperature": 0},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]}
    try:
        req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(json.loads(r.read())["message"]["content"])
    except Exception:
        return None


def _quote_ok(quote, text):
    return bool(quote) and quote.strip().lower() in text.lower()


def _qty(entry, text, convert):
    if not entry or entry.get("value") is None or not entry.get("unit") or not _quote_ok(entry.get("quote"), text):
        return None
    try:
        return convert(entry["value"], entry["unit"].strip().lower().replace("°", "")), entry["quote"]
    except Exception:
        return None


def guard(raw, text, kb):
    """Validate a raw model draft against the sentence and the knowledge base.
    Returns (draft, rejected) where draft contains only verified items."""
    draft = {"components": [], "temperature_K": None, "pressure_atm": None, "duration_fs": None,
             "box_A": None, "reactive": None}
    rejected = []
    if not isinstance(raw, dict):
        return draft, ["model returned no usable JSON"]
    for s in raw.get("substances") or []:
        mid = kb.resolve(s.get("name", "")) if isinstance(s, dict) else None
        if mid is None:
            rejected.append(f"substance '{s.get('name') if isinstance(s, dict) else s}' is not in the chemical knowledge base")
        elif not _quote_ok(s.get("quote"), text):
            rejected.append(f"substance '{s.get('name')}' is not supported by a quote from the sentence")
        else:
            cnt = s.get("count")
            draft["components"].append({"id": mid, "count": int(cnt) if isinstance(cnt, int) and cnt > 0 else None, "quote": s["quote"]})
    for key, conv, field in [("temperature", U.to_kelvin, "temperature_K"), ("pressure", U.to_atm, "pressure_atm"),
                             ("duration", U.to_fs, "duration_fs"), ("box_length", U.to_angstrom, "box_A")]:
        entry = raw.get(key)
        if entry:
            got = _qty(entry, text, conv)
            if got:
                draft[field] = got
            else:
                rejected.append(f"{key} was dropped (missing unit, unknown unit, or not quoted from the sentence)")
    if isinstance(raw.get("reactive"), bool):
        draft["reactive"] = raw["reactive"]
    return draft, rejected
