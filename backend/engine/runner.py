"""
engine/runner.py

The bridge between the web backend and the molecular-dynamics engines.
For one simulation request this module:

  1. builds a Plan from the validated parameters and the chemical knowledge
     base (engine/plan.py),
  2. writes the engine's input files (engine/lammps_case.py),
  3. runs the engine as a subprocess,
  4. reads back the trajectory and thermodynamic log, analyses them
     (analysis/report.py) and returns them in the shape the interface expects.

Engines:
  LAMMPS      classical MD (Lennard-Jones, Coulomb/PPPM, SHAKE) and reactive MD
              (ReaxFF) -- the established open-source MD package (Sandia).
  md_engine   the project's own small C++ engine, used for the Hard-Sphere model.

Returned to the interface:  { trajectory, energy, run_seconds, report,
properties }.  Positions and times are given in the interface's reduced units
(sigma and tau of the reference substance); the `report` lines give the real
(kelvin / angstrom / picosecond) numbers.
"""

import csv
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import uuid

import numpy as np

from backend.analysis import report as rep
from backend.engine import lammps_case, lammps_parse
from backend.engine.plan import make_plan
from backend.knowledge import phase
from backend.knowledge.checks import domain_check
from backend.validation.schema import SimParams

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine_cpp")
RUNS_DIR = os.path.join(PROJECT_ROOT, "runs")
_ENGINE_CANDIDATES = ["md_engine.exe", "md_engine"]


class EngineRunError(Exception):
    """Raised when an engine can't be found, times out, or exits with an error."""
    pass


def find_lammps():
    """LAMMPS executable: $LAMMPS_BIN, else `lmp` on PATH, else the one installed with the pip package."""
    cands = [os.environ.get("LAMMPS_BIN")]
    for name in ("lmp", "lmp_serial", "lmp_mpi"):
        cands.append(shutil.which(name))
    cands.append(os.path.join(os.path.dirname(sys.executable), "lmp"))
    cands.append(os.path.join(sys.prefix, "bin", "lmp"))
    for c in cands:
        if c and os.path.isfile(c):
            return c
    raise EngineRunError("LAMMPS was not found. Install it with `pip install lammps mpich` (or set LAMMPS_BIN to the lmp executable).")


def _engine_env(lmp):
    """The pip LAMMPS wheel needs an MPI library; if `mpich` is installed in the same environment, point the loader at it."""
    env = dict(os.environ)
    libdirs = [os.path.join(sys.prefix, "lib"), os.path.join(os.path.dirname(os.path.realpath(lmp)), "..", "lib")]
    env["LD_LIBRARY_PATH"] = os.pathsep.join([d for d in libdirs if os.path.isdir(d)] + [env.get("LD_LIBRARY_PATH", "")])
    return env


def _find_md_engine():
    for name in _ENGINE_CANDIDATES:
        path = os.path.join(ENGINE_DIR, name)
        if os.path.isfile(path):
            return path
    raise EngineRunError("Hard-sphere engine not found. Build it first: run engine_cpp/build.sh.")


# ===================================================================== LAMMPS ====
def _run_lammps(plan, outdir, timeout):
    lmp = find_lammps()
    seed = plan.params.seed or random.randint(1, 2 ** 30)
    meta = lammps_case.build_case(plan, outdir, seed)
    if plan.engine == "reaxff":
        ff = lammps_case.find_reaxff_file()
        if not ff:
            raise EngineRunError("ReaxFF parameter file ffield.reax.cho not found (it ships with LAMMPS; set LAMMPS_POTENTIALS).")
        shutil.copy(ff, os.path.join(outdir, "ffield.reax.cho"))
    t0 = time.time()
    try:
        res = subprocess.run([lmp, "-in", "in.lammps", "-log", "log.lammps", "-screen", "none"], cwd=outdir,
                             capture_output=True, text=True, timeout=timeout, env=_engine_env(lmp))
    except subprocess.TimeoutExpired:
        raise EngineRunError(f"Simulation timed out after {timeout}s -- try fewer particles or a shorter run.")
    secs = time.time() - t0
    logp = os.path.join(outdir, "log.lammps")
    log = open(logp).read() if os.path.isfile(logp) else ""
    if res.returncode != 0:
        err = [l for l in (log + res.stdout + res.stderr).splitlines() if "ERROR" in l]
        detail = err[0] if err else (res.stderr.strip() or res.stdout.strip() or "no output")[:400]
        code = res.returncode & 0xFFFFFFFF
        hint = ""
        if code in (0xC0000135, 0xC000007B, 3221225781):
            hint = " (Windows could not load a DLL LAMMPS needs, usually the MPI runtime: install MS-MPI, or use the official LAMMPS installer)"
        raise EngineRunError(f"LAMMPS ({lmp}) exited with code {res.returncode}: {detail}{hint}")
    thermo = lammps_parse.parse_thermo(log)
    steps, data = lammps_parse.parse_dump(os.path.join(outdir, "traj.dump"))
    if not thermo or len(steps) == 0:
        raise EngineRunError("LAMMPS finished but produced no output.")
    species_rows = lammps_parse.parse_species(os.path.join(outdir, "species.out")) if plan.engine == "reaxff" else None
    return meta, thermo, steps, data, secs, species_rows


def _reduced_trajectory(plan, meta, steps, data):
    ref = plan.ref
    sig, tau = ref.sigma, ref.tau_fs
    pos = data[:, :, 2:5] / sig
    speed = np.linalg.norm(data[:, :, 8:11], axis=2) * tau / sig
    frames = np.concatenate([pos, speed[:, :, None]], axis=2)
    return {
        "model": plan.params.model, "state": plan.params.state,
        "container_enabled": not plan.periodic, "container_shape": plan.shape,
        "box_length": plan.box_A / sig, "sigma": 1.0, "particle_count": int(data.shape[1]),
        "dt": plan.dt_fs / tau, "dump_every": meta["every"],
        "reference": {"substance": plan.primary.mol["name"], "sigma_A": sig, "tau_fs": tau, "epsilon_over_k_K": ref.eps_over_k},
        "frames": np.round(frames, 4).tolist(),
    }


def _reduced_energy(plan, thermo):
    ref, N = plan.ref, plan.n_objects
    rows = []
    for k, r in enumerate(thermo):
        rows.append({"step": int(r["Step"]), "time": round((r["Step"] - thermo[0]["Step"]) * plan.dt_fs / ref.tau_fs, 6),
                     "potential": r["PotEng"] / N / ref.eps, "kinetic": r["KinEng"] / N / ref.eps,
                     "total": r["TotEng"] / N / ref.eps})
    return rows


# ================================================================= hard sphere ====
def _write_hs_config(plan, output_dir, config_path):
    p = plan.params
    lines = [f"model={p.model}", f"state={p.state}", f"container_enabled={'true' if p.container_enabled else 'false'}",
             f"container_shape={p.container_shape}", f"particle_count={p.particle_count}", f"container_size={p.container_size}",
             f"density={p.density}", f"temperature={p.temperature}", f"particle_speed={p.particle_speed}",
             f"timestep={p.timestep}", f"total_time={p.total_time}", f"epsilon={p.epsilon}", f"sigma={p.sigma}",
             f"cutoff={p.cutoff}", f"seed={p.seed}", f"output_dir={output_dir}"]
    with open(config_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _run_hard_sphere(plan, outdir, timeout):
    exe = _find_md_engine()
    cfg = os.path.join(outdir, "config.txt")
    _write_hs_config(plan, outdir, cfg)
    t0 = time.time()
    try:
        res = subprocess.run([exe, cfg], cwd=ENGINE_DIR, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise EngineRunError(f"Simulation timed out after {timeout}s -- try fewer particles or a shorter run.")
    secs = time.time() - t0
    if res.returncode != 0:
        raise EngineRunError(f"Simulation engine failed: {res.stderr.strip() or res.stdout.strip()}")
    with open(os.path.join(outdir, "trajectory.json")) as f:
        traj = json.load(f)
    with open(os.path.join(outdir, "energy.csv"), newline="") as f:
        energy = [{"step": int(r["step"]), "time": float(r["time"]), "potential": float(r["potential"]),
                   "kinetic": float(r["kinetic"]), "total": float(r["total"])} for r in csv.DictReader(f)]
    return traj, energy, secs


def _hs_report(plan, traj, energy):
    """Measured quantities and explanation for the hard-sphere model."""
    from scipy import stats
    ref = plan.ref
    fr = traj["frames"]
    sp0 = np.array([p[3] for p in fr[0]])
    sp1 = np.array([p[3] for p in fr[-1]])
    t_star = float(np.mean(sp1 ** 2) / 3.0)
    scale = np.sqrt(t_star)
    ks0 = stats.kstest(sp0, "maxwell", args=(0, scale)).statistic
    ks1 = stats.kstest(sp1, "maxwell", args=(0, scale)).statistic
    unit_v = ref.sigma / ref.tau_fs * 1e5           # reduced speed -> m/s
    pm = plan.primary.mol
    lines = rep.chemical_lines(plan)
    lines.append(f"Properties used: mass {pm['molar_mass_g_mol']:.4f} u and diameter sigma = {ref.sigma:.3f} A from the knowledge base set the "
                 f"length unit and the velocity unit ({unit_v:.0f} m/s per unit of reduced speed).")
    lines.append("Physics: hard spheres of diameter sigma move in straight lines and exchange momentum only in elastic collisions (no "
                 "attraction); all energy is kinetic, so the temperature is the mean kinetic energy per particle, T = m<v²>/3k.")
    lines.append(f"Simulation: {plan.n_objects} spheres, {'periodic box' if plan.periodic else plan.shape} {plan.box_A:.1f} A, initial speed "
                 f"{plan.params.particle_speed * unit_v:.0f} m/s for every particle (effective temperature {plan.T_K:.1f} K), "
                 f"{plan.total_fs / 1000:.1f} ps with the project's C++ collision engine.")
    kin = [e["kinetic"] for e in energy]
    lines.append(f"Observed: kinetic energy per particle stays at {np.mean(kin):.3f} epsilon (range {min(kin):.3f}–{max(kin):.3f}): elastic "
                 f"collisions conserve energy. Mean speed at the end {np.mean(sp1) * unit_v:.0f} m/s.")
    n_dens = plan.number_density_A3
    lam = 1.0 / (math.sqrt(2) * math.pi * ref.sigma ** 2 * n_dens)                    # mean free path, A
    if ks1 < 0.5 * ks0:
        lines.append(f"Why: every particle started with the SAME speed. Through collisions alone the speeds spread into the Maxwell\u2013Boltzmann "
                     f"distribution: Kolmogorov\u2013Smirnov distance to Maxwell\u2013Boltzmann fell from {ks0:.2f} (first frame) to {ks1:.2f} (last frame).")
    else:
        lines.append(f"Why: every particle started with the SAME speed and the speeds relax toward the Maxwell\u2013Boltzmann distribution only by "
                     f"collisions. Here the mean free path is {lam / 10:.1f} nm against a box of {plan.box_A / 10:.1f} nm, so few collisions happen "
                     f"and the distribution has barely relaxed (distance {ks0:.2f} \u2192 {ks1:.2f}). Raise the density to see it relax.")
    return lines, {"T_K": ref.T_from_star(t_star), "ks_start": float(ks0), "ks_end": float(ks1)}


# =================================================================== top level ====
def run_simulation(params: SimParams, timeout_seconds: int = 600) -> dict:
    plan = make_plan(params)
    errors, warnings = domain_check(plan)
    if errors:
        raise EngineRunError(" ".join(errors))
    run_id = uuid.uuid4().hex[:12]
    outdir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(outdir, exist_ok=True)
    pm = plan.primary.mol

    if plan.engine == "hard_sphere":
        traj, energy, secs = _run_hard_sphere(plan, outdir, timeout_seconds)
        traj["reference"] = {"substance": pm["name"], "sigma_A": plan.ref.sigma, "tau_fs": plan.ref.tau_fs,
                             "epsilon_over_k_K": plan.ref.eps_over_k}
        lines, res = _hs_report(plan, traj, energy)
        label = f"{pm['name']} · hard spheres"
        props = {"label": label, "temperature_K": res["T_K"], "engine": "hard-sphere"}
        return {"trajectory": traj, "energy": energy, "run_seconds": round(secs, 2),
                "report": [f"Warning: {w}" for w in warnings] + lines, "properties": props}

    meta, thermo, steps, data, secs, species_rows = _run_lammps(plan, outdir, timeout_seconds)
    res = rep.analyse(plan, meta, thermo, steps, data, species_rows)
    measured_phase = rep.diagnose_phase(plan, res)
    lines = [f"Warning: {w}" for w in warnings] + [f"Note: {n}" for n in plan.notes]
    lines += rep.explain(plan, res, measured_phase)
    if plan.engine == "reaxff":
        lines += rep.reactive_lines(plan, res)
    else:
        lines.append("Limits: classical molecular dynamics — bonds are fixed, so no chemical reactions occur; molecules are described "
                     "by the force field above, not by quantum mechanics.")
    traj = _reduced_trajectory(plan, meta, steps, data)
    energy = _reduced_energy(plan, thermo)
    label = f"{' + '.join(s.mol['name'] for s in plan.species)} · {measured_phase}"
    props = {"label": label, "temperature_K": res["T_K"], "pressure_atm": res["P_atm"], "compressibility": res["Z"],
             "phase_measured": measured_phase, "engine": "LAMMPS " + ("ReaxFF" if plan.engine == "reaxff" else "classical"),
             "density_star": res.get("density_star")}
    with open(os.path.join(outdir, "analysis.json"), "w") as f:
        json.dump({k: v for k, v in res.items() if k not in ("rdf",)} | {"phase": measured_phase}, f, default=str, indent=1)
    return {"trajectory": traj, "energy": energy, "run_seconds": round(secs, 2), "report": lines, "properties": props}
