"""
engine/plan.py

Turns validated interface parameters (reduced units of the reference substance)
into a fully specified, real-unit SIMULATION PLAN, using the chemical
knowledge base for every substance-specific number.

    SimParams (reduced)  +  chemical_knowledge/*.json
            |
            v
    Plan:  which species and how many of each, their masses, sigma / epsilon /
           charges, box size in angstrom, temperature in kelvin, time step in fs,
           number of steps, which engine and which physical model.

This is the step that makes the substance matter: change the substance and
the mass, the Lennard-Jones sigma and epsilon, the charges, the length of
tau, the real temperature and box all change with it.
"""

from dataclasses import dataclass, field

from backend.knowledge.kb import get_kb
from backend.units import KB, Reference, thermal_de_broglie_A

# Measured throughput of the engine (atom-steps per second) on a laptop-class
# CPU; used only to warn about / refuse runs that would take too long.
RATE_LJ = 1.0e6
RATE_CHARGED = 2.0e5
RATE_REAXFF = 2.0e4
REAXFF_DT_FS = 0.25
MAX_REAXFF_ATOMS = 150
MAX_REAXFF_STEPS = 40000
MAX_SECONDS = 480


@dataclass
class Species:
    id: str
    mol: dict
    model: dict          # entry of force_parameters.json (or None)
    count: int           # number of molecules / ions / atoms of this species

    @property
    def n_sites(self):
        # a rigid water molecule is 3 atoms (its model lists the two distinct SITE types, O and H)
        return len(self.mol["structure"]["atoms"]) if self.model and self.model["type"] == "rigid_molecule_tip3p" else 1

    @property
    def charge_total(self):
        return self.mol.get("net_charge", 0) * self.count


@dataclass
class Plan:
    params: object
    species: list
    primary: Species
    ref: Reference
    engine: str                      # hard_sphere | lj | charged | reaxff
    T_K: float
    box_A: float
    periodic: bool
    shape: str
    dt_fs: float
    total_fs: float
    steps: int
    n_objects: int
    n_atoms: int
    number_density_A3: float
    reactive_requested: bool = False
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def tau_fs(self):
        return self.ref.tau_fs

    @property
    def has_charges(self):
        return any(s.charge_total != 0 or s.mol["id"] == "water" for s in self.species)

    def estimated_seconds(self):
        rate = {"lj": RATE_LJ, "charged": RATE_CHARGED, "reaxff": RATE_REAXFF, "hard_sphere": 5e5}[self.engine]
        extra = 1.5 if self.engine != "hard_sphere" else 1.0     # equilibration + minimisation
        return self.n_atoms * self.steps * extra / rate


def reference_for(species):
    """Reduced-unit reference (sigma, epsilon, mass) of a species."""
    model = species.model
    site = model["sites"][0]
    eps = site.get("epsilon_kcal_mol")
    mass = species.mol["molar_mass_g_mol"]
    return Reference(site["sigma_A"], eps, mass)


def allocate_counts(components, total):
    """Split `total` objects among components by fraction (largest remainder,
    at least one of each), then repair ionic charge balance."""
    kb = get_kb()
    fr = [c.fraction for c in components]
    s = sum(fr)
    raw = [total * f / s for f in fr]
    counts = [max(1, int(r)) for r in raw]
    while sum(counts) < total:
        i = max(range(len(raw)), key=lambda k: raw[k] - counts[k])
        counts[i] += 1
    while sum(counts) > total and max(counts) > 1:
        counts[counts.index(max(counts))] -= 1
    # charge balance: ions are only created in neutral combinations
    charges = [kb.molecule(c.species).get("net_charge", 0) for c in components]
    net = sum(q * n for q, n in zip(charges, counts))
    guard = 0
    while net != 0 and guard < 50:
        guard += 1
        sign = 1 if net > 0 else -1
        idx = [i for i, q in enumerate(charges) if q * sign > 0 and counts[i] > 1]
        if not idx:
            break
        i = idx[0]
        counts[i] -= 1
        counts[0] += 1                       # freed object goes to the main (first) component
        net -= charges[i] * 1
    return counts


def make_plan(params) -> Plan:
    kb = get_kb()
    comps = params.components or []
    if not comps:
        from backend.validation.schema import Component
        comps = [Component(species="argon", fraction=1.0)]
    notes, warnings, errors = [], [], []

    counts = allocate_counts(comps, params.particle_count)
    species = [Species(c.species, kb.molecule(c.species), kb.model(c.species), n) for c, n in zip(comps, counts)]

    for s in species:
        if s.model is None:
            errors.append(f"'{s.mol['name']}' is in the knowledge base but has no validated force-field model, so it cannot be simulated. "
                          f"Supported: {', '.join(kb.suggestions())}.")
    if errors:
        # minimal plan so callers can still report errors
        primary = species[0]
        return Plan(params, species, primary, Reference(1, 1, 1), "lj", 0, 0, True, "cuboid", 0, 0, 0, 0, 0, 0, errors=errors)

    primary = next((s for s in species if s.model["type"] in ("lj_sphere", "rigid_molecule_tip3p")), species[0])
    ref = reference_for(primary)

    # ---- which physical model / engine ------------------------------------
    reaxff_ok = all(s.mol["reactivity"].get("reaxff_supported") for s in species) and len(species) >= 2
    reactive = bool(params.reactive)
    if reactive and not reaxff_ok:
        warnings.append("Reactive chemistry was requested, but the reactive force field (ReaxFF CHO) does not cover every "
                        "element involved or fewer than two substances were given: running NON-reactive molecular dynamics "
                        "(bonds cannot break or form).")
        reactive = False
    charged = any(s.charge_total != 0 or s.model["type"] == "rigid_molecule_tip3p" for s in species)
    if params.model == "hard_sphere":
        engine = "hard_sphere"
    elif reactive:
        engine = "reaxff"
    elif charged:
        engine = "charged"
    else:
        engine = "lj"

    n_obj = sum(s.count for s in species)
    n_atoms = sum(s.count * (len(s.mol["structure"]["atoms"]) if engine == "reaxff" else s.n_sites) for s in species)

    # ---- geometry -----------------------------------------------------------
    periodic = not params.container_enabled
    shape = params.container_shape
    if engine in ("charged", "reaxff") and not periodic:
        warnings.append("Walls are not modelled for water / ions / reactive systems (no validated wall-solvent model): using periodic boundaries.")
        periodic = True
    if periodic:
        box = ref.sigma * (n_obj / params.density) ** (1.0 / 3.0)
    else:
        box = ref.sigma * params.container_size
    volume = box ** 3 if (periodic or shape == "cuboid") else (4.0 / 3.0) * 3.14159265 * (box / 2) ** 3

    # ---- temperature / time -----------------------------------------------------
    if engine == "hard_sphere":
        T_K = ref.T_from_star(params.particle_speed ** 2 / 3.0)     # kinetic temperature of the starting speed
    else:
        T_K = ref.T_from_star(params.temperature)
    if engine == "reaxff":
        dt_fs = REAXFF_DT_FS
        notes.append(f"Reactive force fields need a very small time step: dt fixed at {REAXFF_DT_FS} fs.")
    else:
        dt_fs = params.timestep * ref.tau_fs
    total_fs = params.total_time * ref.tau_fs
    steps = max(1, int(round(total_fs / dt_fs)))

    return Plan(params=params, species=species, primary=primary, ref=ref, engine=engine, T_K=T_K, box_A=box,
                periodic=periodic, shape=shape, dt_fs=dt_fs, total_fs=total_fs, steps=steps, n_objects=n_obj,
                n_atoms=n_atoms, number_density_A3=n_obj / volume, reactive_requested=bool(params.reactive),
                notes=notes, warnings=warnings, errors=errors)
