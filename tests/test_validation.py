"""
Tests for backend/validation/schema.py -- the gatekeeper that decides
whether a set of parameters is allowed to reach the C++ engine.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.validation.schema import validate_params


def test_default_parameters_are_valid():
    params, errors = validate_params({})
    assert errors is None
    assert params.model == "lennard_jones"
    assert params.state == "liquid"


def test_particle_count_too_high_is_rejected():
    params, errors = validate_params({"particle_count": 50000})
    assert params is None
    assert errors and "particle_count" in errors[0]


def test_particle_count_too_low_is_rejected():
    params, errors = validate_params({"particle_count": 0})
    assert params is None
    assert errors is not None


def test_timestep_outside_stability_bound_is_rejected():
    params, errors = validate_params({"timestep": 0.05})
    assert params is None
    assert errors is not None


def test_cutoff_larger_than_half_box_is_rejected():
    # A tiny container with the default cutoff (2.5 sigma) can't fit the
    # minimum-image rule -- this should be rejected, not silently allowed.
    params, errors = validate_params({"container_enabled": True, "container_size": 3.0})
    assert params is None
    assert errors is not None
    assert any("cutoff" in e for e in errors)


def test_valid_sphere_container_is_accepted():
    params, errors = validate_params({
        "container_enabled": True,
        "container_shape": "sphere",
        "container_size": 12.0,
        "particle_count": 100,
    })
    assert errors is None
    assert params.container_shape == "sphere"


def test_unknown_model_is_rejected():
    params, errors = validate_params({"model": "quantum_magic"})
    assert params is None
    assert errors is not None


def test_periodic_mode_sizes_box_from_density():
    # container_enabled=False means the cutoff check must use the
    # density-derived box length instead of container_size.
    params, errors = validate_params({"container_enabled": False, "density": 1.2, "particle_count": 10})
    assert errors is not None  # box from N=10, density=1.2 is tiny -> cutoff won't fit
