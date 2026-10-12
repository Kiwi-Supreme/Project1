"""
Tests for the language layer (backend/agent/): sentence -> substances -> knowledge-base
lookup -> validated parameters, including the guard that stops a language model from
inventing substances or numbers.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend.agent import llm as llm_mod
from backend.agent.orchestrator import interpret
from backend.knowledge.kb import get_kb
from backend.validation.schema import validate_params

kb = get_kb()


def _valid(result):
    p = dict(result["params"])
    p.update(result["extras"]["sim"])
    params, errors = validate_params(p)
    assert errors is None, errors
    return params


def test_helium_at_room_temperature_uses_helium_properties():
    r = interpret("Simulate helium at room temperature.")
    assert r["questions"] == []
    assert r["extras"]["sim"]["components"][0]["species"] == "helium"
    params = _valid(r)
    # T* = 298.15 K / (epsilon/k of helium = 10.22 K)
    assert params.temperature == pytest.approx(298.15 / 10.22, rel=0.02)
    assert params.state == "gas"
    # 1 atm ideal-gas density in helium's reduced units: ~4.1e-4
    assert params.density == pytest.approx(4.1e-4, rel=0.05)
    assert any("room temperature" in n for n in r["notes"])


def test_different_substances_give_different_reduced_conditions_for_the_same_sentence():
    he = interpret("Simulate helium at 300 K")["params"]["temperature"]
    ar = interpret("Simulate argon at 300 K")["params"]["temperature"]
    # kT / epsilon is ~12x larger for helium (weaker attraction)
    assert he / ar == pytest.approx(kb.model("argon")["sites"][0]["epsilon_K"] / kb.model("helium")["sites"][0]["epsilon_K"], rel=0.02)


def test_water_in_a_closed_container_is_a_liquid_at_liquid_density():
    r = interpret("Simulate 100 water molecules at 300 K in a closed container and observe their movement over time.")
    p = r["params"]
    assert r["extras"]["sim"]["components"] == [{"species": "water", "fraction": 100.0}]
    assert p["particle_count"] == 100 and p["state"] == "liquid"
    assert p["density"] == pytest.approx(1.04, abs=0.03)                 # 0.997 g/cm3 in sigma(O)^-3
    _valid(r)


def test_units_are_converted_not_ignored():
    r = interpret("Simulate 50 argon atoms at 27 degrees C for 10 ps")
    # 27 C = 300.15 K
    assert any("300.15 K" in n for n in r["notes"])
    ref_tau = 2125.0
    assert r["params"]["total_time"] == pytest.approx(10000.0 / ref_tau, rel=0.02)


def test_explicit_box_and_particle_count_set_the_density():
    r = interpret("Simulate 100 argon atoms at 100 K in a 4 nm box")
    sigma = kb.model("argon")["sites"][0]["sigma_A"]
    assert r["params"]["density"] == pytest.approx(100 * sigma ** 3 / 40.0 ** 3, rel=0.01)


def test_salt_in_water_becomes_neutral_ion_pairs():
    r = interpret("Simulate sodium chloride dissolved in water at 300 K")
    comp = {c["species"]: c["fraction"] for c in r["extras"]["sim"]["components"]}
    assert comp["sodium_ion"] == comp["chloride_ion"] and "water" in comp
    _valid(r)


def test_salt_without_a_solvent_is_refused_with_a_question():
    r = interpret("Simulate sodium ions at 300 K")
    assert r["questions"] and "solvent" in r["questions"][0]


def test_unbalanced_ions_are_refused():
    r = interpret("Simulate 3 Na+ and 5 Cl- in water")
    assert r["questions"] and "neutral" in r["questions"][0]


def test_unknown_substance_is_never_replaced_by_a_guess():
    r = interpret("Simulate benzene at room temperature")
    assert r["params"] == {} and "benzene" in r["questions"][0]


def test_element_known_but_without_a_force_field_is_explained():
    r = interpret("Simulate carbon")
    assert r["params"] == {} and "no validated" in r["questions"][0] and "Carbon" in r["questions"][0]


def test_reaction_asks_for_temperature_unless_high_temperature_is_stated():
    assert interpret("Simulate hydrogen and oxygen reacting")["questions"]
    r = interpret("Simulate hydrogen and oxygen reacting at high temperature.")
    assert r["questions"] == [] and r["extras"]["sim"]["reactive"] is True
    counts = {c["species"]: c["fraction"] for c in r["extras"]["sim"]["components"]}
    assert counts["hydrogen"] == 2 * counts["oxygen"]                       # 2 H2 + O2 stoichiometry from the knowledge base
    assert any("accelerated kinetics" in n for n in r["notes"])


def test_reaction_with_an_unsupported_element_falls_back_to_non_reactive_md():
    r = interpret("Simulate hydrogen and nitrogen reacting at 5000 K")
    assert r["extras"]["sim"]["reactive"] is False
    assert any("NON-reactive" in n for n in r["notes"])


def test_solid_request_that_is_unphysical_is_flagged():
    r = interpret("Simulate solid helium at 300 K")
    assert any("is a gas" in n for n in r["notes"])


def test_state_presets_follow_the_substance():
    he = interpret("Simulate helium")["extras"]["presets"]["lennard_jones"]
    ar = interpret("Simulate argon")["extras"]["presets"]["lennard_jones"]
    assert he["liquid"]["temperature"] != ar["liquid"]["temperature"]


# ------------------------------------------------------------- LLM guard
SENTENCE = "Simulate 100 helium atoms at twenty degrees Celsius"


def test_llm_substance_must_exist_in_the_knowledge_base_and_be_quoted():
    raw = {"substances": [{"name": "unobtainium", "quote": "unobtainium"}, {"name": "helium", "quote": "helium"},
                          {"name": "argon", "quote": "argon in the sentence"}]}
    draft, rejected = llm_mod.guard(raw, SENTENCE, kb)
    assert [c["id"] for c in draft["components"]] == ["helium"]
    assert len(rejected) == 2


def test_llm_quantity_needs_a_real_quote_and_a_known_unit():
    raw = {"substances": [], "temperature": {"value": 20, "unit": "C", "quote": "twenty degrees Celsius"},
           "pressure": {"value": 5, "unit": "atm", "quote": "5 atm"},                 # quote not in sentence: hallucinated
           "duration": {"value": 5, "unit": "parsecs", "quote": "twenty"}}
    draft, rejected = llm_mod.guard(raw, SENTENCE, kb)
    assert draft["temperature_K"][0] == pytest.approx(293.15)
    assert draft["pressure_atm"] is None and draft["duration_fs"] is None
    assert len(rejected) == 2


def test_llm_fills_what_the_rules_missed_but_cannot_override_them():
    fake = lambda text: {"substances": [{"name": "helium", "quote": "helium"}],
                         "temperature": {"value": 20, "unit": "C", "quote": "twenty degrees Celsius"}}
    r = interpret(SENTENCE, llm=fake)
    assert any("293.15" in n for n in r["notes"])                                 # the model read 'twenty degrees Celsius'
    # an explicit number the rules found is kept even if the model disagrees
    fake2 = lambda text: {"substances": [], "temperature": {"value": 999, "unit": "K", "quote": "999 K"}}
    r2 = interpret("Simulate 100 helium atoms at 300 K", llm=fake2)
    assert any("300.00 K" in n for n in r2["notes"])


def test_a_broken_llm_does_not_break_the_pipeline():
    r = interpret("Simulate helium at room temperature", llm=lambda t: {"garbage": True})
    assert r["questions"] == [] and r["params"]
