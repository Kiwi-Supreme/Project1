"""
Tests for backend/nlp/extractor.py -- the local, rule-based
natural-language parameter extractor.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.nlp.extractor import extract_parameters


def test_extracts_particle_count():
    params = extract_parameters("Simulate 300 particles in a box.")
    assert params["particle_count"] == 300


def test_detects_liquid_state_and_container():
    params = extract_parameters("Simulate particles moving inside a box as a liquid.")
    assert params["state"] == "liquid"
    assert params["container_enabled"] is True
    assert params["container_shape"] == "cuboid"


def test_detects_gas_state():
    params = extract_parameters("I want a gas of particles spreading through the space.")
    assert params["state"] == "gas"


def test_detects_solid_state():
    params = extract_parameters("Show me a solid crystal structure.")
    assert params["state"] == "solid"


def test_detects_sphere_container():
    params = extract_parameters("Put the particles inside a spherical container.")
    assert params["container_shape"] == "sphere"
    assert params["container_enabled"] is True


def test_detects_periodic_when_no_container_mentioned():
    params = extract_parameters("Run a Lennard-Jones liquid simulation.")
    assert params["container_enabled"] is False


def test_detects_hard_sphere_model():
    params = extract_parameters("Use a hard-sphere model with elastic collisions.")
    assert params["model"] == "hard_sphere"

def test_state_preset_fills_density_and_temperature():
    params = extract_parameters("Simulate a solid.")
    assert params["state"] == "solid"
    assert "density" in params and "temperature" in params


def test_explicit_numbers_override_state_preset():
    params = extract_parameters("Simulate a liquid with density of 0.95 and temperature of 1.3.")
    assert params["density"] == 0.95
    assert params["temperature"] == 1.3


# --- the specific sentences that used to be read wrongly ---

def test_sphere_inside_another_word_is_not_a_container():
    # "atmosphere" contains "sphere"; plain substring matching turned this
    # sentence into a spherical container.
    params = extract_parameters("Show me a gas of 300 atoms in the atmosphere.")
    assert params["container_enabled"] is False
    assert params["particle_count"] == 300


def test_cube_counts_as_a_container():
    params = extract_parameters("A solid crystal in a cube.")
    assert params["container_enabled"] is True
    assert params["container_shape"] == "cuboid"


def test_hard_sphere_model_does_not_imply_a_sphere_container():
    params = extract_parameters("Hard-sphere gas of 150 particles, no container.")
    assert params["model"] == "hard_sphere"
    assert params["container_enabled"] is False
    assert params["container_shape"] == "cuboid"


def test_negated_state_is_skipped():
    params = extract_parameters("Make it not solid but liquid.")
    assert params["state"] == "liquid"


def test_written_out_numbers():
    params = extract_parameters("A solid crystal of two hundred particles in a cube.")
    assert params["particle_count"] == 200


def test_count_survives_a_describing_word():
    params = extract_parameters("100 argon atoms as a gas.")
    assert params["particle_count"] == 100


def test_run_length_needs_a_time_unit():
    # "for" alone used to grab any number after it, so this sentence was
    # read as a 300-time-unit run.
    params = extract_parameters("Run a simulation for 300 particles.")
    assert "total_time" not in params
    assert params["particle_count"] == 300


def test_run_length_is_read_when_units_are_given():
    params = extract_parameters("Simulate a liquid for 4 time units.")
    assert params["total_time"] == 4.0


def test_container_size_from_a_natural_phrase():
    params = extract_parameters("A liquid in a spherical container of size 12.")
    assert params["container_size"] == 12.0
    assert params["container_shape"] == "sphere"


def test_notes_explain_every_decision():
    from backend.nlp.extractor import extract_with_notes
    params, notes = extract_with_notes("Simulate 250 particles inside a box as a liquid.")
    assert any("particle count = 250" in note for note in notes)
    assert any("state = liquid" in note for note in notes)
