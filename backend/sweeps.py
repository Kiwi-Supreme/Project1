"""
sweeps.py  --  "virtual experiments": several simulations in a row, one quantity varied.

Each experiment runs the same molecular-dynamics engine used for a single run, once
per point, and plots a measured property against the varied one together with the
theory it should be compared with:

  eos         pressure vs density at fixed T   vs ideal gas and van der Waals
  boyle       pressure vs volume at fixed T    (P V = constant)
  charles     pressure vs temperature at fixed volume (Gay-Lussac / Charles)
  heating     energy and diffusion vs temperature of a heated crystal (melting)
              -> also gives the heat capacity (13)
  arrhenius   ln D vs 1/T of a liquid, activation energy of diffusion

The substance, and for some experiments the temperature, come from the description
the user last ran.  Everything substance-specific (sigma, epsilon, mass, critical
constants, saturated liquid density) is read from the chemical knowledge base.

Jobs run in a background thread; the interface polls for progress.
"""

import math
import threading
import uuid

import numpy as np

from backend.engine.runner import EngineRunError, run_simulation
from backend.knowledge import phase
from backend.knowledge.kb import get_kb
from backend.units import KB, NA, Reference
from backend.validation.schema import validate_params

ATM_A3 = 1.4583e-5          # 1 atm * A^3 * N_A, in kcal/mol
R_GAS = 8.314462618         # J/(mol K)
JOBS = {}
_LOCK = threading.Lock()

LABELS = {"eos": "Equation of state", "boyle": "Boyle's law", "charles": "Gay-Lussac / Charles's law",
          "heating": "Heating curve", "heatcap": "Heat capacity", "arrhenius": "Diffusion vs temperature"}


class SweepError(Exception):
    pass


def _ref(kb, mid):
    site = kb.model(mid)["sites"][0]
    return Reference(site["sigma_A"], site["epsilon_kcal_mol"], kb.molecule(mid)["molar_mass_g_mol"])


def _pick(kb, components, kind):
    """The single substance an experiment runs on."""
    ids = [c.get("species") for c in (components or [])] or ["argon"]
    if kind == "arrhenius" and "water" in ids:
        return "water"
    for i in ids:
        m = kb.model(i)
        if m and m["type"] == "lj_sphere":
            return i
    raise SweepError("This experiment needs a simple atomic or molecular substance (e.g. helium, argon, nitrogen, methane). "
                     "For water use 'Diffusion vs temperature'.")


def _run(mid, ref, T_K, n_A3, N, state, total_tau, seed=3):
    rho = n_A3 * ref.sigma ** 3
    if not (1e-4 <= rho <= 1.2):
        raise SweepError(f"density rho* = {rho:.3g} outside the supported range 0.0001-1.2")
    t_star = ref.T_to_star(T_K)
    if not (0.05 <= t_star <= 200):
        raise SweepError(f"temperature T* = {t_star:.3g} outside the supported range")
    params, errors = validate_params({
        "components": [{"species": mid, "fraction": 1.0}], "particle_count": N, "density": rho, "temperature": t_star,
        "state": state, "container_enabled": False, "timestep": min(max(2.0 / ref.tau_fs, 1e-4), 5e-3),
        "total_time": total_tau, "seed": seed})
    if errors:
        raise SweepError("; ".join(errors))
    return run_simulation(params)["scalars"]


# ----------------------------------------------------------------------- the experiments
def _vdw_pressure_atm(mol, rho_g_cm3):
    th = mol["thermo"]
    Tc, Pc = th["critical_T_K"], th["critical_P_atm"] * 101325.0
    a = 27 * R_GAS ** 2 * Tc ** 2 / (64 * Pc)
    b = R_GAS * Tc / (8 * Pc)
    return a, b


def exp_eos(kb, mid, ref, t_star, job):
    mol = kb.molecule(mid)
    T = ref.T_from_star(t_star)
    rhos = [0.02, 0.05, 0.1, 0.2, 0.3, 0.45, 0.6]
    job["total"] = len(rhos)
    pts = []
    for r in rhos:
        s = _run(mid, ref, T, r / ref.sigma ** 3, 200, "gas" if r <= 0.15 else "liquid", 3.0)
        g = r / ref.sigma ** 3 * mol["molar_mass_g_mol"] / NA * 1e24
        pts.append((g, s["P_atm"], s["P_err"], s["Z"]))
        job["done"] += 1
    g = np.array([p[0] for p in pts])
    grid = np.linspace(g.min() * 0.8, g.max() * 1.05, 50)
    n = grid / mol["molar_mass_g_mol"] * NA * 1e-24                      # per A^3
    ideal = n * KB * T / ATM_A3
    a, b = _vdw_pressure_atm(mol, 0)
    vm = mol["molar_mass_g_mol"] / grid * 1e-6                          # m^3/mol
    ok = vm > b * 1.02
    vdw = (R_GAS * T / (vm - b) - a / vm ** 2) / 101325.0
    series = [{"label": "simulation (error bars: block s.e.)", "kind": "points", "x": [round(float(p[0]), 5) for p in pts],
               "y": [round(float(p[1]), 3) for p in pts], "yerr": [round(float(p[2]), 3) for p in pts]},
              {"label": "ideal gas  P = n k T", "kind": "line", "dash": True, "x": [round(float(x), 5) for x in grid], "y": [round(float(y), 3) for y in ideal]},
              {"label": "van der Waals (a, b from critical constants)", "kind": "line", "x": [round(float(x), 5) for x in grid[ok]],
               "y": [round(float(y), 3) for y in vdw[ok]]}]
    cap = (f"{mol['name']} at {T:.0f} K, 200 particles per point. At low density the simulated pressure follows the ideal-gas line (Z = {pts[0][3]:.2f} at the "
           f"lowest density); as density rises, intermolecular forces bend it away: Z = {pts[-1][3]:.2f} at the highest. The van der Waals curve uses only the "
           f"substance's critical constants from the knowledge base - it captures the trend but is not exact.")
    return {"eos": _graphd("Equation of state: pressure vs density", "density (g/cm3)", "pressure (atm)", series, cap)}


def exp_boyle(kb, mid, ref, t_star, job):
    mol = kb.molecule(mid)
    T = ref.T_from_star(t_star)
    rhos = [0.005, 0.01, 0.02, 0.04, 0.07, 0.1]
    N = 200
    job["total"] = len(rhos)
    V, P, E = [], [], []
    for r in rhos:
        s = _run(mid, ref, T, r / ref.sigma ** 3, N, "gas", 3.0)
        V.append(N / (r / ref.sigma ** 3) / 1000.0)                        # nm^3
        P.append(s["P_atm"]); E.append(s["P_err"])
        job["done"] += 1
    V, P = np.array(V), np.array(P)
    c = float(np.mean(P * V))
    grid = np.linspace(V.min() * 0.9, V.max() * 1.05, 50)
    spread = 100 * (P * V).std() / c
    series = [{"label": "simulation", "kind": "points", "x": [round(float(x), 3) for x in V], "y": [round(float(y), 4) for y in P], "yerr": [round(float(e), 4) for e in E]},
              {"label": f"Boyle's law  P V = {c:.3g} atm nm3", "kind": "line", "x": [round(float(x), 3) for x in grid], "y": [round(c / float(x), 4) for x in grid]},
              {"label": "ideal gas N k T / V", "kind": "line", "dash": True, "x": [round(float(x), 3) for x in grid],
               "y": [round(N * KB * T / (float(x) * 1000.0 * ATM_A3), 4) for x in grid]}]
    cap = (f"{mol['name']} gas at {T:.0f} K, N = {N}: pressure against volume. Pressure rises as the box shrinks because particles hit the walls more often; "
           f"P x V is constant to within {spread:.1f}% (Boyle's law), and equals N k T = {N * KB * T / ATM_A3 / 1000.0:.3g} atm nm3 for an ideal gas.")
    return {"boyle": _graphd("Boyle's law: pressure vs volume (constant T)", "volume (nm3)", "pressure (atm)", series, cap)}


def exp_charles(kb, mid, ref, t_star, job):
    mol = kb.molecule(mid)
    T0 = ref.T_from_star(t_star)
    facs = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
    facs = [f for f in facs if 0.05 <= ref.T_to_star(T0 * f) <= 200]
    N, r = 200, 0.05
    job["total"] = len(facs)
    T, P, E, Zs = [], [], [], []
    for f in facs:
        s = _run(mid, ref, T0 * f, r / ref.sigma ** 3, N, "gas", 3.0)
        T.append(s["T_K"]); P.append(s["P_atm"]); E.append(s["P_err"]); Zs.append(s["Z"])
        job["done"] += 1
    T, P = np.array(T), np.array(P)
    k = float(np.sum(P * T) / np.sum(T * T))
    n = r / ref.sigma ** 3
    grid = np.linspace(0, T.max() * 1.05, 20)
    series = [{"label": "simulation", "kind": "points", "x": [round(float(x), 2) for x in T], "y": [round(float(y), 4) for y in P], "yerr": [round(float(e), 4) for e in E]},
              {"label": f"P = {k:.4g} T  (through the origin)", "kind": "line", "x": [round(float(x), 2) for x in grid], "y": [round(k * float(x), 4) for x in grid]},
              {"label": "ideal gas n k T", "kind": "line", "dash": True, "x": [round(float(x), 2) for x in grid], "y": [round(n * KB * float(x) / ATM_A3, 4) for x in grid]}]
    cap = (f"{mol['name']} at constant volume (rho* = {r}): pressure is proportional to absolute temperature (P/T = {k:.4g} atm/K, ideal gas {n * KB / ATM_A3:.4g}) - "
           "Gay-Lussac's law. Together with Boyle's law this is the ideal-gas law PV = NkT; at constant pressure the same law gives Charles's law, V proportional to T. "
           "The cause is microscopic: kinetic energy per particle is (3/2)kT, so hotter particles hit the walls harder and more often."
           + (f" At the lowest temperature ({T[0]:.0f} K) Z = {Zs[0]:.2f}: attraction between particles lowers the pressure below the ideal value, so the law holds best when kT is much larger than the attraction." if Zs[0] < 0.95 else ""))
    return {"charles": _graphd("Gay-Lussac / Charles: pressure vs temperature (constant volume)", "temperature (K)", "pressure (atm)", series, cap)}


def exp_heating(kb, mid, ref, t_star, job):
    mol = kb.molecule(mid)
    tstars = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    job["total"] = len(tstars)
    rows = []
    for ts in tstars:
        s = _run(mid, ref, ref.T_from_star(ts), 0.95 / ref.sigma ** 3, 256, "solid", 4.0)
        rows.append(s)
        job["done"] += 1
    T = np.array([s["T_K"] for s in rows])
    U = np.array([s["U_per_particle_kcal_mol"] for s in rows])
    D = np.maximum(np.array([s["D_cm2_s"] or 0.0 for s in rows]), 0.0)         # a fitted slope of ~0 can come out slightly negative
    Dstar = np.array([s["D_star"] or 0.0 for s in rows])
    melt = None
    for i in range(1, len(rows)):
        if Dstar[i] > 0.005 >= Dstar[i - 1]:
            melt = 0.5 * (T[i] + T[i - 1])
            break
    vl = [{"x": round(float(melt), 1), "label": f"melting ~{melt:.0f} K"}] if melt else []
    capm = (f"Diffusion switches on between {T[i - 1]:.0f} and {T[i]:.0f} K: the lattice melts (at this fixed density; a perfect crystal can be "
            "superheated, so this slightly overestimates the true melting point)." if melt else "No melting seen in this temperature range.")
    g_u = _graphd(f"Heating curve: energy vs temperature ({mol['name']} crystal)", "temperature (K)", "total energy per particle (kcal/mol)",
                  [{"label": "simulation", "kind": "points", "x": _rl(T, 2), "y": _rl(U, 4)}, {"label": "", "kind": "line", "x": _rl(T, 2), "y": _rl(U, 4)}],
                  "Total (potential + kinetic) energy per particle as the crystal is heated at constant volume. The slope is the heat capacity; "
                  "a bend or step marks melting. " + capm, vlines=vl)
    g_d = _graphd(f"Heating curve: diffusion vs temperature", "temperature (K)", "self-diffusion coefficient D (cm2/s)",
                  [{"label": "simulation", "kind": "points", "x": _rl(T, 2), "y": [float(x) for x in D]}, {"label": "", "kind": "line", "x": _rl(T, 2), "y": [float(x) for x in D]}],
                  "A solid has D ~ 0 (atoms only vibrate); a liquid has D > 0 (atoms exchange places). The sudden rise is the melting transition. " + capm, vlines=vl)
    # heat capacity: derivative of U(T), and fluctuation formula
    kk = KB
    mid_T = 0.5 * (T[1:] + T[:-1])
    cv_d = (U[1:] - U[:-1]) / (T[1:] - T[:-1]) / kk
    cf = [(float(T[i]), s["Cv_fluct_over_Nk"]) for i, s in enumerate(rows) if s.get("Cv_fluct_over_Nk")]
    series = [{"label": "from dU/dT (slope of the heating curve)", "kind": "points", "x": _rl(mid_T, 2), "y": _rl(cv_d, 3)}]
    if cf:
        series.append({"label": "from energy fluctuations (Lebowitz-Percus-Verlet)", "kind": "points", "x": [round(a, 2) for a, _ in cf], "y": [round(b, 3) for _, b in cf]})
    g_c = _graphd(f"Heat capacity at constant volume ({mol['name']})", "temperature (K)", "C_V / (N k_B)", series,
                  "Heat capacity per particle in units of k_B, measured two independent ways. Theory: a harmonic crystal has 3 (each atom has 3 kinetic + 3 potential "
                  "quadratic terms, each worth k_B/2); an ideal monatomic gas has 3/2 (kinetic only). The simulated values go from near 3 in the crystal, "
                  "rise near melting (the liquid also stores energy in loosening neighbour bonds), and would approach the dilute-gas value 3/2 at low density and "
                  "high temperature (not reached in this range). The fluctuation estimate is noisier than the slope.",
                  hlines=[{"y": 3.0, "label": "harmonic crystal 3"}, {"y": 1.5, "label": "ideal monatomic gas 3/2"}], vlines=vl)
    return {"heating_U": g_u, "heating_D": g_d, "heat_capacity": g_c}


def exp_arrhenius(kb, mid, ref, t_star, job):
    mol = kb.molecule(mid)
    if mid == "water":
        Ts, N, ttau = [280.0, 300.0, 320.0, 340.0, 360.0], 100, 12.0
    else:
        rows = mol["saturation_table"]["rows"]
        lo, hi = rows[0][0] * 1.02, 0.75 * mol["thermo"]["critical_T_K"]
        Ts, N, ttau = list(np.linspace(lo, hi, 5)), 216, 4.0
    job["total"] = len(Ts)
    pts = []
    for T in Ts:
        rho = phase.mass_density_g_cm3(mol, float(T), 1.0, "liquid")
        n = rho * NA / mol["molar_mass_g_mol"] * 1e-24
        s = _run(mid, ref, float(T), n, N, "liquid", ttau)
        if s["D_cm2_s"]:
            pts.append((float(s["T_K"]), float(s["D_cm2_s"]), float(s["D_err_cm2_s"] or 0.0)))
        job["done"] += 1
    if len(pts) < 3:
        raise SweepError("too few liquid points with a measurable diffusion coefficient")
    T = np.array([p[0] for p in pts]); D = np.array([p[1] for p in pts]); E = np.array([p[2] for p in pts])
    x = 1000.0 / T
    y = np.log(D)
    slope, icpt = np.polyfit(x, y, 1)
    ea = -slope * 1000.0 * R_GAS / 1000.0                                  # kJ/mol
    xx = np.linspace(x.min() * 0.98, x.max() * 1.02, 10)
    series = [{"label": "simulation", "kind": "points", "x": _rl(x, 4), "y": _rl(y, 4), "yerr": _rl(E / D, 4)},
              {"label": f"fit: ln D = {icpt:.2f} - {-slope:.2f} (1000/T)", "kind": "line", "dash": True, "x": _rl(xx, 4), "y": _rl(slope * xx + icpt, 4)}]
    cap = (f"{mol['name']} liquid at saturated-liquid density (knowledge base), {N} particles. Diffusion is thermally activated: D = D0 exp(-Ea/RT), so ln D against 1/T "
           f"is a straight line whose slope gives the activation energy Ea = {ea:.1f} kJ/mol. Error bars are the spread between particle groups; with this few "
           f"particles and short runs, Ea is an estimate (roughly +/-30%).")
    if mid == "water":
        cap += " TIP3P water diffuses about twice as fast as real water, but its temperature dependence is the quantity of interest here."
    return {"arrhenius": _graphd("Arrhenius plot: ln D vs 1000/T", "1000 / T (1/K)", "ln D  (D in cm2/s)", series, cap)}


EXPERIMENTS = {"eos": exp_eos, "boyle": exp_boyle, "charles": exp_charles, "heating": exp_heating, "heatcap": exp_heating, "arrhenius": exp_arrhenius}


def _rl(a, n=4):
    return [round(float(v), n) for v in a]


def _graphd(title, xl, yl, series, caption, vlines=None, hlines=None):
    return {"title": title, "x_label": xl, "y_label": yl, "series": series, "vlines": vlines or [], "hlines": hlines or [], "ylog": False, "caption": caption}


# -------------------------------------------------------------------------------- jobs
def _worker(job, kind, components, t_star):
    kb = get_kb()
    try:
        mid = _pick(kb, components, kind)
        job["substance"] = kb.molecule(mid)["name"]
        job["graphs"] = EXPERIMENTS[kind](kb, mid, _ref(kb, mid), t_star, job)
        job["status"] = "done"
    except (SweepError, EngineRunError) as exc:
        job["status"], job["error"] = "error", str(exc)
    except Exception as exc:                       # never leave the interface polling forever
        job["status"], job["error"] = "error", f"{type(exc).__name__}: {exc}"


def start(kind, components, t_star):
    if kind not in EXPERIMENTS:
        raise SweepError(f"unknown experiment '{kind}'")
    with _LOCK:
        if any(j["status"] == "running" for j in JOBS.values()):
            raise SweepError("another experiment is still running; wait for it to finish")
        jid = uuid.uuid4().hex[:10]
        job = {"id": jid, "kind": kind, "status": "running", "done": 0, "total": 0, "graphs": {}, "error": None, "substance": None}
        JOBS[jid] = job
    threading.Thread(target=_worker, args=(job, kind, components, float(t_star)), daemon=True).start()
    return jid


def get(jid):
    return JOBS.get(jid)
