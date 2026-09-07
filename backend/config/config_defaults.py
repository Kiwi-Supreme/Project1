"""
config_defaults.py

The density/temperature (or particle-speed) values that make a Lennard-Jones
or Hard-Sphere simulation actually LOOK like a solid, a liquid, or a gas.

These are the single source of truth for "what does solid/liquid/gas mean" --
the frontend shows the same numbers when it applies a preset, and this file
is what actually gets sent to the C++ engine. Keeping them in one place
means the UI and the real simulation can never disagree about what
"liquid" means.
"""

# Lennard-Jones presets: density and temperature, in reduced (LJ) units.
LJ_STATE_PRESETS = {
    "solid": {"density": 1.0, "temperature": 0.2},
    "liquid": {"density": 0.8, "temperature": 1.0},
    "gas": {"density": 0.2, "temperature": 2.5},
}

# Hard-Sphere has no "temperature" -- particle speed plays the same role.
HARD_SPHERE_STATE_PRESETS = {
    "solid": {"particle_speed": 0.3},
    "liquid": {"particle_speed": 1.2},
    "gas": {"particle_speed": 2.4},
}


def get_state_preset(model: str, state: str) -> dict:
    """Returns the default density/temperature (or particle_speed) for a
    given model + state combination, so a request that only says
    'liquid' still has real numbers to run with."""
    if model == "hard_sphere":
        return HARD_SPHERE_STATE_PRESETS.get(state, HARD_SPHERE_STATE_PRESETS["liquid"])
    return LJ_STATE_PRESETS.get(state, LJ_STATE_PRESETS["liquid"])
