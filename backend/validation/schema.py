"""
validation/schema.py

Checks that a set of simulation parameters (whether they came from the
manual form or from the natural-language extractor) are physically
sensible BEFORE they're ever sent to the C++ engine. This is the one
place that decides "is this request even runnable" -- both the manual
and natural-language paths go through it, so there's a single source of
truth for what counts as valid.
"""

from pydantic import BaseModel, field_validator, model_validator


class Component(BaseModel):
    """One substance in the system.  `species` is a key of
    chemical_knowledge/molecules.json; `fraction` is its share of the particles."""
    species: str
    fraction: float = 1.0

    @field_validator("species")
    @classmethod
    def check_species(cls, v):
        from backend.knowledge.kb import get_kb
        kb = get_kb()
        if v not in kb.molecules:
            raise ValueError(f"unknown substance '{v}' (not in the chemical knowledge base)")
        return v

    @field_validator("fraction")
    @classmethod
    def check_fraction(cls, v):
        if not (v > 0):
            raise ValueError("component fraction must be positive")
        return v


class SimParams(BaseModel):
    # ---- Every numeric quantity below is in the interface's REDUCED units of the
    # reference substance (the first component): lengths in sigma, energies in
    # epsilon, T* = k_B T / epsilon, rho* = N sigma^3 / V, time in tau.  The knowledge
    # base supplies that substance's real sigma / epsilon / mass, so the same
    # numbers mean different real temperatures and lengths for different
    # substances (see backend/engine/plan.py).
    components: list[Component] | None = None   # None -> generic argon reference fluid
    reactive: bool = False                     # True -> reactive MD (ReaxFF), else classical
    # what to simulate
    model: str = "lennard_jones"          # "lennard_jones" or "hard_sphere"
    state: str = "liquid"                 # "solid", "liquid", or "gas"
    container_enabled: bool = True
    container_shape: str = "cuboid"       # "cuboid" or "sphere"

    # size and count
    particle_count: int = 200
    container_size: float = 10.0
    density: float = 0.8

    # energy / speed
    temperature: float = 1.0
    particle_speed: float = 1.2

    # time
    timestep: float = 0.001
    total_time: float = 5.0

    # Lennard-Jones potential parameters
    epsilon: float = 1.0
    sigma: float = 1.0
    cutoff: float | None = None           # None -> chosen automatically from the box size

    # Random seed for the starting arrangement. 0 means "seed from the
    # clock", so two runs of the same settings differ slightly -- which is
    # what a live demo wants. A fixed value makes a run exactly repeatable,
    # which is what the automated tests need.
    seed: int = 0

    @field_validator("model")
    @classmethod
    def check_model(cls, v):
        if v not in ("lennard_jones", "hard_sphere"):
            raise ValueError("model must be 'lennard_jones' or 'hard_sphere'")
        return v

    @field_validator("state")
    @classmethod
    def check_state(cls, v):
        if v not in ("solid", "liquid", "gas"):
            raise ValueError("state must be 'solid', 'liquid', or 'gas'")
        return v

    @field_validator("container_shape")
    @classmethod
    def check_shape(cls, v):
        if v not in ("cuboid", "sphere"):
            raise ValueError("container_shape must be 'cuboid' or 'sphere'")
        return v

    @field_validator("particle_count")
    @classmethod
    def check_particle_count(cls, v):
        if not (1 <= v <= 500):
            raise ValueError("particle_count must be between 1 and 500 for this prototype")
        return v

    @field_validator("density")
    @classmethod
    def check_density(cls, v):
        if not (1e-4 <= v <= 1.2):
            raise ValueError("density must be between 0.0001 and 1.2 (reduced units)")
        return v

    @field_validator("temperature")
    @classmethod
    def check_temperature(cls, v):
        if not (0.05 <= v <= 200.0):
            raise ValueError("temperature must be between 0.05 and 200 (reduced units, T* = k_B T / epsilon)")
        return v

    @field_validator("particle_speed")
    @classmethod
    def check_speed(cls, v):
        if not (0.05 <= v <= 20.0):
            raise ValueError("particle_speed must be between 0.05 and 20 (reduced units)")
        return v

    @field_validator("timestep")
    @classmethod
    def check_timestep(cls, v):
        if not (0.0001 <= v <= 0.005):
            raise ValueError("timestep must be between 0.0001 and 0.005 (velocity-Verlet stability bound)")
        return v

    @field_validator("total_time")
    @classmethod
    def check_total_time(cls, v):
        if not (0.1 <= v <= 20.0):
            raise ValueError("total_time must be between 0.1 and 20.0 reduced time units for this prototype")
        return v

    @field_validator("seed")
    @classmethod
    def check_seed(cls, v):
        if not (0 <= v <= 2147483647):
            raise ValueError("seed must be between 0 and 2147483647 (0 = random each run)")
        return v

    @field_validator("container_size")
    @classmethod
    def check_container_size(cls, v):
        if not (2.0 <= v <= 300.0):
            raise ValueError("container_size must be between 2.0 and 300 (reduced units)")
        return v

    @model_validator(mode="after")
    def check_cutoff_fits_box(self):
        """
        The minimum-image / no-self-interaction rule: a particle must
        never be able to interact with its own periodic or reflected
        image. That means the interaction cutoff has to be smaller than
        half the box size. If it isn't, the physics would silently
        double-count interactions -- so we reject the request instead.

        When no cutoff is given, the usual 2.5 sigma is used, shrunk if the box
        is small (but never below 1.5 sigma, where too much of the
        attraction would be cut off).
        """
        box_length = self.container_size if self.container_enabled else \
            (self.particle_count / self.density) ** (1.0 / 3.0)

        if self.cutoff is None:
            self.cutoff = round(min(2.5, 0.49 * box_length / self.sigma), 4)
            if self.cutoff < 1.5:
                raise ValueError(
                    f"the box ({box_length:.2f} sigma) is too small for this many particles: the interaction "
                    f"cutoff would have to be below 1.5 sigma and must stay smaller than half the box ({box_length / 2.0:.2f} sigma)")
            return self

        cutoff_distance = self.cutoff * self.sigma
        if cutoff_distance >= box_length / 2.0:
            raise ValueError(
                f"cutoff ({cutoff_distance:.2f}) must be smaller than half the box size "
                f"({box_length / 2.0:.2f}) -- otherwise a particle could interact with its own image"
            )
        return self


def validate_params(raw_params: dict):
    """
    Runs the checks above. Returns (params, None) if everything is valid,
    or (None, [list of error messages]) if not -- callers use this to
    decide whether it's safe to hand the request to the C++ engine.
    """
    try:
        params = SimParams(**raw_params)
        return params, None
    except Exception as exc:
        # pydantic bundles every failed check into one exception; pull out
        # a plain-English message for each one instead of the raw traceback.
        errors = []
        if hasattr(exc, "errors"):
            for e in exc.errors():
                errors.append(e.get("msg", str(e)))
        else:
            errors.append(str(exc))
        return None, errors
