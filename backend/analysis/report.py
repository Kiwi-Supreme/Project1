"""
analysis/report.py

Turns raw simulation output into (1) measured physical quantities and (2) a
scientific explanation in the chain the interface shows in its Messages panel:

    Chemical -> Properties -> Physics -> Forces -> Simulation -> Observed behaviour

Everything numeric in the "Observed" lines is MEASURED from the trajectory and
the thermodynamic log.  Everything in the other lines is read from the chemical
knowledge base or from the Plan that configured the run.  The explanation text
is assembled by deterministic rules (no language model), so every sentence can
be traced to a number.
"""

import math

import numpy as np

from backend.knowledge import phase
from backend.knowledge.kb import get_kb
from backend.units import (ATM_A3_TO_KCALMOL, KB, MVV2E, NA, KB_J, pressure_atm_from_virial, thermal_de_broglie_A)

LJ_TC_STAR = 1.31      # critical temperature of the Lennard-Jones fluid, k_B T / epsilon
LJ_TRIPLE_STAR = 0.7   # its triple point (approximately)


def _block_stats(x, nblocks=8):
    x = np.asarray(x, float)
    if len(x) < nblocks * 2:
        return float(x.mean()), float(x.std() / math.sqrt(max(len(x), 1)))
    b = np.array_split(x, nblocks)
    m = np.array([bb.mean() for bb in b])
    return float(x.mean()), float(m.std(ddof=1) / math.sqrt(nblocks))


def _fmt(v, e=None, digits=3):
    if e is None:
        return f"{v:.{digits}g}"
    return f"{v:.{digits}g} ± {e:.1g}"


# --------------------------------------------------------------------- analysis
def analyse(plan, meta, thermo, steps, data, species_rows=None):
    """Compute measured quantities. `data` is (frames, atoms, 13) from the dump."""
    kb = get_kb()
    out = {}
    N = plan.n_objects
    V = plan.box_A ** 3
    if not plan.periodic and plan.shape == "sphere":
        V = (4.0 / 3.0) * math.pi * (plan.box_A / 2) ** 3
    out["volume_A3"] = V
    T, Te = _block_stats([r["Temp"] for r in thermo])
    P, Pe = _block_stats([r["Press"] for r in thermo])
    if not plan.periodic and plan.shape == "sphere":
        P *= plan.box_A ** 3 / V            # LAMMPS divides the virial by the bounding box, not the sphere
        Pe *= plan.box_A ** 3 / V
    out.update(T_K=T, T_err=Te, P_atm=P, P_err=Pe)
    out["Z"] = pressure_atm_from_virial(P, V, N, T)
    pe = np.array([r["PotEng"] for r in thermo])
    ke = np.array([r["KinEng"] for r in thermo])
    et = np.array([r["TotEng"] for r in thermo])
    out["pe_per_object"] = float(pe.mean() / N)
    out["U_per_object"] = float(et.mean() / N)                                 # total energy per particle, kcal/mol
    if plan.engine == "lj" and len(ke) > 20:
        # Lebowitz-Percus-Verlet: in a constant-energy run the kinetic-energy fluctuations give Cv
        kT = KB * T
        x = 2.0 * float(np.var(ke)) / (3.0 * N * kT ** 2)
        out["Cv_fluct_over_Nk"] = 1.5 / (1.0 - x) if x < 0.9 else None
    out["ke_per_object"] = float(ke.mean() / N)
    out["energy_drift_rel"] = float((et[-1] - et[0]) / max(abs(ke.mean()), 1e-9))
    out["energy_breakdown"] = {k: float(np.mean([r.get(c, 0.0) for r in thermo]) / N)
                               for k, c in [("van der Waals (LJ)", "E_vdwl"), ("Coulomb (short range)", "E_coul"),
                                            ("Coulomb (long range)", "E_long"), ("bonds", "E_bond"), ("angles", "E_angle")]}
    if data is not None and len(data):
        table = np.array(meta["table"])
        sp_idx = table[:, 0]
        site_idx = table[:, 1]
        f = data[:, :, 11:14]
        out["rms_force"] = float(np.sqrt((f ** 2).sum(axis=2).mean()))
        # --- primary species centre sites
        prim_i = [i for i, s in enumerate(plan.species) if s is plan.primary][0]
        centres = np.where((sp_idx == prim_i) & (site_idx == 0))[0]
        # --- speeds of the primary species' molecular centres of mass (Maxwell-Boltzmann check)
        mass_atom = np.array([meta["types"][int(t) - 1]["mass"] for t in data[0, :, 1]])
        sp = None
        if plan.engine in ("lj", "charged"):
            prim_atoms = np.where(sp_idx == prim_i)[0]
            nsite = plan.primary.n_sites
            groups = prim_atoms.reshape(-1, nsite)
            mv = data[:, groups, 8:11] * mass_atom[groups][None, :, :, None]
            com_v = mv.sum(axis=2) / mass_atom[groups].sum(axis=1)[None, :, None]
            sp = np.linalg.norm(com_v, axis=2)                               # A/fs
        else:
            sp = np.linalg.norm(data[:, centres, 8:11], axis=2)
        out["mean_speed_m_s"] = float(sp.mean() * 1e5)
        m = plan.primary.mol["molar_mass_g_mol"]
        if plan.engine in ("lj", "charged"):
            a = math.sqrt(KB * T / (MVV2E * m))                           # Maxwell scale parameter, A/fs
            out["mean_speed_theory_m_s"] = float(math.sqrt(8 * KB * T / (math.pi * MVV2E * m)) * 1e5)
            sample = sp[:: max(1, len(sp) // 12)].ravel()
            out.setdefault("_arrays", {})["speeds_m_s"] = sample * 1e5
            try:
                from scipy import stats
                out["ks_maxwell"] = float(stats.kstest(sample, "maxwell", args=(0, a)).statistic)
            except Exception:
                pass
        # --- structure and dynamics (periodic bulk only: walls distort g(r))
        dens_star = N * plan.ref.sigma ** 3 / V
        out["density_star"] = dens_star
        if plan.periodic and len(centres) >= 8:
            rdf = _rdf(data[:, centres, 2:5], plan.box_A, plan.ref.sigma)
            out["rdf"] = rdf
            # diffusion is motion RELATIVE to the centre of mass: remove any drift of the whole box
            mass = np.array([meta["types"][int(t) - 1]["mass"] for t in data[0, :, 1]])
            com = (data[:, :, 5:8] * mass[None, :, None]).sum(axis=1) / mass.sum()
            out["msd"] = _msd(data[:, centres, 5:8] - com[:, None, :], meta["every"] * plan.dt_fs)
            # ion hydration shells: ion -- water-oxygen radial distribution function
            water_i = next((i for i, s in enumerate(plan.species) if s.id == "water"), None)
            if water_i is not None:
                ox = np.where((sp_idx == water_i) & (site_idx == 0))[0]
                out["hydration"] = []
                for i, s in enumerate(plan.species):
                    if s.mol.get("category") == "ion":
                        ions = np.where(sp_idx == i)[0]
                        h = _pair_rdf(data[:, ions, 2:5], data[:, ox, 2:5], plan.box_A)
                        if h:
                            h["ion"] = s.mol["name"]
                            out["hydration"].append(h)
    out["tau_fs"] = plan.ref.tau_fs
    if species_rows:
        out["species_rows"] = species_rows
    return out


def _rdf(pos, L, sigma):
    nf, n, _ = pos.shape
    rmax = min(L / 2, 6 * sigma)
    nb = 120
    edges = np.linspace(0, rmax, nb + 1)
    hist = np.zeros(nb)
    sel = np.linspace(0, nf - 1, min(nf, 16)).astype(int)
    for f in sel:
        d = pos[f][:, None, :] - pos[f][None, :, :]
        d -= L * np.round(d / L)
        r = np.sqrt((d ** 2).sum(axis=2))[np.triu_indices(n, 1)]
        hist += np.histogram(r, edges)[0]
    shell = 4.0 / 3.0 * math.pi * (edges[1:] ** 3 - edges[:-1] ** 3)
    rho = n / L ** 3
    g = 2 * hist / (len(sel) * n * rho * shell)
    rc = 0.5 * (edges[1:] + edges[:-1])
    mask = (rc > 0.8 * sigma) & (rc < 2.0 * sigma)
    if not mask.any():
        return None
    ip = np.where(mask)[0][g[mask].argmax()]
    # first minimum after the peak
    j = ip
    while j + 1 < nb and g[j + 1] < g[j]:
        j += 1
    coord = 4 * math.pi * rho * float(np.sum(g[:j + 1] * rc[:j + 1] ** 2) * (edges[1] - edges[0]))
    return {"r": rc.tolist(), "g": g.tolist(), "peak_r_A": float(rc[ip]), "peak_g": float(g[ip]),
            "first_min_r_A": float(rc[j]), "coordination": coord}


def _pair_rdf(pa, pb, L):
    """g(r) between two different groups of particles (e.g. an ion and water oxygens) and the
    number of B particles in the first shell around an A particle."""
    nf, na, nb_ = pa.shape[0], pa.shape[1], pb.shape[1]
    rmax = min(L / 2, 6.0)
    nb = 60
    edges = np.linspace(0, rmax, nb + 1)
    hist = np.zeros(nb)
    sel = np.linspace(0, nf - 1, min(nf, 40)).astype(int)
    for f in sel:
        d = pa[f][:, None, :] - pb[f][None, :, :]
        d -= L * np.round(d / L)
        hist += np.histogram(np.sqrt((d ** 2).sum(axis=2)).ravel(), edges)[0]
    shell = 4.0 / 3.0 * math.pi * (edges[1:] ** 3 - edges[:-1] ** 3)
    rho_b = nb_ / L ** 3
    g = hist / (len(sel) * na * rho_b * shell)
    rc = 0.5 * (edges[1:] + edges[:-1])
    mask = (rc > 1.5) & (rc < 4.0)
    if not mask.any() or g[mask].max() < 1.0:
        return None
    ip = np.where(mask)[0][g[mask].argmax()]
    j = ip
    while j + 1 < nb and g[j + 1] < g[j]:
        j += 1
    coord = 4 * math.pi * rho_b * float(np.sum(g[:j + 1] * rc[:j + 1] ** 2) * (edges[1] - edges[0]))
    return {"peak_r_A": float(rc[ip]), "peak_g": float(g[ip]), "coordination": coord, "r": rc.tolist(), "g": g.tolist()}


def _msd(xu, dt_frame_fs):
    """Self-diffusion from the Einstein relation D = lim MSD(t) / 6t, using every frame as a
    time origin.  The error bar is the spread between 5 independent groups of particles."""
    nf, n = xu.shape[0], xu.shape[1]
    maxlag = nf // 2
    lags = np.arange(1, maxlag)
    per_atom = np.array([((xu[l:] - xu[:-l]) ** 2).sum(axis=2).mean(axis=0) for l in lags])   # (lag, atom)
    t = lags * dt_frame_fs
    lo, hi = int(0.3 * len(t)), int(0.8 * len(t))
    if hi - lo < 3 or n < 10:
        return None
    def slope(cols):
        return np.polyfit(t[lo:hi], per_atom[lo:hi][:, cols].mean(axis=1), 1)[0]
    groups = np.array_split(np.random.default_rng(0).permutation(n), 5)
    ds = np.array([slope(g) / 6.0 for g in groups])
    d = slope(slice(None)) / 6.0
    err = float(ds.std(ddof=1) / math.sqrt(len(ds)))
    curve = per_atom.mean(axis=1)
    coef = np.polyfit(t[lo:hi], curve[lo:hi], 1)
    a0, a1 = int(0.2 * len(t)), int(0.8 * len(t))
    ll = float(np.polyfit(np.log(t[a0:a1]), np.log(np.maximum(curve[a0:a1], 1e-12)), 1)[0])
    step = max(1, len(t) // 60)
    return {"D_A2_fs": float(d), "D_cm2_s": float(d * 0.1), "D_err_cm2_s": err * 0.1,
            "msd_final_A2": float(per_atom[-1].mean()), "t_fs": t[::step].tolist(), "msd": curve[::step].tolist(),
            "slope": float(coef[0]), "intercept": float(coef[1]), "loglog_slope": ll}


def diagnose_phase(plan, res):
    """Phase from the MEASURED density and mobility (not from the label the user chose)."""
    ds = res.get("density_star", 0)
    th = plan.primary.mol.get("thermo") or {}
    if ds < 0.1:
        return "gas"
    msd = res.get("msd")
    if msd:
        d_star = msd["D_A2_fs"] * plan.ref.tau_fs / plan.ref.sigma ** 2
        res["D_star"] = d_star
        if d_star < 0.005:
            return "solid"
        if th and res["T_K"] > th["critical_T_K"]:
            return "supercritical fluid"
        return "liquid"
    return "dense fluid"


# -------------------------------------------------------------------- explanation
def _site_summary(s):
    m = s.model
    st = m["sites"][0]
    if m["type"] == "lj_sphere":
        return f"{s.mol['name']}: sigma = {st['sigma_A']:.3f} A, epsilon/k = {st['epsilon_K']:.1f} K ({m['source'].split(' (as')[0]})"
    if m["type"] == "rigid_molecule_tip3p":
        o, h = m["sites"][0], m["sites"][1]
        return (f"{s.mol['name']}: TIP3P, q(O) = {o['charge']:+.3f} e, q(H) = {h['charge']:+.3f} e, sigma(O) = {o['sigma_A']:.3f} A, "
                f"epsilon(O) = {o['epsilon_kcal_mol']:.4f} kcal/mol, r(OH) = {m['bond']['r0_A']:.4f} A, HOH = {m['angle']['theta0_deg']:.2f} deg")
    return f"{s.mol['name']}: charge {st['charge']:+.0f} e, sigma = {st['sigma_A']:.3f} A, epsilon = {st['epsilon_kcal_mol']:.4f} kcal/mol (Joung-Cheatham)"


def chemical_lines(plan):
    kb = get_kb()
    lines = []
    for s in plan.species:
        mol = s.mol
        el = [kb.element(a["element"]) for a in mol["structure"]["atoms"]]
        cat = mol["category"].replace("_", " ")
        e0 = el[0]
        bits = [f"{mol['name']} ({mol['formula']}) — {cat}"]
        if mol["category"] == "noble_gas_atom":
            bits.append(f"Z = {e0['atomic_number']}, group {e0['group']} period {e0['period']} noble gas, monatomic, "
                        f"first ionisation energy {e0['first_ionization_eV']:.1f} eV (closed shell → chemically inert)")
        elif mol["category"] == "ion":
            bits.append(f"net charge {mol['net_charge']:+d} e, electronegativity {e0['electronegativity_pauling']}")
        else:
            bits.append(f"{mol['n_atoms']} atoms, {mol['structure']['geometry']}")
        p = mol["polarity"]
        bits.append(("polar (dipole %.2f D)" % p["dipole_debye"]) if p["polar"] and p["dipole_debye"] else "non-polar")
        if p.get("note"):
            bits.append(p["note"])
        bits.append(f"M = {mol['molar_mass_g_mol']:.4f} u")
        bits.append("intermolecular forces: " + ", ".join(i.replace("_", " ") for i in mol["intermolecular_forces"]))
        if mol["thermo"]:
            th = mol["thermo"]
            bits.append(f"melts {th['melting_point_K']:.1f} K, boils {th['boiling_point_K']:.1f} K, critical point {th['critical_T_K']:.1f} K")
        lines.append("Chemical: " + "; ".join(bits))
    return lines


def explain(plan, res, phase_measured, extras=None):
    """Chemical -> Properties -> Physics -> Forces -> Simulation -> Observed -> Why."""
    kb = get_kb()
    L = []
    pm = plan.primary
    L += chemical_lines(plan)
    for s in plan.species:
        L.append("Properties used: mass " + f"{s.mol['molar_mass_g_mol']:.4f} u in F = m a; " + _site_summary(s))
    # ---- physics / forces
    if plan.engine == "reaxff":
        L.append("Physics: REACTIVE molecular dynamics. Atoms move by Newton's laws, but the forces come from the ReaxFF bond-order "
                 "potential (Chenoweth, van Duin & Goddard 2008), which lets bonds break and form as atoms approach. This is "
                 "different from classical MD, where bonds are fixed for ever.")
    elif plan.engine == "hard_sphere":
        L.append("Physics: hard spheres of diameter sigma move in straight lines and exchange momentum only in elastic collisions "
                 "(no attraction). Energy is purely kinetic, so temperature is the average kinetic energy per particle: T = m<v^2>/3k.")
    else:
        L.append("Physics: Newton's second law m a = F for every particle, integrated in time with the velocity-Verlet algorithm; "
                 "the force is minus the gradient of the potential energy, F = -dU/dr.")
        if any(s.model["type"] == "lj_sphere" for s in plan.species):
            L.append("Forces: Lennard-Jones U(r) = 4 eps [(sigma/r)^12 - (sigma/r)^6]: the r^-6 term is the London dispersion attraction "
                     "(from induced dipoles), the r^-12 term is Pauli repulsion when electron clouds overlap. Unlike pairs combine by "
                     "Lorentz-Berthelot mixing.")
        if plan.engine == "charged":
            L.append("Forces: plus Coulomb's law between the partial charges, U = q_i q_j /(4 pi eps0 r), summed over all periodic images "
                     "with the particle-mesh Ewald method; water is held rigid with SHAKE. Hydrogen bonds are not a separate term: they "
                     "emerge from the H(+)...O(-) Coulomb attraction.")
    # ---- why: ratio of thermal energy to well depth
    prim_site = pm.model["sites"][0]
    if pm.model["type"] == "lj_sphere":
        eps_k = prim_site["epsilon_K"]
        ratio = plan.T_K / eps_k
        if ratio > 5:
            why = (f"kT is {ratio:.1f}× the attraction well depth (epsilon/k = {eps_k:.1f} K): thermal motion overwhelms the weak "
                   f"{pm.mol['name'].lower()}–{pm.mol['name'].lower()} attraction, so particles are almost free (gas-like, near ideal).")
        elif ratio > LJ_TC_STAR:
            why = (f"T* = {ratio:.2f} is above the Lennard-Jones critical value (~{LJ_TC_STAR}): attraction matters but cannot hold a liquid together.")
        elif ratio > LJ_TRIPLE_STAR:
            why = f"T* = {ratio:.2f} lies between the LJ triple point (~{LJ_TRIPLE_STAR}) and critical point (~{LJ_TC_STAR}): a liquid / dense-vapour regime."
        else:
            why = f"T* = {ratio:.2f} is below the LJ triple point (~{LJ_TRIPLE_STAR}): attraction dominates thermal motion, so a solid is favoured."
        L.append("Forces: " + why)
    elif pm.model["type"] == "rigid_molecule_tip3p":
        L.append(f"Forces: water's large partial charges make the electrostatic part dominate; kT at {plan.T_K:.0f} K is small compared with the "
                 "hydrogen-bond energy, so molecules stay in a connected liquid network.")
    # ---- simulation
    ref = plan.ref
    L.append(f"Simulation: {plan.n_objects} particles ({plan.n_atoms} atoms), {'periodic box' if plan.periodic else plan.shape + ' container'} "
             f"{plan.box_A:.1f} A, target T = {plan.T_K:.1f} K (T* = {ref.T_to_star(plan.T_K):.2f}), time step {plan.dt_fs:.2f} fs, "
             f"{plan.steps} steps = {plan.total_fs / 1000:.1f} ps ({plan.total_fs / ref.tau_fs:.1f} tau; tau = {ref.tau_fs:.0f} fs for {pm.mol['name']}), "
             f"engine: {'LAMMPS reactive (ReaxFF)' if plan.engine == 'reaxff' else 'LAMMPS classical MD' if plan.engine != 'hard_sphere' else 'hard-sphere event model'}"
             + ("; equilibrated with a thermostat, then production run at constant energy (NVE)" if plan.engine == "lj"
                else "; thermostatted (NVT)" if plan.engine in ("charged", "reaxff") else "") + ".")
    # ---- observed
    T, P = res["T_K"], res["P_atm"]
    L.append(f"Observed: temperature {_fmt(T, res['T_err'])} K (target {plan.T_K:.1f} K), pressure {_fmt(P, res['P_err'])} atm, "
             + (f"compressibility Z = PV/NkT = {res['Z']:.2f}, " if res.get("density_star", 1) < 0.1 else "") + f"potential energy {res['pe_per_object']:.3g} and kinetic {res['ke_per_object']:.3g} kcal/mol per particle.")
    if "mean_speed_m_s" in res:
        s = f"Observed: mean speed of {pm.mol['name'].lower()} = {res['mean_speed_m_s']:.0f} m/s"
        if "mean_speed_theory_m_s" in res:
            s += (f" (Maxwell–Boltzmann prediction sqrt(8kT/πm) = {res['mean_speed_theory_m_s']:.0f} m/s; "
                  f"Kolmogorov–Smirnov distance {res.get('ks_maxwell', float('nan')):.3f})")
        L.append(s + ".")
        if pm.mol["id"] != "argon" and plan.engine in ("lj", "charged", "hard_sphere") and pm.model["type"] == "lj_sphere":
            ar = kb.molecule("argon")["molar_mass_g_mol"]
            L.append(f"Why: at the same temperature lighter particles are faster, v ∝ 1/√m: "
                     f"{pm.mol['name']} (M = {pm.mol['molar_mass_g_mol']:.2f} u) is {math.sqrt(ar / pm.mol['molar_mass_g_mol']):.2f}× as fast as argon (M = {ar:.2f} u).")
    if plan.engine == "lj" and abs(res["energy_drift_rel"]) < 1:
        L.append(f"Observed: total energy in the constant-energy production run changed by {abs(100 * res['energy_drift_rel']):.4f}% of the kinetic energy "
                 "(energy conservation check of the integrator).")
    z = res["Z"]
    if plan.engine in ("lj", "charged") and res.get("density_star", 1) < 0.1:
        if abs(z - 1) < 0.05:
            L.append("Why: Z ≈ 1 — the pressure equals the ideal-gas value N k T / V because the particles rarely interact.")
        elif z > 1:
            L.append(f"Why: Z = {z:.2f} > 1 — short-range repulsion between particles raises the pressure above the ideal-gas value.")
        else:
            L.append(f"Why: Z = {z:.2f} < 1 — attraction between particles lowers the pressure below the ideal-gas value.")
    elif plan.engine == "lj" and res.get("density_star", 0) >= 0.1:
        pe_eps = res["pe_per_object"] / plan.ref.eps
        L.append(f"Why: each particle's potential energy is {pe_eps:.1f} \u03b5 (\u03b5 = {plan.ref.eps:.4f} kcal/mol = the depth of one pair attraction): "
                 "it is held in the dense fluid by the attraction to its many near neighbours, balanced by short-range repulsion.")
    if "rdf" in res and res["rdf"] and res.get("density_star", 0) >= 0.2:
        r = res["rdf"]
        L.append(f"Observed: radial distribution function peaks at r = {r['peak_r_A']:.2f} A (height {r['peak_g']:.2f}); "
                 f"about {r['coordination']:.1f} neighbours in the first shell.")
        ref_rdf = pm.mol.get("experimental_reference", {}).get("oxygen_oxygen_rdf_first_peak_A")
        if ref_rdf and pm.mol["id"] == "water":
            L.append(f"Observed: experiment puts the O–O first peak near {ref_rdf['value']} A — the hydrogen-bond distance.")
    for h in res.get("hydration", []):
        L.append(f"Observed: {h['ion']} hydration shell \u2014 first ion\u2013water(O) peak at {h['peak_r_A']:.2f} A, about {h['coordination']:.1f} water molecules "
                 f"around each ion (ion\u2013dipole attraction orients water's negative O toward cations and positive H toward anions).")
    if res.get("msd") and res.get("density_star", 0) >= 0.1:
        d = res["msd"]["D_cm2_s"]
        s = f"Observed: self-diffusion coefficient D = {d:.2e} ± {res['msd']['D_err_cm2_s']:.1e} cm²/s (mean-squared displacement / 6t)"
        ref_d = pm.mol.get("experimental_reference", {}).get("self_diffusion_cm2_s_298K")
        if ref_d and pm.mol["id"] == "water":
            s += f"; experiment at 298 K: {ref_d['value']:.2e} cm²/s (TIP3P is known to diffuse about twice as fast as real water)"
        L.append(s + ".")
    if res["energy_breakdown"] and plan.engine == "charged":
        eb = res["energy_breakdown"]
        L.append("Observed: potential energy split per particle (kcal/mol): " + ", ".join(f"{k} {v:.2f}" for k, v in eb.items() if abs(v) > 1e-9) + ".")
    L.append(f"Observed: root-mean-square force on an atom = {res['rms_force']:.2f} kcal/mol/A." if "rms_force" in res else "")
    # mean free path
    if phase_measured == "gas" and P > 0 and pm.model["type"] == "lj_sphere":
        sig_m = prim_site["sigma_A"] * 1e-10
        lam = KB_J * T / (math.sqrt(2) * math.pi * sig_m ** 2 * P * 101325.0)
        L.append(f"Observed: mean free path λ = kT/(√2 π σ² P) = {lam * 1e9:.1f} nm versus box {plan.box_A / 10:.1f} nm — "
                 + ("collisions between particles are rare (ideal-gas regime)." if lam > plan.box_A * 1e-10 else "particles collide many times while crossing the box."))
    expected = None
    if len(plan.species) == 1 and pm.mol.get("thermo"):
        expected = phase.state_at(pm.mol, plan.T_K, max(P, 1e-6))
    L.append(f"Observed behaviour: the particles form a {phase_measured}" +
             (f" (knowledge-base prediction at the target temperature and measured pressure: {expected})." if expected else "."))
    return [x for x in L if x]


def reactive_lines(plan, res):
    kb = get_kb()
    L = []
    rows = [r for r in (res.get("species_rows") or []) if not all(len(k) <= 2 and k[0].isupper() and k.isalpha() and k not in ("H2", "O2") for k in r[1])]
    # step-0 rows with bare element counts are dropped above
    if not rows:
        return L
    first, last = rows[0][1], rows[-1][1]
    names = sorted(set(first) | set(last))
    L.append("Reaction: species count at start → end: " + ", ".join(f"{n} {first.get(n, 0)}→{last.get(n, 0)}" for n in names))
    formed = [n for n in last if last[n] > first.get(n, 0)]
    for rx in kb.interactions.get("reactions", []):
        reactants = {kb.molecule(k)["formula"] for k, c in rx["stoich"].items() if c < 0}
        if reactants <= set(first):
            prods = {kb.molecule(k)["formula"] for k, c in rx["stoich"].items() if c > 0}
            L.append(f"Reaction: expected overall chemistry {rx['equation']}, ΔH = {rx['reaction_enthalpy_kJ']} kJ per mole of reaction "
                     f"(from tabulated formation enthalpies).")
            made = [p for p in prods if last.get(p, 0) > first.get(p, 0)]
            L.append("Reaction: " + (f"{', '.join(f'{p} (+{last[p] - first.get(p, 0)})' for p in made)} formed in the simulation by bond breaking/forming "
                                     f"predicted by ReaxFF; intermediates such as {', '.join(n for n in formed if n not in prods) or 'none'} appear along the way."
                                     if made else "no product formed within this short simulation: the reaction needs a higher temperature or a longer time."))
    L.append(f"Reaction: LIMITS — ReaxFF is an empirical bond-order model, not quantum mechanics; picosecond runs need very high temperature "
             f"({plan.T_K:.0f} K here) so reactions occur at all, so mechanisms and rates shown are NOT those at ordinary temperatures.")
    return L
