"""
Tests for the chemical knowledge base (chemical_knowledge/*.json) and the code that
reads it (backend/knowledge/).  They check that the data is complete, that every
force-field entry cites a source, and that what the knowledge base says about a
substance is physically consistent.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from backend import units
from backend.knowledge import phase
from backend.knowledge.kb import get_kb

kb = get_kb()


def test_all_118_elements_are_present_with_core_properties():
    assert len(kb.elements) == 118
    he = kb.element("He")
    assert he["atomic_number"] == 2 and he["noble_gas"] is True and he["group"] == 18
    assert abs(he["atomic_weight_u"] - 4.0026) < 1e-3
    assert kb.element("O")["electronegativity_pauling"] > kb.element("H")["electronegativity_pauling"]


def test_every_simulatable_species_has_a_sourced_force_field():
    for mid, mol in kb.molecules.items():
        if mol.get("force_model"):
            model = kb.model(mid)
            assert model["source"].strip(), f"{mid}: force-field entry has no source"
            for site in model["sites"]:
                assert site["mass"] > 0
                assert site["sigma_A"] > 0


def test_lj_site_mass_equals_the_molecular_mass_in_the_knowledge_base():
    for mid, mol in kb.molecules.items():
        model = kb.model(mid)
        if model and model["type"] == "lj_sphere":
            assert abs(model["sites"][0]["mass"] - mol["molar_mass_g_mol"]) < 1e-3


def test_helium_is_a_non_polar_monatomic_noble_gas_with_weak_attraction():
    he = kb.molecule("helium")
    assert he["monatomic"] and he["category"] == "noble_gas_atom" and not he["polarity"]["polar"]
    assert he["intermolecular_forces"] == ["london_dispersion"]
    assert he["reactivity"]["class"] == "inert"
    site = kb.model("helium")["sites"][0]
    assert abs(site["sigma_A"] - 2.551) < 0.01 and abs(site["epsilon_K"] - 10.22) < 0.1
    # helium binds far more weakly than argon or xenon
    assert site["epsilon_K"] < kb.model("argon")["sites"][0]["epsilon_K"] < kb.model("xenon")["sites"][0]["epsilon_K"]


def test_water_is_polar_hydrogen_bonding_with_partial_charges_summing_to_zero():
    w = kb.molecule("water")
    assert w["polarity"]["polar"] and "hydrogen_bonding" in w["intermolecular_forces"]
    sites = kb.model("water")["sites"]
    assert abs(sites[0]["charge"] + 2 * sites[1]["charge"]) < 1e-9          # O + 2 H = 0


def test_co2_has_polar_bonds_but_no_net_dipole():
    co2 = kb.molecule("carbon_dioxide")
    assert not co2["polarity"]["polar"]
    assert co2["polarity"]["max_bond_electronegativity_difference"] > 0.4


def test_ions_carry_charge_and_have_ion_dipole_interactions():
    na, cl = kb.molecule("sodium_ion"), kb.molecule("chloride_ion")
    assert na["net_charge"] == 1 and cl["net_charge"] == -1
    assert "ion_dipole" in na["intermolecular_forces"]
    assert kb.model("sodium_ion")["sites"][0]["charge"] == 1.0


def test_hydrogen_combustion_enthalpy_is_computed_from_formation_enthalpies():
    rx = next(r for r in kb.interactions["reactions"] if r["equation"].startswith("2 H2"))
    assert rx["reaction_enthalpy_kJ"] == pytest.approx(-483.6, abs=0.5)
    assert rx["reaxff_supported"] is True


def test_nitrogen_is_not_covered_by_the_reactive_force_field():
    assert kb.molecule("nitrogen")["reactivity"]["reaxff_supported"] is False


def test_quantum_flag_is_set_for_the_light_species_only():
    assert kb.model("helium")["quantum_effects_significant"] is True
    assert kb.model("hydrogen")["quantum_effects_significant"] is True
    assert kb.model("argon")["quantum_effects_significant"] is False


def test_mentions_are_found_by_name_formula_and_unicode_formula():
    mols, _ = kb.find_mentions("Mix H₂O with Helium and CO2, then NaCl")
    assert [m["id"] for m in mols] == ["water", "helium", "carbon_dioxide", "sodium_chloride"]


def test_short_words_are_not_mistaken_for_symbols():
    mols, _ = kb.find_mentions("He said the argon is not here")
    assert [m["id"] for m in mols] == ["argon"]


def test_an_element_without_a_model_is_reported_as_element_only():
    mols, elems = kb.find_mentions("simulate carbon")
    assert mols == [] and elems[0]["symbol"] == "C"


# ------------------------------------------------------------------- phase logic
def test_phase_at_ordinary_conditions():
    assert phase.state_at(kb.molecule("helium"), 298.15, 1.0) == "gas"
    assert phase.state_at(kb.molecule("water"), 298.15, 1.0) == "liquid"
    assert phase.state_at(kb.molecule("water"), 400.0, 1.0) == "gas"
    assert phase.state_at(kb.molecule("water"), 250.0, 1.0) == "solid"
    assert phase.state_at(kb.molecule("argon"), 85.0, 1.0) == "liquid"
    assert phase.state_at(kb.molecule("argon"), 300.0, 100.0) == "supercritical"


def test_helium_does_not_freeze_at_one_atmosphere_but_does_under_pressure():
    he = kb.molecule("helium")
    assert phase.state_at(he, 1.0, 1.0) != "solid"
    assert phase.state_at(he, 1.0, 30.0) == "solid"


def test_densities_are_close_to_known_values():
    assert phase.mass_density_g_cm3(kb.molecule("water"), 298.15, 1.0, "liquid") == pytest.approx(0.997, abs=0.01)
    assert phase.mass_density_g_cm3(kb.molecule("argon"), 85.0, 1.0, "liquid") == pytest.approx(1.41, abs=0.03)
    # ideal gas helium at room conditions: 1.64e-4 g/cm3
    assert phase.mass_density_g_cm3(kb.molecule("helium"), 298.15, 1.0, "gas") == pytest.approx(1.64e-4, rel=0.02)


def test_every_preset_conditions_really_have_the_state_they_claim():
    for mid in kb.simulatable_ids():
        mol = kb.molecule(mid)
        if not mol.get("thermo"):
            continue
        for st in ("solid", "liquid", "gas"):
            tc = phase.typical_conditions(mol, st)
            if tc:
                assert phase.state_at(mol, *tc) == st, f"{mid}: preset for {st} is actually {phase.state_at(mol, *tc)}"


# ------------------------------------------------------------------------ units
def test_reduced_unit_conversions():
    ref = units.Reference(3.405, 119.8 * units.KB, 39.948)             # argon
    assert ref.tau_fs == pytest.approx(2156, rel=0.01)
    assert ref.T_to_star(300.0) == pytest.approx(2.504, abs=0.01)
    assert units.to_kelvin(27, "C") == pytest.approx(300.15)
    assert units.to_angstrom(5, "nm") == 50.0
    assert units.to_fs(10, "ps") == 10000.0
    he_lambda = units.thermal_de_broglie_A(4.0026, 298.15)
    assert he_lambda == pytest.approx(0.505, abs=0.01)
