"""
nlp/extractor.py

NOTE (current role): the full language pipeline is now backend/agent/orchestrator.py,
which identifies substances in the chemical knowledge base and decides the physics.
This module is still used by it for the shared sentence rules (state words,
containers, negation, written-out numbers), and is kept as the substance-free
BASELINE reader that tests/test_extractor.py checks.

The original description follows.

The local language-processing component. It reads the user's plain-English
description and pulls out the same structured parameters the manual
controls collect. This is the ONLY part of the system that reads free
text, and it runs entirely on this machine -- there is no external AI
service, no API key, and no network call anywhere in this file.

Design choice, explained honestly: this is a rule-based (regex + keyword)
extractor, not a neural language model. It was chosen over running a small
local LLM (e.g. via llama.cpp) for this prototype because:
  - it needs no model download and no compiler toolchain to set up,
    which keeps the project runnable on any machine in a few minutes;
  - for a fixed, small vocabulary of simulation terms (particle counts,
    "liquid"/"gas"/"solid", "box"/"sphere", etc.) a few regular
    expressions cover the same ground a tiny model would, and every
    match is easy to explain line by line;
  - it runs entirely on this machine, with no network call and no
    external API -- which was the actual requirement.
A real small local language model is a natural upgrade path that drops in
at exactly this function's boundary -- extract_parameters() is the only
place the rest of the system talks to "the language step", so swapping
the implementation later doesn't touch anything else.

Three rules keep the matching honest, and each one exists because the
simpler version of it got a real sentence wrong:
  1. Whole words only. Plain substring matching found "sphere" inside
     "atmosphere" and turned "a gas in the atmosphere" into a spherical
     container.
  2. Negation is respected. "not solid but liquid" used to come back as
     solid, because "solid" appears first in the sentence.
  3. A number is only read when its own keyword is next to it. The old
     run-length pattern keyed off the bare word "for", so "...for 300
     particles" was read as a 300-time-unit run.
"""

import re

from backend.config.config_defaults import get_state_preset

# --- number words, so "two hundred particles" works as well as "200" ---
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

# Words that flip the meaning of a keyword that follows them. Only the few
# words before a match are checked (see _is_negated), so "not a solid, make
# it a liquid" skips "solid" but still accepts "liquid".
_NEGATION_WORDS = ("not", "no", "without", "never", "isn't", "aren't",
                   "instead", "rather", "avoid", "except")


def _whole_word_pattern(phrase: str) -> str:
    """Builds a regex that matches `phrase` as whole words, allowing a
    space or a hyphen between its parts ("hard sphere" also matches
    "hard-sphere"). \\b at both ends is what stops "sphere" from matching
    inside "atmosphere"."""
    parts = [re.escape(part) for part in phrase.split()]
    return r"\b" + r"[\s-]*".join(parts) + r"\b"


def _is_negated(text: str, match_start: int) -> bool:
    """True if a negation word appears in the handful of words directly
    before this match. Looking at a short window rather than the whole
    sentence keeps 'no container, make it a liquid' from marking the
    liquid as negated too."""
    window = text[max(0, match_start - 28):match_start]
    words = re.findall(r"[a-z']+", window)
    return any(word in _NEGATION_WORDS for word in words[-4:])


def _find_keyword(keyword_to_value: dict, text: str):
    """Returns (value, matched_phrase) for the EARLIEST keyword in the
    text that isn't negated, or (None, None) if none of them appear.

    Earliest-in-the-sentence is used rather than first-in-the-dictionary
    so the result depends on what the user wrote, not on the order the
    keywords happen to be listed here.
    """
    best = None
    for phrase, value in keyword_to_value.items():
        for match in re.finditer(_whole_word_pattern(phrase), text, re.IGNORECASE):
            if _is_negated(text, match.start()):
                continue
            if best is None or match.start() < best[0]:
                best = (match.start(), value, match.group(0))
            break  # only the first occurrence of each phrase matters
    if best is None:
        return None, None
    return best[1], best[2]


def _mentions_any(phrases, text: str):
    """Returns the first non-negated phrase from `phrases` that appears in
    the text as whole words, or None."""
    for phrase in phrases:
        for match in re.finditer(_whole_word_pattern(phrase), text, re.IGNORECASE):
            if not _is_negated(text, match.start()):
                return match.group(0)
            break
    return None


def _find_number(pattern: str, text: str):
    """Searches for a regex with one number-capturing group and returns
    (value, matched_text), or (None, None) if the pattern isn't found.

    The capturing group is deliberately loose ([\\d.]+) so a single regex
    reads naturally next to its keyword -- but that means it can also
    grab a sentence-ending period ("...temperature of 1.3." -> "1.3."),
    which float() would reject. Trimming a trailing "." here fixes that
    for every call site at once, rather than fiddling with each pattern.
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        raw = match.group(1).rstrip(".")
        try:
            return float(raw), match.group(0).strip()
        except ValueError:
            return None, None
    return None, None


def _words_to_number(phrase: str):
    """Turns a written number ("two hundred and fifty") into an int, or
    returns None if the phrase holds no number words. Handles the range
    this project actually needs -- particle counts up to a few hundred."""
    total = 0
    current = 0
    seen_any = False
    for word in re.findall(r"[a-z]+", phrase.lower()):
        if word == "and":
            continue
        if word == "hundred":
            current = (current or 1) * 100
            seen_any = True
        elif word in _NUMBER_WORDS:
            current += _NUMBER_WORDS[word]
            seen_any = True
        else:
            return None
    if not seen_any:
        return None
    return total + current


def _find_particle_count(text: str):
    """Reads a particle count written either as digits ("300 particles",
    "100 argon atoms") or as words ("two hundred atoms")."""
    countable = r"(?:particles?|atoms?|molecules?|points?)"

    # Digits, allowing a describing word or two before the noun.
    match = re.search(r"(\d+)\s*(?:[a-z]+\s+){0,2}?" + countable, text, re.IGNORECASE)
    if match:
        return int(match.group(1)), match.group(0).strip()

    # Written-out numbers. Rather than trying to capture the number words
    # with one regex -- which grabs whatever precedes them, because a
    # regex search always prefers the earliest start position -- this
    # finds the noun first and then reads backwards over the words just
    # before it, keeping the longest run that is a valid number.
    match = re.search(countable, text, re.IGNORECASE)
    if match:
        preceding = re.findall(r"[a-z]+", text[:match.start()].lower())
        for take in range(min(4, len(preceding)), 0, -1):
            phrase = " ".join(preceding[-take:])
            value = _words_to_number(phrase)
            if value:
                return value, f"{phrase} {match.group(0)}"
    return None, None


def extract_with_notes(text: str):
    """
    Reads the user's description and returns (params, notes):

      params -- a dict of simulation parameters, in the same shape the
                manual controls produce.
      notes  -- a list of plain-English lines saying what was matched and
                what fell back to a default. The interface prints these
                so the user can see exactly how their sentence was read,
                rather than having to trust it.

    Only fields that were actually mentioned (or implied by the detected
    state) differ from the base defaults -- everything else is left for
    the validator to fill in, exactly like a partially-completed form.
    """
    params = {}
    notes = []

    # --- which interaction model ---
    model, matched = _find_keyword({
        "hard sphere": "hard_sphere",
        "billiard": "hard_sphere",
        "elastic collision": "hard_sphere",
        "elastic collisions": "hard_sphere",
        "lennard jones": "lennard_jones",
    }, text)
    params["model"] = model or "lennard_jones"
    notes.append(f"model = {params['model']}"
                 + (f" (from \"{matched}\")" if matched else " (default -- no model named)"))

    # The model name "hard sphere" contains the word "sphere", which would
    # otherwise be read as a spherical container. Removing the model phrase
    # before looking for a container shape keeps the two from colliding.
    shape_text = re.sub(_whole_word_pattern("hard sphere"), " ", text, flags=re.IGNORECASE)

    # --- state of matter ---
    state, matched = _find_keyword({
        "solid": "solid",
        "crystal": "solid",
        "crystalline": "solid",
        "lattice": "solid",
        "frozen": "solid",
        "ice": "solid",
        "liquid": "liquid",
        "fluid": "liquid",
        "water like": "liquid",
        "molten": "liquid",
        "gas": "gas",
        "gaseous": "gas",
        "vapor": "gas",
        "vapour": "gas",
        "steam": "gas",
    }, text)
    params["state"] = state or "liquid"
    notes.append(f"state = {params['state']}"
                 + (f" (from \"{matched}\")" if matched else " (default -- no state named)"))

    # --- container: on/off, and shape ---
    off_phrase = _mentions_any(
        ["periodic", "no container", "open space", "unbounded", "infinite", "bulk"], text)
    # "without a container" reads as a negated container word, so the
    # container keyword below already refuses to match it.
    on_phrase = _mentions_any(
        ["box", "container", "cube", "cubic", "cuboid", "sphere", "spherical",
         "jar", "vessel", "tank", "flask", "walls", "walled", "enclosed", "inside"],
        shape_text)

    if off_phrase:
        params["container_enabled"] = False
        notes.append(f"container = off, periodic boundaries (from \"{off_phrase}\")")
    elif on_phrase:
        params["container_enabled"] = True
        notes.append(f"container = on (from \"{on_phrase}\")")
    else:
        params["container_enabled"] = False
        notes.append("container = off, periodic boundaries (default -- no container mentioned)")

    shape, matched = _find_keyword({
        "sphere": "sphere",
        "spherical": "sphere",
        "ball": "sphere",
        "round": "sphere",
        "flask": "sphere",
        "cube": "cuboid",
        "cubic": "cuboid",
        "cuboid": "cuboid",
        "box": "cuboid",
        "rectangular": "cuboid",
    }, shape_text)
    params["container_shape"] = shape or "cuboid"
    if params["container_enabled"]:
        notes.append(f"shape = {params['container_shape']}"
                     + (f" (from \"{matched}\")" if matched else " (default)"))

    # --- apply the state's default density/temperature (or speed) first,
    #     so numbers explicitly mentioned in the text can still override them ---
    preset = get_state_preset(params["model"], params["state"])
    params.update(preset)
    notes.append(f"{params['state']} preset applied: "
                 + ", ".join(f"{k} = {v}" for k, v in preset.items()))

    # --- explicit numbers, if the sentence gives them ---
    # Each pattern requires its own keyword right next to the number, so a
    # count can never be mistaken for a run length or a temperature.
    particle_count, matched = _find_particle_count(text)
    if particle_count is not None:
        params["particle_count"] = particle_count
        notes.append(f"particle count = {particle_count} (from \"{matched}\")")

    density, matched = _find_number(r"densit\w*\s*(?:of|=|:|at)?\s*([\d.]+)", text)
    if density is not None:
        params["density"] = density
        notes.append(f"density = {density} (from \"{matched}\")")

    temperature, matched = _find_number(
        r"(?:temperature|temp|\bT\*?)\s*(?:of|=|:|at)?\s*([\d.]+)", text)
    if temperature is not None:
        params["temperature"] = temperature
        notes.append(f"temperature = {temperature} (from \"{matched}\")")

    speed, matched = _find_number(r"(?:speed|velocity)\s*(?:of|=|:|at)?\s*([\d.]+)", text)
    if speed is not None:
        params["particle_speed"] = speed
        notes.append(f"particle speed = {speed} (from \"{matched}\")")

    timestep, matched = _find_number(
        r"(?:time\s*-?\s*step|timestep|\bdt\b)\s*(?:of|=|:)?\s*([\d.]+)", text)
    if timestep is not None:
        params["timestep"] = timestep
        notes.append(f"timestep = {timestep} (from \"{matched}\")")

    # The run length only counts when a time unit follows the number, or
    # when the phrase "total time" names it outright -- otherwise the word
    # "for" would swallow any number that happened to come after it.
    total_time, matched = _find_number(
        r"(?:for|over|during|run(?:ning)?\s+for|lasting)\s+(?:about\s+|roughly\s+)?"
        r"([\d.]+)\s*(?:reduced\s+)?(?:time\s+units?|units?)\b", text)
    if total_time is None:
        total_time, matched = _find_number(
            r"total\s+time\s*(?:of|=|:)?\s*([\d.]+)", text)
    if total_time is not None:
        params["total_time"] = total_time
        notes.append(f"run length = {total_time} (from \"{matched}\")")

    container_size, matched = _find_number(
        r"(?:container|box|sphere|edge|side)?\s*(?:size|length|width|diameter)"
        r"\s*(?:of|=|:)?\s*([\d.]+)", text)
    if container_size is None:
        container_size, matched = _find_number(r"([\d.]+)\s*(?:sigma|σ)\s*(?:box|container|cube)", text)
    if container_size is not None:
        params["container_size"] = container_size
        notes.append(f"container size = {container_size} (from \"{matched}\")")

    return params, notes


def extract_parameters(text: str) -> dict:
    """The parameter half of extract_with_notes(), for callers that only
    need the values. This is the function boundary the rest of the system
    talks to -- and the single point a real local language model would
    replace."""
    params, _ = extract_with_notes(text)
    return params
