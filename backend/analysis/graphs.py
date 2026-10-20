"""
analysis/graphs.py

Turns MEASURED quantities (analysis/report.py) into plot descriptions that the
interface draws.  A graph is plain data:

    {"title", "x_label", "y_label", "ylog": bool,
     "series": [{"label", "kind": "line" | "points" | "bars", "x": [...], "y": [...],
                 "yerr": [...] (optional), "dash": bool (optional)}],
     "vlines": [{"x", "label"}], "hlines": [{"y", "label"}],
     "caption": "what it shows and how to read it"}

The captions are generated from the numbers by fixed rules (no language model), so
what is written under a graph is exactly what the graph shows.
"""

import math

import numpy as np

from backend.knowledge.kb import get_kb
from backend.units import KB, KB_J, MVV2E, NA


def _r(a, n=5):
    return [round(float(v), n) for v in a]


def _graph(title, x_label, y_label, series, caption, vlines=None, hlines=None, ylog=False):
    return {"title": title, "x_label": x_label, "y_label": y_label, "series": series,
            "vlines": vlines or [], "hlines": hlines or [], "ylog": ylog, "caption": caption}


# ------------------------------------------------------------------ time series --
def thermo_graphs(plan, res, thermo, equil, dt_fs):
    """Temperature and pressure against time, equilibration + production."""
    t0 = thermo[0]["Step"]
    t_prod = [(r["Step"] - t0) * dt_fs / 1000.0 for r in thermo]
    sphere = (not plan.periodic) and plan.shape == "sphere"
    pf = plan.box_A ** 3 / res["volume_A3"] if sphere else 1.0
    out = {}
    for key, col, unit, name in [("thermo_T", "Temp", "K", "Temperature"), ("thermo_P", "Press", "atm", "Pressure")]:
        scale = pf if col == "Press" else 1.0
        series = []
        if equil:
            e0 = equil[-1]["Step"]
            te = [(r["Step"] - e0) * dt_fs / 1000.0 for r in equil]
            series.append({"label": "equilibration", "kind": "line", "x": _r(te), "y": _r([r[col] * scale for r in equil]), "dash": True})
        series.append({"label": "production", "kind": "line", "x": _r(t_prod), "y": _r([r[col] * scale for r in thermo])})
        hl = []
        if col == "Temp":
            hl.append({"y": round(plan.T_K, 2), "label": f"target {plan.T_K:.0f} K"})
            cap = (f"Kinetic temperature T = 2K/(3Nk) of the particles. Production average {res['T_K']:.1f} K against the {plan.T_K:.0f} K "
                   f"requested. A thermostat (dashed, equilibration) brings the system to the target; production then runs at constant energy"
                   if plan.engine == "lj" else
                   f"Kinetic temperature. Average {res['T_K']:.1f} K against the {plan.T_K:.0f} K target, held by the thermostat")
            cap += (f"; fluctuations of about {100 * math.sqrt(2.0 / (3 * max(plan.n_objects, 1))):.0f}% are expected for {plan.n_objects} particles "
                    "(canonical-ensemble result sqrt(2/3N)).")
        else:
            if res.get("density_star", 1) < 0.1:
                p_id = plan.n_objects * KB * res["T_K"] / (res["volume_A3"] * 1.4583e-5)
                hl.append({"y": round(p_id, 4), "label": "ideal gas NkT/V"})
            hl.append({"y": round(res["P_atm"], 4), "label": "mean"})
            cap = (f"Pressure from the virial (kinetic + intermolecular forces). Mean {res['P_atm']:.4g} atm"
                   + (f", Z = PV/NkT = {res['Z']:.2f}" if res.get("density_star", 1) < 0.1 else "")
                   + ". Instantaneous pressure fluctuates strongly in small systems; only the average is meaningful.")
        out[key] = _graph(f"{name} vs time", "time (ps)", f"{name.lower()} ({unit})", series, cap,
                          vlines=[{"x": 0.0, "label": "production starts"}] if equil else None, hlines=hl)
    return out


# ---------------------------------------------------------------- speed distribution --
def _mb_curve(m_gmol, T_K, vmax):
    """Maxwell-Boltzmann speed density f(v) [per m/s] on a grid up to vmax (m/s)."""
    m = m_gmol / 1000.0 / NA
    v = np.linspace(0, vmax, 120)
    f = 4 * math.pi * (m / (2 * math.pi * KB_J * T_K)) ** 1.5 * v ** 2 * np.exp(-m * v ** 2 / (2 * KB_J * T_K))
    return v, f


def speed_graph(plan, res):
    arr = res.get("_arrays", {}).get("speeds_m_s")
    if arr is None or len(arr) == 0:
        return None
    kb = get_kb()
    pm = plan.primary.mol
    M = pm["molar_mass_g_mol"]
    T = res["T_K"]
    vmax = float(np.percentile(arr, 99.8)) * 1.25
    hist, edges = np.histogram(arr, bins=36, range=(0, vmax), density=True)
    centres = 0.5 * (edges[1:] + edges[:-1])
    series = [{"label": f"simulated {pm['name'].lower()}", "kind": "bars", "x": _r(centres, 3), "y": [float(f) for f in hist]}]
    v, f = _mb_curve(M, T, vmax)
    series.append({"label": f"Maxwell-Boltzmann, M={M:.1f} u", "kind": "line", "x": _r(v, 2), "y": [float(x) for x in f]})
    # the same temperature for other substances: mass alone changes the curve
    for other in ("helium", "argon"):
        if other != pm["id"] and len(series) < 4:
            om = kb.molecule(other)["molar_mass_g_mol"]
            v2, f2 = _mb_curve(om, T, vmax)
            series.append({"label": f"same T, {kb.molecule(other)['name'].lower()} (M={om:.1f} u)", "kind": "line", "dash": True,
                           "x": _r(v2, 2), "y": [float(x) for x in f2]})
    ks = res.get("ks_maxwell")
    cap = (f"Distribution of particle speeds at {T:.0f} K. Bars: measured from the trajectory; solid line: the Maxwell-Boltzmann law "
           f"f(v) ~ v^2 exp(-mv^2/2kT) for this substance"
           + (f" (Kolmogorov-Smirnov distance {ks:.3f}: a close match)" if ks is not None else "")
           + ". Dashed curves: the same law for other masses at the same temperature - lighter particles are faster, v ~ 1/sqrt(m).")
    return _graph("Speed distribution", "speed (m/s)", "probability density (per m/s)", series, cap,
                  vlines=[{"x": round(res["mean_speed_m_s"], 1), "label": f"mean {res['mean_speed_m_s']:.0f} m/s"}] if "mean_speed_m_s" in res else None)


def hard_sphere_speed_graph(plan, sp0, sp1, unit_v):
    """Hard spheres: initial vs final speed distribution against Maxwell-Boltzmann."""
    pm = plan.primary.mol
    a0, a1 = np.asarray(sp0) * unit_v, np.asarray(sp1) * unit_v
    vmax = float(max(a0.max(), a1.max())) * 1.6
    h0, e = np.histogram(a0, bins=36, range=(0, vmax), density=True)
    h1, _ = np.histogram(a1, bins=36, range=(0, vmax), density=True)
    c = 0.5 * (e[1:] + e[:-1])
    T = pm and plan.T_K
    v, f = _mb_curve(pm["molar_mass_g_mol"], T, vmax)
    series = [{"label": "first frame (all equal speed)", "kind": "bars", "x": _r(c, 3), "y": [float(x) for x in h0]},
              {"label": "last frame", "kind": "bars", "x": _r(c, 3), "y": [float(x) for x in h1]},
              {"label": "Maxwell-Boltzmann", "kind": "line", "x": _r(v, 2), "y": [float(x) for x in f]}]
    cap = ("Hard spheres start with identical speeds. Only collisions redistribute the energy: the speed distribution relaxes toward the "
           "Maxwell-Boltzmann law (Boltzmann's H-theorem). If few collisions occur (dilute gas) it stays near the initial spike.")
    return _graph("Speed distribution: initial vs final", "speed (m/s)", "probability density (per m/s)", series, cap)


# ----------------------------------------------------------------------------- g(r) --
def rdf_graph(plan, res):
    rd = res.get("rdf")
    if not rd:
        return None
    pm = plan.primary.mol
    ds = res.get("density_star", 0)
    series = [{"label": "g(r), " + ("O-O" if pm["id"] == "water" else pm["name"].lower()), "kind": "line", "x": _r(rd["r"], 3), "y": _r(rd["g"], 4)}]
    for h in res.get("hydration", []):
        if h.get("r"):
            series.append({"label": f"{h['ion'].split()[0]} - water O", "kind": "line", "x": _r(h["r"], 3), "y": _r(h["g"], 4)})
    vl = [{"x": round(rd["peak_r_A"], 2), "label": f"first peak {rd['peak_r_A']:.2f} A"}]
    ref = pm.get("experimental_reference", {}).get("oxygen_oxygen_rdf_first_peak_A")
    if ref and pm["id"] == "water":
        vl.append({"x": ref["value"], "label": f"experiment {ref['value']} A"})
    if ds < 0.1:
        cap = "g(r) is the relative probability of finding a neighbour at distance r. It stays near 1 at all distances: no structure - the particles are uncorrelated, as in an ideal gas."
    elif res.get("D_star", 1) < 0.005 and res.get("msd"):
        cap = (f"Sharp, repeated peaks: long-range order of a crystal. First peak at {rd['peak_r_A']:.2f} A, "
               f"about {rd['coordination']:.1f} neighbours in the first shell (an FCC crystal has 12).")
    else:
        cap = (f"Liquid structure: a strong first peak at {rd['peak_r_A']:.2f} A (height {rd['peak_g']:.2f}) and fading peaks that tend to 1 - short-range "
               f"order only. About {rd['coordination']:.1f} neighbours in the first shell.")
        if pm["id"] == "water":
            cap += " The first O-O peak is the hydrogen-bond distance."
    return _graph("Radial distribution function g(r)", "distance r (A)", "g(r)", series, cap, vlines=vl, hlines=[{"y": 1.0, "label": "uncorrelated (1)"}])


# ----------------------------------------------------------------------------- MSD --
def msd_graph(plan, res):
    m = res.get("msd")
    if not m or not m.get("t_fs"):
        return None
    t = np.array(m["t_fs"]) / 1000.0
    series = [{"label": "mean-squared displacement", "kind": "points", "x": _r(t, 4), "y": _r(m["msd"], 4)}]
    fit = m["slope"] * np.array(m["t_fs"]) + m["intercept"]
    series.append({"label": f"linear fit: slope = 6D", "kind": "line", "dash": True, "x": _r(t, 4), "y": _r(fit, 4)})
    ll = m["loglog_slope"]
    if ll > 1.6:
        regime = ("MSD grows as t^2 (ballistic motion): particles travel straight between rare collisions, so a diffusion coefficient is not defined here "
                  "- the mean free path is longer than the box.")
    elif ll > 0.7:
        regime = (f"MSD grows linearly with time (diffusive motion), as in a liquid or dense gas. The Einstein relation D = slope/6 gives "
                  f"D = {m['D_cm2_s']:.2e} cm2/s.")
        ref = plan.primary.mol.get("experimental_reference", {}).get("self_diffusion_cm2_s_298K")
        if ref and plan.primary.mol["id"] == "water":
            regime += f" Experiment at 298 K: {ref['value']:.2e} cm2/s."
    else:
        regime = "MSD levels off (plateau): particles only vibrate around fixed sites, as in a solid; D is about zero."
    return _graph("Mean-squared displacement", "time (ps)", "MSD (A^2)", series, regime)


# --------------------------------------------------------------------- reactions --
def species_graph(plan, species_rows, dt_fs):
    if not species_rows:
        return None
    first = {s.mol["formula"]: s.count for s in plan.species}
    pts = [(0.0, dict(first))]
    for step, d in species_rows:
        if all(len(k) <= 2 and k.isalpha() and k.isupper() and k not in ("H2", "O2") for k in d) and step == 0:
            continue
        pts.append((step * dt_fs / 1000.0, d))
    names = sorted({k for _t, d in pts for k in d}, key=lambda k: -max(d.get(k, 0) for _t, d in pts))
    series = []
    for k in names:
        ys = [d.get(k, 0) for _t, d in pts]
        if max(ys) > 0:
            series.append({"label": k, "kind": "line", "x": _r([t for t, _ in pts], 4), "y": ys})
    last = pts[-1][1]
    kb = get_kb()
    made = [k for k in last if last[k] > first.get(k, 0)]
    cap = ("Number of molecules of each species over time, counted from the bond network that the ReaxFF potential predicts "
           f"(bonds break and form during the run). Products: {', '.join(f'{k} (+{last[k] - first.get(k, 0)})' for k in made) or 'none yet'}. "
           "Short-lived intermediates (HO, H2O2, H) appear along the way. This is accelerated, high-temperature chemistry - see the limits in Messages.")
    return _graph("Species during the reaction", "time (ps)", "number of molecules", series, cap)


# ------------------------------------------------------------------------- driver --
def build(plan, res, thermo, equil, species_rows):
    g = {}
    if thermo:
        g.update(thermo_graphs(plan, res, thermo, equil, plan.dt_fs))
    sp = speed_graph(plan, res) if plan.engine in ("lj", "charged") else None
    if sp:
        g["speed"] = sp
    rd = rdf_graph(plan, res)
    if rd:
        g["rdf"] = rd
    ms = msd_graph(plan, res)
    if ms:
        g["msd"] = ms
    if plan.engine == "reaxff":
        sg = species_graph(plan, species_rows, plan.dt_fs)
        if sg:
            g["species"] = sg
    return g
