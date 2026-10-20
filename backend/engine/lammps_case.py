"""
engine/lammps_case.py

Writes the two files LAMMPS needs for a Plan:

    system.data   the starting configuration: box, atom types (mass), atoms
                  (positions, charges), bonds and angles for water
    in.lammps     the input script: force field, thermostat, time step, outputs

and returns a description of every atom (which species, which site) so the
results can be interpreted.  Everything substance-specific -- masses, sigma,
epsilon, charges, geometries -- is read from the Plan, i.e. from the chemical
knowledge base.  Nothing is hard-coded here.

Three physical models are produced:
  lj       neutral species as Lennard-Jones spheres (noble gases, small
           molecules as one site), optional LJ-93 walls; production in NVE
  charged  rigid TIP3P water + ions (+ LJ spheres): Lennard-Jones + Coulomb with
           PPPM long-range electrostatics, SHAKE constraints; NVT
  reaxff   reactive molecular dynamics with the ReaxFF bond-order potential
           (only for substances whose elements the force field covers); NVT
"""

import math
import os
import shutil

import numpy as np

from backend.units import KB

DUMP_FRAMES = 250


def _rotation(rng):
    q = rng.normal(size=4)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def _fcc_sites(box, n_needed, inside=None):
    """FCC lattice points inside the box (optionally inside a predicate), with
    the lattice constant chosen so at least n_needed points fit."""
    n = max(1, math.ceil((n_needed / 4.0) ** (1.0 / 3.0)))
    basis = np.array([[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]])
    while True:
        a = box / n
        cells = np.array([[i, j, k] for i in range(n) for j in range(n) for k in range(n)])
        pts = ((cells[:, None, :] + basis[None, :, :]).reshape(-1, 3) + 0.25) * a
        if inside is not None:
            pts = pts[inside(pts)]
        if len(pts) >= n_needed:
            return pts
        n += 1


def _random_sites(rng, box, n, min_sep, inside=None, margin=0.0, periodic=True):
    pts = []
    tries = 0
    while len(pts) < n:
        tries += 1
        if tries > 200000:
            raise RuntimeError("could not place particles without overlap -- density too high for random placement")
        p = margin + rng.random(3) * (box - 2 * margin)
        if inside is not None and not inside(p[None, :])[0]:
            continue
        ok = True
        if pts:
            d = np.array(pts) - p
            if periodic:
                d -= box * np.round(d / box)
            ok = (np.einsum("ij,ij->i", d, d) >= min_sep ** 2).all()
        if ok:
            pts.append(p)
    return np.array(pts)


def _grid_sites(rng, box, n):
    g = math.ceil(n ** (1.0 / 3.0))
    sp = box / g
    idx = [(i, j, k) for i in range(g) for j in range(g) for k in range(g)]
    rng.shuffle(idx)
    return (np.array(idx[:n]) + 0.5) * sp


def build_case(plan, outdir, seed):
    """Create system.data + in.lammps in `outdir`. Returns the atom table."""
    rng = np.random.default_rng(seed)
    prm = plan.params
    L = plan.box_A
    engine = plan.engine
    kb_species = plan.species

    # ---------------- atom types ------------------------------------------------
    types = []                       # dicts: mass, charge, sigma, eps, element, label
    type_of = {}                     # (species idx, site idx) -> type id (1-based)

    def add_type(key, **kw):
        if key not in type_of:
            types.append(kw)
            type_of[key] = len(types)
        return type_of[key]

    for si, s in enumerate(kb_species):
        if engine == "reaxff":
            for a in s.mol["structure"]["atoms"]:
                el = a["element"]
                add_type(("el", el), mass=_el_mass(el), charge=0.0, sigma=0, eps=0, element=el, label=el)
        elif s.model["type"] == "rigid_molecule_tip3p":
            for k, site in enumerate(s.model["sites"]):
                add_type(("water", k), mass=site["mass"], charge=site["charge"], sigma=site["sigma_A"],
                         eps=site["epsilon_kcal_mol"], element=site["element"], label=site["name"])
        else:
            site = s.model["sites"][0]
            add_type((si, 0), mass=site["mass"], charge=site["charge"], sigma=site["sigma_A"],
                     eps=site["epsilon_kcal_mol"], element=site.get("element"), label=s.mol["formula"])

    # ---------------- centres of the objects ----------------------------------------
    n_obj = plan.n_objects
    R = L / 2.0
    center = np.array([R, R, R])
    sphere = (not plan.periodic) and plan.shape == "sphere"
    inside = (lambda P: np.linalg.norm(P - center, axis=1) <= 0.88 * R) if sphere else None
    sigma_min = min(t["sigma"] for t in types if t["sigma"] > 0) if engine != "reaxff" else 1.0
    if engine == "lj":
        if prm.state == "gas":
            pts = _random_sites(rng, L, n_obj, 0.8 * sigma_min, inside=inside,
                                margin=0.0 if plan.periodic else 0.9 * plan.ref.sigma, periodic=plan.periodic)
        else:
            pts = _fcc_sites(L, n_obj, inside=inside)
            pts = pts[rng.permutation(len(pts))[:n_obj]]
    else:
        pts = _grid_sites(rng, L, n_obj)
    order = []
    for si, s in enumerate(kb_species):
        order += [si] * s.count
    order = rng.permutation(order)

    # ---------------- atoms ---------------------------------------------------------------
    atoms, bonds, angles, table = [], [], [], []
    for oi, (c, si) in enumerate(zip(pts, order)):
        s = kb_species[si]
        mol_id = oi + 1
        if engine == "reaxff":
            geo = np.array([a["xyz_A"] for a in s.mol["structure"]["atoms"]], float)
            geo -= geo.mean(axis=0)
            xyz = geo @ _rotation(rng).T + c
            for k, a in enumerate(s.mol["structure"]["atoms"]):
                atoms.append((len(atoms) + 1, mol_id, type_of[("el", a["element"])], 0.0, *xyz[k]))
                table.append((si, k))
        elif s.model["type"] == "rigid_molecule_tip3p":
            r0 = s.model["bond"]["r0_A"]
            th = math.radians(s.model["angle"]["theta0_deg"])
            geo = np.array([[0, 0, 0], [r0, 0, 0], [r0 * math.cos(th), r0 * math.sin(th), 0]])
            xyz = geo @ _rotation(rng).T + c
            first = len(atoms) + 1
            o_site, h_site = s.model["sites"][0], s.model["sites"][1]
            for k, site in enumerate([o_site, h_site, h_site]):          # O, H, H
                atoms.append((len(atoms) + 1, mol_id, type_of[("water", 0 if k == 0 else 1)], site["charge"], *xyz[k]))
                table.append((si, k))
            bonds += [(len(bonds) + 1, 1, first, first + 1), (len(bonds) + 2, 1, first, first + 2)]
            angles.append((len(angles) + 1, 1, first + 1, first, first + 2))
        else:
            site = s.model["sites"][0]
            atoms.append((len(atoms) + 1, mol_id, type_of[(si, 0)], site["charge"], *c))
            table.append((si, 0))

    # ---------------- data file --------------------------------------------------------------
    atom_style = {"lj": "atomic", "charged": "full", "reaxff": "charge"}[engine]
    with open(os.path.join(outdir, "system.data"), "w") as f:
        f.write(f"{engine} system generated from the chemical knowledge base\n\n{len(atoms)} atoms\n{len(types)} atom types\n")
        if engine == "charged" and bonds:
            f.write(f"{len(bonds)} bonds\n1 bond types\n{len(angles)} angles\n1 angle types\n")
        f.write(f"\n0 {L:.6f} xlo xhi\n0 {L:.6f} ylo yhi\n0 {L:.6f} zlo zhi\n\nMasses\n\n")
        for i, t in enumerate(types, 1):
            f.write(f"{i} {t['mass']:.6f}\n")
        f.write(f"\nAtoms # {atom_style}\n\n")
        for a in atoms:
            if atom_style == "atomic":
                f.write(f"{a[0]} {a[2]} {a[4]:.6f} {a[5]:.6f} {a[6]:.6f}\n")
            elif atom_style == "charge":
                f.write(f"{a[0]} {a[2]} {a[3]:.6f} {a[4]:.6f} {a[5]:.6f} {a[6]:.6f}\n")
            else:
                f.write(f"{a[0]} {a[1]} {a[2]} {a[3]:.6f} {a[4]:.6f} {a[5]:.6f} {a[6]:.6f}\n")
        if engine == "charged" and bonds:
            f.write("\nBonds\n\n")
            for b in bonds:
                f.write(f"{b[0]} {b[1]} {b[2]} {b[3]}\n")
            f.write("\nAngles\n\n")
            for a in angles:
                f.write(f"{a[0]} {a[1]} {a[2]} {a[3]} {a[4]}\n")

    # ---------------- input script ----------------------------------------------------------------
    T = plan.T_K
    dt = plan.dt_fs
    prod = plan.steps
    every = max(1, prod // DUMP_FRAMES)
    prod = every * (prod // every)                       # whole number of dump intervals
    equil = int(min(10000, max(3000, prod // 2)))
    rc = prm.cutoff * plan.ref.sigma
    sig_ref, eps_ref = plan.ref.sigma, plan.ref.eps
    thermo = "thermo_style custom step time temp press pe ke etotal vol evdwl ecoul elong ebond eangle"
    L_ = []
    w = L_.append
    w("units real")
    w(f"atom_style {atom_style}")
    w("boundary p p p" if plan.periodic else "boundary f f f")
    if engine == "charged" and bonds:
        w("bond_style harmonic\nangle_style harmonic")
    w("read_data system.data")
    w("neighbor 2.0 bin\nneigh_modify delay 0 every 1 check yes")
    if engine == "lj":
        w(f"pair_style lj/cut {rc:.4f}")
        for i, t in enumerate(types, 1):
            w(f"pair_coeff {i} {i} {t['eps']:.8f} {t['sigma']:.6f}")
        w("pair_modify mix arithmetic shift yes")
    elif engine == "charged":
        w(f"pair_style lj/cut/coul/long {rc:.4f}")
        for i, t in enumerate(types, 1):
            sg = t["sigma"] if t["sigma"] > 0 else 1.0
            w(f"pair_coeff {i} {i} {t['eps']:.8f} {sg:.6f}")
        w("pair_modify mix arithmetic")
        w("kspace_style pppm 1.0e-4")
        if bonds:
            ws = next(s for s in kb_species if s.model["type"] == "rigid_molecule_tip3p")
            w(f"bond_coeff 1 {ws.model['bond']['k_kcal_mol_A2']:.4f} {ws.model['bond']['r0_A']:.5f}")
            w(f"angle_coeff 1 {ws.model['angle']['k_kcal_mol_rad2']:.4f} {ws.model['angle']['theta0_deg']:.4f}")
        w("special_bonds lj/coul 0.0 0.0 0.0")
    else:  # reaxff
        els = [t["element"] for t in types]
        w("pair_style reaxff NULL")
        w(f"pair_coeff * * ffield.reax.cho {' '.join(els)}")
        w("fix q all qeq/reaxff 1 0.0 10.0 1e-6 reaxff")
    if engine == "lj" and not plan.periodic:
        if plan.shape == "sphere":
            w(f"region wallsph sphere {R:.4f} {R:.4f} {R:.4f} {R:.4f} side in units box")
            w(f"fix wall all wall/region wallsph lj93 {eps_ref:.8f} {sig_ref:.6f} {2.5 * sig_ref:.4f}")
        else:
            w(f"fix wall all wall/lj93 xlo EDGE {eps_ref:.8f} {sig_ref:.6f} {2.5 * sig_ref:.4f} xhi EDGE {eps_ref:.8f} {sig_ref:.6f} "
              f"{2.5 * sig_ref:.4f} ylo EDGE {eps_ref:.8f} {sig_ref:.6f} {2.5 * sig_ref:.4f} yhi EDGE {eps_ref:.8f} {sig_ref:.6f} "
              f"{2.5 * sig_ref:.4f} zlo EDGE {eps_ref:.8f} {sig_ref:.6f} {2.5 * sig_ref:.4f} zhi EDGE {eps_ref:.8f} {sig_ref:.6f} {2.5 * sig_ref:.4f}")
        w("fix_modify wall energy yes virial yes")      # count the wall potential in the energy and pressure
    w(thermo)
    w("thermo_modify flush yes")
    w(f"thermo {max(equil // 40, 1)}")
    w(f"timestep {dt:.5f}")
    if engine != "reaxff":
        w("minimize 1.0e-6 1.0e-8 200 2000" if engine == "lj" else "minimize 1.0e-4 1.0e-6 200 2000")
        w(f"velocity all create {T:.4f} {seed % 900000 + 1} mom yes rot {'no' if engine == 'lj' else 'yes'} dist gaussian")
        if engine == "charged":
            w("fix relax all nve/limit 0.05\nrun 500\nunfix relax")
            if bonds:
                w("fix sh all shake 1.0e-4 20 0 b 1 a 1")
            w(f"fix th all nvt temp {T:.4f} {T:.4f} 100.0")
            w("fix mom all momentum 100 linear 1 1 1")   # keep total momentum zero (no drift of the whole box)
            w(f"run {equil}")
        else:
            w(f"fix integ all nve\nfix lang all langevin {T:.4f} {T:.4f} {100.0:.1f} {seed % 800000 + 7}")
            w(f"run {equil}")
            w("unfix lang")
            if plan.periodic:
                w("velocity all zero linear")          # the thermostat leaves a small net momentum: remove it so the whole system does not drift
            w(f"velocity all scale {T:.4f}")          # start the constant-energy run exactly at the target temperature
    else:
        w(f"velocity all create {T:.4f} {seed % 900000 + 1} mom yes rot yes dist gaussian")
        w(f"fix th all nvt temp {T:.4f} {T:.4f} 25.0")
        w("fix mom all momentum 100 linear 1 1 1")
        w("fix sp all reaxff/species 10 10 100 species.out element " + " ".join(t["element"] for t in types))
    w("reset_timestep 0")
    w(f"dump d all custom {every} traj.dump id type x y z xu yu zu vx vy vz fx fy fz")
    w("dump_modify d sort id")
    w(f"thermo {every}")
    w(f"run {prod}")
    with open(os.path.join(outdir, "in.lammps"), "w") as f:
        f.write("\n".join(L_) + "\n")

    return {"table": table, "types": types, "n_atoms": len(atoms), "every": every, "prod_steps": prod,
            "equil_steps": equil if engine != "reaxff" else 0, "seed": seed, "rc_A": rc}


def _el_mass(sym):
    from backend.knowledge.kb import get_kb
    return get_kb().element(sym)["atomic_weight_u"]


def find_reaxff_file():
    """Locate ffield.reax.cho (shipped with LAMMPS)."""
    cand = []
    if os.environ.get("LAMMPS_POTENTIALS"):
        cand.append(os.environ["LAMMPS_POTENTIALS"])
    try:
        import lammps
        cand.append(os.path.join(os.path.dirname(lammps.__file__), "share", "lammps", "potentials"))
    except Exception:
        pass
    exe = shutil.which("lmp") or shutil.which("lmp_serial") or shutil.which("lmp_mpi")
    if exe:
        base = os.path.dirname(os.path.realpath(exe))
        cand += [os.path.join(base, "..", "share", "lammps", "potentials"), os.path.join(base, "potentials")]
    for d in cand:
        p = os.path.join(d, "ffield.reax.cho")
        if os.path.isfile(p):
            return p
    return None
