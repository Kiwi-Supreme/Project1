"""
agent/quantities.py

Finds physical quantities WITH UNITS in a sentence ("300 K", "27 degrees C",
"1 atm", "5 nm", "10 ps", "0.8 g/cm3") and converts them to the units the
simulator works in.  A number without a unit is never read as a physical
quantity here (the caller may still treat it as a reduced-unit value).
"""

import re

from backend import units as U

NUM = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"


def _first(pattern, text, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m


def temperature_K(text):
    """-> (kelvin, quote) or (None, None)."""
    m = _first(NUM + r"\s*(?:°\s*|degrees?\s*|deg\.?\s*)?(kelvin|K)(?![A-Za-z])", text, 0) \
        or _first(NUM + r"\s*kelvin", text)
    if m:
        return U.to_kelvin(m.group(1), "k"), m.group(0).strip()
    m = _first(NUM + r"\s*(?:°\s*|degrees?\s*|deg\.?\s*)(celsius|fahrenheit|C|F)(?![A-Za-z])", text) \
        or _first(NUM + r"\s*(celsius|fahrenheit)", text)
    if m:
        return U.to_kelvin(m.group(1), m.group(2)), m.group(0).strip()
    m = _first(r"\b(room temperature|ambient temperature|standard temperature)\b", text)
    if m:
        return 298.15, m.group(0)
    m = _first(r"\bbody temperature\b", text)
    if m:
        return 310.15, m.group(0)
    return None, None


def pressure_atm(text):
    m = _first(NUM + r"\s*(atm|atmospheres?|bar|pa|kpa|mpa|gpa|torr|mmhg|psi)(?![A-Za-z])", text)
    if m:
        unit = m.group(2).lower()
        unit = "atm" if unit.startswith("atmosphere") else unit
        return U.to_atm(m.group(1), unit), m.group(0).strip()
    m = _first(r"\b(atmospheric pressure|standard pressure|ambient pressure|one atmosphere)\b", text)
    if m:
        return 1.0, m.group(0)
    return None, None


def duration_fs(text):
    m = _first(NUM + r"\s*(fs|ps|ns|femtoseconds?|picoseconds?|nanoseconds?)(?![A-Za-z])", text)
    if m and not re.search(r"time\s*-?\s*step\s*(?:of|=|:)?\s*$", text[:m.start()], re.IGNORECASE):
        return U.to_fs(m.group(1), m.group(2).lower()), m.group(0).strip()
    return None, None


def timestep_fs(text):
    m = _first(r"time\s*-?\s*step\s*(?:of|=|:|is)?\s*" + NUM + r"\s*(fs|ps|femtoseconds?|picoseconds?)", text)
    if m:
        return U.to_fs(m.group(1), m.group(2).lower()), m.group(0).strip()
    return None, None


def box_length_A(text):
    """A length that describes the container ('5 nm box', 'a cube of 30 Angstrom')."""
    for m in re.finditer(NUM + r"\s*(nm|nanometers?|nanometres?|angstroms?|Å|pm)(?![A-Za-z])", text, re.IGNORECASE):
        around = text[max(0, m.start() - 40):m.end() + 40].lower()
        if re.search(r"box|container|cell|side|edge|cube|cubic|wide|vessel|jar|flask|tank", around):
            return U.to_angstrom(m.group(1), m.group(2).lower().replace("Å", "å")), m.group(0).strip()
    return None, None


def density_g_cm3(text):
    m = _first(NUM + r"\s*(g\s*/\s*cm\s*\^?3|g\s*/\s*ml|g\s*/\s*cc|kg\s*/\s*m\s*\^?3)", text)
    if m:
        unit = re.sub(r"\s+", "", m.group(2).lower())
        return U.to_g_cm3(m.group(1), unit), m.group(0).strip()
    return None, None
