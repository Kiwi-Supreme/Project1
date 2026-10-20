"""
Physics tests against the real molecular-dynamics engine (LAMMPS).  They check that the
simulation behaves according to known laws and that the chemistry in the knowledge base
actually changes what is simulated.  Skipped if LAMMPS is not installed; the slower
water / reaction tests run only with RUN_SLOW=1.
"""

import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from backend.agent.orchestrator import interpret
from backend.engine import runner
from backend.engine.plan import make_plan
from backend.knowledge.checks import domain_check
from backend.knowledge.kb import get_kb
from backend.units import KB, MVV2E
from backend.validation.schema import validate_params

try:
    runner.find_lammps()
    HAVE_LAMMPS = True
except runner.EngineRunError:
    HAVE_LAMMPS = False

pytestmark = pytest.mark.skipif(not HAVE_LAMMPS, reason="LAMMPS not installed (pip install lammps mpich)")
slow = pytest.mark.skipif(os.environ.get("RUN_SLOW") != "1", reason="slow; set RUN_SLOW=1")
kb = get_kb()


def _run(sentence, **override):
    r = interpret(sentence)
    assert not r["questions"], r["questions"]
    p = dict(r["params"])
    p.update(r["extras"]["sim"])
    p.update(seed=7, **override)
    params, errors = validate_params(p)
    assert errors is None, errors
    return params, runner.run_simulation(params)


def _val(report, prefix):
    return next(l for l in report if l.startswith(prefix))


def test_dilute_helium_obeys_the_ideal_gas_law_and_maxwell_boltzmann_speeds():
    params, res = _run("Simulate 250 helium atoms at 300 K and 1 atm for 10 ps")
    props = res["properties"]
    assert props["compressibility"] == pytest.approx(1.0, abs=0.03)          # PV = NkT
    assert props["temperature_K"] == pytest.approx(300.0, rel=0.06)
    assert props["pressure_atm"] == pytest.approx(1.0, rel=0.12)
    line = _val(res["report"], "Observed: mean speed")
    measured, theory = [float(x) for x in __import__("re").findall(r"(\d+) m/s", line)[:2]]
    assert measured == pytest.approx(theory, rel=0.04)                        # <v> = sqrt(8kT / pi m)


def test_total_energy_is_conserved_in_the_constant_energy_run():
    _, res = _run("Simulate 150 argon atoms as a liquid for 2 time units")
    totals = [e["total"] for e in res["energy"]]
    kinetic = np.mean([e["kinetic"] for e in res["energy"]])
    assert (max(totals) - min(totals)) / kinetic < 0.01                       # velocity-Verlet is symplectic


def test_particle_mass_is_used_lighter_atoms_are_faster_by_sqrt_of_mass_ratio():
    speeds = {}
    for name in ("helium", "argon"):
        _, res = _run(f"Simulate 100 {name} atoms at 300 K for 4 ps")
        speeds[name] = float(__import__("re").findall(r"(\d+) m/s", _val(res["report"], "Observed: mean speed"))[0])
    expected = math.sqrt(kb.molecule("argon")["molar_mass_g_mol"] / kb.molecule("helium")["molar_mass_g_mol"])
    assert speeds["helium"] / speeds["argon"] == pytest.approx(expected, rel=0.06)


def test_interaction_parameters_are_used_argon_condenses_where_helium_cannot():
    # the same real temperature, in each substance's own reduced units, is above vs below the critical point
    he, ar = kb.model("helium")["sites"][0]["epsilon_K"], kb.model("argon")["sites"][0]["epsilon_K"]
    assert 85.0 / ar < 1.31 < 85.0 / he
    _, res = _run("Simulate 200 argon atoms at 85 K as a liquid for 2 time units")
    assert res["properties"]["phase_measured"] == "liquid"
    _, res = _run("Simulate 200 helium atoms at 85 K for 2 time units")
    assert res["properties"]["phase_measured"] == "gas"


def test_liquid_argon_structure_has_twelve_neighbours_and_a_first_peak_near_1p1_sigma():
    _, res = _run("Simulate argon as a liquid for 2 time units")
    line = _val(res["report"], "Observed: radial distribution function")
    nums = [float(x) for x in __import__("re").findall(r"[-+]?\d+\.?\d*", line)]
    peak_r, neighbours = nums[0], nums[2]
    sigma = kb.model("argon")["sites"][0]["sigma_A"]
    assert peak_r / sigma == pytest.approx(1.1, abs=0.06)
    assert 10.0 < neighbours < 13.5


def test_walls_confine_particles_and_wall_pressure_matches_the_ideal_gas():
    params, res = _run("Simulate 200 argon atoms as a gas in a spherical container at 300 K and 1 atm for 10 ps")
    traj = res["trajectory"]
    centre = traj["box_length"] / 2
    for frame in traj["frames"][::25]:
        for x, y, z, _s in frame:
            assert math.dist((x, y, z), (centre,) * 3) <= centre + 1e-6        # nobody leaves the sphere
    assert res["properties"]["pressure_atm"] == pytest.approx(1.0, rel=0.2)


def test_temperature_sets_the_kinetic_energy_per_particle():
    _, res = _run("Simulate 150 helium atoms at 400 K for 3 ps")
    ke = np.mean([e["kinetic"] for e in res["energy"]])                         # in units of epsilon per particle
    eps_k = kb.model("helium")["sites"][0]["epsilon_K"]
    assert ke == pytest.approx(1.5 * 400.0 / eps_k, rel=0.07)                    # (3/2) k T per atom (equipartition)


def test_unstable_or_unphysical_requests_are_refused_by_the_domain_checks():
    r = interpret("Simulate 100 water molecules at 300 K")
    p = dict(r["params"]); p.update(r["extras"]["sim"]); p["timestep"] = 0.005
    params, errors = validate_params(p)
    plan = make_plan(params)
    errs, _ = domain_check(plan)
    assert any("too large for rigid water" in e for e in errs)


def test_hard_spheres_relax_to_maxwell_boltzmann_through_collisions():
    _, res = _run("Simulate argon using a hard-sphere model as a liquid")
    assert res["properties"]["engine"] == "hard-sphere"
    assert "fell from" in _val(res["report"], "Why: every particle started")


@slow
def test_water_structure_and_diffusion_match_tip3p_literature():
    _, res = _run("Simulate 100 water molecules at 300 K in a closed container")
    nums = [float(x) for x in __import__("re").findall(r"[-+]?\d+\.?\d*", _val(res["report"], "Observed: radial distribution function"))]
    assert 2.6 < nums[0] < 2.9                                                  # O-O hydrogen-bond distance
    d = float(__import__("re").search(r"D = ([\d.e+-]+)", _val(res["report"], "Observed: self-diffusion")).group(1))
    assert 2e-5 < d < 7e-5
    assert res["properties"]["temperature_K"] == pytest.approx(300, rel=0.05)


@slow
def test_ion_hydration_shells():
    _, res = _run("Simulate sodium chloride dissolved in water at 300 K")
    na = _val(res["report"], "Observed: Sodium ion hydration")
    assert 2.2 < float(__import__("re").search(r"peak at ([\d.]+) A", na).group(1)) < 2.6


@slow
def test_hydrogen_and_oxygen_form_water_by_reactive_md():
    _, res = _run("Simulate hydrogen and oxygen reacting at 5000 K")
    line = _val(res["report"], "Reaction: species count")
    assert "H2O 0→" in line and "H2O 0→0" not in line


# ------------------------------------------------------------ graphs and experiments
def test_a_run_returns_the_measured_property_graphs_with_captions():
    from backend.analysis import graphs  # noqa: F401  (module imports cleanly)
    _, res = _run("Simulate argon as a liquid for 2 time units")
    g = res["graphs"]
    assert {"thermo_T", "thermo_P", "speed", "rdf", "msd"} <= set(g)
    for key, graph in g.items():
        assert graph["caption"] and graph["series"] and all(len(s["x"]) == len(s["y"]) for s in graph["series"]), key
    assert any(v["label"].startswith("production") or v["label"] for v in g["thermo_T"]["vlines"])
    # the speed graph overlays the Maxwell-Boltzmann law and another mass at the same temperature
    labels = [s["label"] for s in g["speed"]["series"]]
    assert any("Maxwell" in l for l in labels) and any("helium" in l for l in labels)


def test_reactive_run_returns_a_species_graph():
    if os.environ.get("RUN_SLOW") != "1":
        pytest.skip("slow; set RUN_SLOW=1")
    _, res = _run("Simulate hydrogen and oxygen reacting at 5000 K")
    sp = res["graphs"]["species"]
    assert {s["label"] for s in sp["series"]} >= {"H2", "O2", "H2O"}


def _run_experiment(kind, substance, t_star):
    import time
    from backend import sweeps
    jid = sweeps.start(kind, [{"species": substance}], t_star)
    for _ in range(600):
        job = sweeps.get(jid)
        if job["status"] != "running":
            break
        time.sleep(0.5)
    assert job["status"] == "done", job["error"]
    return job["graphs"]


def test_boyle_experiment_shows_pressure_inversely_proportional_to_volume():
    g = _run_experiment("boyle", "helium", 29.0)["boyle"]
    pts = g["series"][0]
    pv = [x * y for x, y in zip(pts["x"], pts["y"])]
    assert max(pv) / min(pv) < 1.15                                           # P V constant (dilute gas)
    assert "Boyle" in g["caption"]


def test_gay_lussac_experiment_shows_pressure_proportional_to_temperature():
    g = _run_experiment("charles", "helium", 29.0)["charles"]
    pts = g["series"][0]
    ratio = [y / x for x, y in zip(pts["x"], pts["y"])]
    assert max(ratio) / min(ratio) < 1.08                                      # P / T constant


def test_experiments_refuse_substances_without_a_simple_model():
    from backend import sweeps
    jid = sweeps.start("eos", [{"species": "water"}], 3.9)
    import time
    for _ in range(40):
        job = sweeps.get(jid)
        if job["status"] != "running":
            break
        time.sleep(0.25)
    assert job["status"] == "error" and "simple atomic or molecular" in job["error"]
