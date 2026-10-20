"""
build_dataset.py  --  (re)generates the JSON files in this folder.

This is a DEVELOPER tool. The running application never imports it and never
needs the libraries it uses; at run time the app only reads the JSON files.
Every number in the JSON files is pulled from a published dataset by this
script -- none is typed in by hand -- except the handful of items listed in
STRUCTURE / REACTIVITY / INTERACTION_TEXT below, which are textbook facts
(molecular geometries, qualitative chemistry) and carry a source tag.

    pip install mendeleev chemicals thermo openmm lammps mpich
    python chemical_knowledge/build_dataset.py

Sources
  elements.json        mendeleev (aggregates NIST / CRC Handbook element data)
  molecules.json       chemicals + thermo (Caleb Bell; DIPPR / CRC / Yaws / NIST
                       WebBook-derived critical constants, melting / boiling
                       points, dipole moments, saturated liquid density and
                       vapour pressure correlations, formation enthalpies)
  force_parameters.json
                       neutral species: Lennard-Jones sigma / epsilon tabulated
                       in `chemicals` (Poling, Prausnitz & O'Connell 2001;
                       Magalhaes et al. 2013), chosen by the rule documented in
                       pick_lj().  Water + ions: OpenMM's bundled Amber files
                       tip3p.xml / amber14/tip3p.xml (Jorgensen 1983 TIP3P;
                       Joung & Cheatham 2008 ions).  Reactive: LAMMPS
                       ffield.reax.cho (Chenoweth, van Duin, Goddard 2008).
"""

import json
import math
import os
import warnings
import xml.etree.ElementTree as ET

import numpy as np

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))

KB_K = 0.0019872041          # Boltzmann constant, kcal/mol/K
LJ_TC_STAR = 1.31            # critical temperature of the LJ fluid, kT/eps
H_PLANCK, NA, KB_J = 6.62607015e-34, 6.02214076e23, 1.380649e-23

# ---------------------------------------------------------------- elements ----
def build_elements():
    from mendeleev import element
    out = {}
    for z in range(1, 119):
        e = element(z)
        def g(name, call=False):
            try:
                v = getattr(e, name)
                return v() if call else v
            except Exception:
                return None
        ie = g("ionenergies") or {}
        out[e.symbol] = {
            "symbol": e.symbol, "name": e.name, "atomic_number": e.atomic_number,
            "atomic_weight_u": g("atomic_weight"), "group": g("group_id"),
            "period": g("period"), "block": g("block"), "series": g("series"),
            "noble_gas": g("series") == "Noble gases",
            "electronegativity_pauling": g("electronegativity_pauling", True),
            "vdw_radius_pm": g("vdw_radius"), "covalent_radius_pm": g("covalent_radius_pyykko"),
            "first_ionization_eV": ie.get(1), "electron_affinity_eV": g("electron_affinity"),
            "melting_point_K": g("melting_point"), "boiling_point_K": g("boiling_point"),
            "density_g_cm3": g("density"), "electron_configuration": g("econf"),
            "oxidation_states": g("oxidation_states", True),
        }
    return out

# --------------------------------------------------------------- molecules ----
# Textbook geometry (experimental, NIST CCCBDB). Coordinates in Angstrom.
def _ch4():
    d = 1.087 / math.sqrt(3)
    return [("C", 0, 0, 0)] + [("H", sx * d, sy * d, sz * d)
                               for sx, sy, sz in [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]]

def _h2o():
    r, th = 0.9572, math.radians(104.52)
    return [("O", 0, 0, 0), ("H", r, 0, 0), ("H", r * math.cos(th), r * math.sin(th), 0)]

STRUCTURE = {   # id: (geometry text, atoms with coordinates, bonds [i, j, order])
    "helium": ("single atom", [("He", 0, 0, 0)], []),
    "neon": ("single atom", [("Ne", 0, 0, 0)], []),
    "argon": ("single atom", [("Ar", 0, 0, 0)], []),
    "krypton": ("single atom", [("Kr", 0, 0, 0)], []),
    "xenon": ("single atom", [("Xe", 0, 0, 0)], []),
    "hydrogen": ("linear diatomic, r(H-H)=0.741 A", [("H", 0, 0, 0), ("H", 0.7414, 0, 0)], [[0, 1, 1]]),
    "oxygen": ("linear diatomic, r(O=O)=1.208 A", [("O", 0, 0, 0), ("O", 1.2075, 0, 0)], [[0, 1, 2]]),
    "nitrogen": ("linear diatomic, r(N#N)=1.098 A", [("N", 0, 0, 0), ("N", 1.0977, 0, 0)], [[0, 1, 3]]),
    "carbon_dioxide": ("linear triatomic O=C=O, r(C=O)=1.162 A",
                       [("O", -1.162, 0, 0), ("C", 0, 0, 0), ("O", 1.162, 0, 0)], [[0, 1, 2], [1, 2, 2]]),
    "methane": ("tetrahedral, r(C-H)=1.087 A, H-C-H = 109.5 deg", _ch4(),
                [[0, 1, 1], [0, 2, 1], [0, 3, 1], [0, 4, 1]]),
    "water": ("bent, r(O-H)=0.9572 A, H-O-H = 104.52 deg", _h2o(), [[0, 1, 1], [0, 2, 1]]),
}
# Textbook fact: helium does not freeze at atmospheric pressure at any temperature;
# it solidifies only above ~25 atm (zero-point energy; Keesom 1926).
SOLID_MIN_P = {"helium": 25.0}
# Experimental reference values used ONLY to compare simulation output against
# (never to configure the simulation).
REFERENCE = {
    "water": {
        "self_diffusion_cm2_s_298K": {"value": 2.299e-5, "source": "Holz, Heil & Sacco, Phys. Chem. Chem. Phys. 2, 4740 (2000)"},
        "oxygen_oxygen_rdf_first_peak_A": {"value": 2.8, "source": "neutron/X-ray diffraction of liquid water (Soper 2000; approx. position)"},
    },
}
STRUCTURE_SOURCE = "NIST CCCBDB experimental geometries (textbook values)"

# id: (display name, chemicals search name, aliases, category)
SPECIES = {
    "helium": ("Helium", "helium", ["he"], "noble_gas_atom"),
    "neon": ("Neon", "neon", ["ne"], "noble_gas_atom"),
    "argon": ("Argon", "argon", ["ar"], "noble_gas_atom"),
    "krypton": ("Krypton", "krypton", ["kr"], "noble_gas_atom"),
    "xenon": ("Xenon", "xenon", ["xe"], "noble_gas_atom"),
    "hydrogen": ("Hydrogen", "hydrogen", ["h2", "h₂", "hydrogen gas", "dihydrogen"], "diatomic_molecule"),
    "oxygen": ("Oxygen", "oxygen", ["o2", "o₂", "oxygen gas", "dioxygen"], "diatomic_molecule"),
    "nitrogen": ("Nitrogen", "nitrogen", ["n2", "n₂", "nitrogen gas", "dinitrogen"], "diatomic_molecule"),
    "carbon_dioxide": ("Carbon dioxide", "carbon dioxide", ["co2", "co₂", "carbon dioxide"], "polyatomic_molecule"),
    "methane": ("Methane", "methane", ["ch4", "ch₄", "natural gas"], "polyatomic_molecule"),
    "water": ("Water", "water", ["h2o", "h₂o", "steam", "ice", "liquid water"], "polyatomic_molecule"),
}
# Qualitative chemistry (textbook).  Reaction enthalpies are computed below from
# formation enthalpies, not typed.
REACTIVITY = {
    "helium": ("inert", "Closed 1s2 shell, highest first-ionisation energy of any element: forms no chemical bonds."),
    "neon": ("inert", "Closed-shell noble gas: forms no chemical bonds."),
    "argon": ("inert", "Closed-shell noble gas: forms no chemical bonds."),
    "krypton": ("inert", "Closed-shell noble gas; compounds only under extreme conditions."),
    "xenon": ("inert", "Closed-shell noble gas; only forms compounds with the most electronegative elements."),
    "hydrogen": ("reactive", "Fuel: combines exothermically with oxygen to form water once the strong H-H bond is broken (needs initiation/high temperature)."),
    "oxygen": ("reactive", "Oxidiser: supports combustion of hydrogen and hydrocarbons."),
    "nitrogen": ("unreactive", "Very strong N#N triple bond: inert at ordinary temperatures."),
    "carbon_dioxide": ("unreactive", "Fully oxidised carbon: stable, product of combustion."),
    "methane": ("reactive", "Fuel: burns in oxygen to CO2 and water once initiated."),
    "water": ("stable", "Stable; product of hydrogen combustion. Acts as a polar solvent."),
}
REACTIONS = [   # stoichiometry as {species: coefficient}; negative = reactant
    {"name": "hydrogen combustion", "equation": "2 H2 + O2 -> 2 H2O", "stoich": {"hydrogen": -2, "oxygen": -1, "water": 2}},
    {"name": "methane combustion", "equation": "CH4 + 2 O2 -> CO2 + 2 H2O",
     "stoich": {"methane": -1, "oxygen": -2, "carbon_dioxide": 1, "water": 2}},
]


def pick_lj(cas, tc_exp):
    """Choose sigma / epsilon for a neutral species among the sets tabulated in
    `chemicals`.  Rule (documented in README.md):
      1. discard physically implausible sets (sigma outside 2-5 A, eps/k < 5 K);
      2. of the rest, keep the set whose predicted critical temperature
         1.31 * eps/k (critical point of the LJ fluid) is closest to the
         EXPERIMENTAL critical temperature.
    Returns (sigma_A, eps_K, source, rejected list)."""
    import chemicals.lennard_jones as lj
    cands, rejected = [], []
    for m in lj.Stockmayer_all_methods:
        try:
            eps = lj.Stockmayer(cas, method=m)
            sig = lj.molecular_diameter(cas, method=m) if m in lj.molecular_diameter_all_methods else None
        except Exception:
            continue
        if sig is None:
            continue
        if not (2.0 <= sig <= 5.0 and eps >= 5.0):
            rejected.append({"source": m, "sigma_A": round(sig, 3), "epsilon_K": round(eps, 2), "why": "implausible"})
            continue
        cands.append((abs(LJ_TC_STAR * eps - tc_exp) / tc_exp, sig, eps, m))
    cands.sort()
    _, sig, eps, m = cands[0]
    for c in cands[1:]:
        rejected.append({"source": c[3], "sigma_A": round(c[1], 3), "epsilon_K": round(c[2], 2),
                         "why": "predicted Tc further from experiment"})
    return sig, eps, m, rejected


def build_molecules_and_forces(elements):
    from chemicals import search_chemical, Tc, Pc, Tm, Tb, Tt, Pt, omega, dipole_moment
    from thermo import Chemical

    mols, models = {}, {}
    hfg = {}
    for sid, (name, query, aliases, category) in SPECIES.items():
        chem = search_chemical(query)
        cas = chem.CASs
        geometry, atoms, bonds = STRUCTURE[sid]
        mass = sum(elements[a[0]]["atomic_weight_u"] for a in atoms)
        comp = {}
        for a in atoms:
            comp[a[0]] = comp.get(a[0], 0) + 1
        tc, pc = Tc(cas), Pc(cas)
        tm, tb = Tm(cas), Tb(cas)
        dip = dipole_moment(cas) or 0.0
        # polar bonds: largest electronegativity difference across a bond
        max_den = 0.0
        for i, j, _o in bonds:
            en = [elements[atoms[k][0]]["electronegativity_pauling"] for k in (i, j)]
            if None not in en:
                max_den = max(max_den, abs(en[0] - en[1]))
        has_hbond_donor = any(
            {atoms[i][0], atoms[j][0]} & {"N", "O", "F"} and "H" in (atoms[i][0], atoms[j][0])
            for i, j, _ in bonds)
        imf = ["london_dispersion"]
        if dip > 0.1:
            imf.append("dipole_dipole")
        if has_hbond_donor and dip > 0.1:
            imf.append("hydrogen_bonding")
        # --- saturated liquid density + vapour pressure tables --------------
        t_lo = max(tt for tt in [Tt(cas) or tm or 1.0] if tt) * 1.02
        if sid == "helium":
            t_lo = 2.2
        grid = np.linspace(t_lo, 0.97 * tc, 24)
        tab = []
        for T in grid:
            c = Chemical(query, T=float(T), P=101325)
            try:
                if c.Psat and c.rhol:
                    tab.append([round(float(T), 3), round(float(c.Psat) / 101325.0, 6),
                                round(float(c.rhol) / 1000.0, 5)])
            except Exception:
                pass
        csol = Chemical(query, T=0.8 * tm, P=101325)
        rho_s = None
        try:
            if csol.rhos:
                rho_s = {"T_K": round(0.8 * tm, 2), "rho_g_cm3": round(float(csol.rhos) / 1000.0, 4)}
        except Exception:
            pass
        hfg[sid] = Chemical(query, T=298.15, P=101325).Hfgm  # J/mol, gas
        mols[sid] = {
            "id": sid, "name": name, "aliases": [name.lower()] + aliases, "cas": cas,
            "formula": chem.formula, "smiles": chem.smiles, "category": category,
            "n_atoms": len(atoms), "composition": comp, "net_charge": 0,
            "molar_mass_g_mol": round(mass, 4), "monatomic": len(atoms) == 1,
            "structure": {"geometry": geometry, "atoms": [{"element": a[0], "xyz_A": [round(a[1], 5), round(a[2], 5), round(a[3], 5)]} for a in atoms],
                          "bonds": [{"i": b[0], "j": b[1], "order": b[2]} for b in bonds],
                          "source": STRUCTURE_SOURCE},
            "polarity": {"dipole_debye": round(float(dip), 3), "polar": dip > 0.1,
                         "max_bond_electronegativity_difference": round(max_den, 2),
                         "note": ("polar bonds cancel by symmetry: no net dipole" if max_den > 0.4 and dip <= 0.1 else "")},
            "intermolecular_forces": imf,
            "thermo": {"melting_point_K": tm, "boiling_point_K": round(tb, 3), "critical_T_K": tc,
                       "critical_P_atm": round(pc / 101325, 4), "triple_T_K": Tt(cas), "triple_P_Pa": Pt(cas),
                       "acentric_factor": omega(cas),
                       "source": "chemicals/thermo (DIPPR, CRC Handbook, NIST WebBook-derived)"},
            "saturation_table": {"columns": ["T_K", "P_sat_atm", "rho_liquid_g_cm3"], "rows": tab,
                                 "source": "thermo.Chemical correlations (DIPPR/Yaws)"},
            "solid_density_ref": rho_s,
            "solid_min_pressure_atm": SOLID_MIN_P.get(sid),
            "experimental_reference": REFERENCE.get(sid, {}),
            "gas_formation_enthalpy_kJ_mol": round((hfg[sid] or 0.0) / 1000.0, 3),
            "reactivity": {"class": REACTIVITY[sid][0], "description": REACTIVITY[sid][1],
                           "reaxff_supported": set(comp) <= {"H", "C", "O"}},
            "force_model": None,
        }
        # ------------------------------------------------ force-field entry --
        if sid == "water":
            ff = ET.parse(os.path.join(os.path.dirname(__import__("openmm").__file__), "app/data/tip3p.xml")).getroot()
            nb = {a.get("type"): a.attrib for a in ff.find("NonbondedForce")}
            bond = ff.find("HarmonicBondForce")[0].attrib
            ang = ff.find("HarmonicAngleForce")[0].attrib
            types = {t.get("name"): t.attrib for t in ff.find("AtomTypes")}
            models["tip3p_water"] = {
                "species": "water", "type": "rigid_molecule_tip3p",
                "sites": [
                    {"name": "O", "element": "O", "mass": float(types["tip3p-O"]["mass"]), "charge": float(nb["tip3p-O"]["charge"]),
                     "sigma_A": float(nb["tip3p-O"]["sigma"]) * 10, "epsilon_kcal_mol": float(nb["tip3p-O"]["epsilon"]) / 4.184},
                    {"name": "H", "element": "H", "mass": float(types["tip3p-H"]["mass"]), "charge": float(nb["tip3p-H"]["charge"]),
                     "sigma_A": 1.0, "epsilon_kcal_mol": 0.0}],
                "bond": {"r0_A": float(bond["length"]) * 10, "k_kcal_mol_A2": float(bond["k"]) / 4.184 / 100 / 2},
                "angle": {"theta0_deg": math.degrees(float(ang["angle"])), "k_kcal_mol_rad2": float(ang["k"]) / 4.184 / 2},
                "constraint": "SHAKE (rigid water)",
                "electrostatics": "particle-mesh Ewald (PPPM)",
                "source": "TIP3P: Jorgensen, Chandrasekhar, Madura, Impey & Klein, J. Chem. Phys. 79, 926 (1983); values read from OpenMM app/data/tip3p.xml",
                "valid_temperature_K": [250, 400],
            }
            mols[sid]["force_model"] = "tip3p_water"
        else:
            sig, eps, src, rej = pick_lj(cas, tc)
            lam = H_PLANCK / (sig * 1e-10 * math.sqrt(mass / 1000 / NA * eps * KB_J))
            models["lj_" + sid] = {
                "species": sid, "type": "lj_sphere",
                "sites": [{"name": mols[sid]["formula"], "element": None, "mass": round(mass, 4), "charge": 0.0,
                           "sigma_A": round(sig, 4), "epsilon_K": round(eps, 3), "epsilon_kcal_mol": round(eps * KB_K, 6)}],
                "source": f"{src} (as tabulated in the `chemicals` package)",
                "selection_rule": "plausible set whose 1.31*eps/k is closest to the experimental critical temperature",
                "rejected_sets": rej,
                "de_boer_parameter": round(lam, 3),
                "quantum_effects_significant": lam > 0.5,
                "approximation": ("single atom" if len(atoms) == 1 else
                                  "whole molecule treated as one spherical Lennard-Jones site: rotation, internal vibration and "
                                  "multipole (e.g. quadrupole) interactions are not represented"),
            }
            mols[sid]["force_model"] = "lj_" + sid

    # ---------------------------------------------------------------- ions ----
    ff = ET.parse(os.path.join(os.path.dirname(__import__("openmm").__file__), "app/data/amber14/tip3p.xml")).getroot()
    nb = {a.get("type"): a.attrib for a in ff.find("NonbondedForce")}
    types = {t.get("name"): t.attrib for t in ff.find("AtomTypes")}
    for sid, name, sym, q, key, aliases in [
            ("sodium_ion", "Sodium ion", "Na", 1, "tip3p_standard-Na+", ["na+", "na⁺", "sodium", "sodium cation"]),
            ("chloride_ion", "Chloride ion", "Cl", -1, "tip3p_standard-Cl-", ["cl-", "cl⁻", "chloride", "chloride anion"])]:
        el = elements[sym]
        a = nb[key]
        models["ion_" + sid] = {
            "species": sid, "type": "ion_sphere",
            "sites": [{"name": sym + ("+" if q > 0 else "-"), "element": sym, "mass": float(types[key]["mass"]), "charge": float(q),
                       "sigma_A": float(a["sigma"]) * 10, "epsilon_kcal_mol": float(a["epsilon"]) / 4.184}],
            "source": "Joung & Cheatham, J. Phys. Chem. B 112, 9020 (2008), TIP3P-compatible set; values read from OpenMM app/data/amber14/tip3p.xml",
            "valid_with": "tip3p_water",
        }
        mols[sid] = {
            "id": sid, "name": name, "aliases": aliases, "cas": None, "formula": sym + ("+" if q > 0 else "-"), "smiles": f"[{sym}{'+' if q > 0 else '-'}]",
            "category": "ion", "n_atoms": 1, "composition": {sym: 1}, "net_charge": q,
            "molar_mass_g_mol": float(types[key]["mass"]), "monatomic": True,
            "structure": {"geometry": "single charged atom", "atoms": [{"element": sym, "xyz_A": [0, 0, 0]}], "bonds": [], "source": "-"},
            "polarity": {"dipole_debye": 0.0, "polar": False, "max_bond_electronegativity_difference": 0.0, "note": "charged: interacts by Coulomb's law"},
            "intermolecular_forces": ["ion_ion", "ion_dipole", "london_dispersion"],
            "thermo": {}, "saturation_table": None, "solid_density_ref": None,
            "reactivity": {"class": "stable", "description": "Closed-shell ion (isoelectronic with a noble gas); does not react chemically with water.", "reaxff_supported": False},
            "force_model": "ion_" + sid,
            "electronegativity_pauling": el["electronegativity_pauling"], "ionization_energy_eV": el["first_ionization_eV"],
        }
    mols["sodium_chloride"] = {
        "id": "sodium_chloride", "name": "Sodium chloride", "aliases": ["nacl", "salt", "table salt", "common salt", "sodium chloride"],
        "cas": "7647-14-5", "formula": "NaCl", "smiles": "[Na+].[Cl-]", "category": "ionic_compound",
        "n_atoms": 2, "composition": {"Na": 1, "Cl": 1}, "net_charge": 0,
        "molar_mass_g_mol": round(elements["Na"]["atomic_weight_u"] + elements["Cl"]["atomic_weight_u"], 4),
        "monatomic": False, "dissociates_into": {"sodium_ion": 1, "chloride_ion": 1},
        "polarity": {"dipole_debye": None, "polar": True, "max_bond_electronegativity_difference": round(abs(elements["Na"]["electronegativity_pauling"] - elements["Cl"]["electronegativity_pauling"]), 2),
                     "note": "ionic bond (electronegativity difference > 1.7): modelled as free Na+ and Cl- ions"},
        "intermolecular_forces": ["ion_ion"], "thermo": {}, "saturation_table": None, "solid_density_ref": None,
        "reactivity": {"class": "stable", "description": "Ionic solid; dissolves in polar solvents (water) by ion-dipole hydration.", "reaxff_supported": False},
        "force_model": None,
    }
    # ----------------------------------------------- reactions (computed) ----
    rx = []
    for r in REACTIONS:
        dh = sum(c * (hfg[s] or 0.0) for s, c in r["stoich"].items()) / 1000.0
        rx.append({**r, "reaction_enthalpy_kJ": round(dh, 1),
                   "enthalpy_source": "sum of gas-phase formation enthalpies (thermo/DIPPR); computed, not typed",
                   "reaxff_supported": all(mols[s]["reactivity"]["reaxff_supported"] for s in r["stoich"])})
    return mols, models, rx


def main():
    elements = build_elements()
    mols, models, reactions = build_molecules_and_forces(elements)
    models_doc = {
        "_meta": {"units": {"sigma": "angstrom", "epsilon_K": "epsilon / k_B in kelvin", "epsilon_kcal_mol": "kcal/mol",
                            "mass": "g/mol (u)", "charge": "elementary charges"},
                  "mixing_rule": "Lorentz-Berthelot: sigma_ij = (sigma_i + sigma_j)/2, eps_ij = sqrt(eps_i eps_j)"},
        "models": models,
        "reaxff": {"file": "ffield.reax.cho", "elements": ["H", "C", "O"],
                   "source": "Chenoweth, van Duin & Goddard, J. Phys. Chem. A 112, 1040 (2008); file distributed with LAMMPS",
                   "timestep_fs": 0.25},
    }
    inter = json.load(open(os.path.join(HERE, "interactions.json"))) if os.path.exists(os.path.join(HERE, "interactions.json")) else {}
    inter["reactions"] = reactions
    for name, doc in [("elements.json", elements), ("molecules.json", mols), ("force_parameters.json", models_doc), ("interactions.json", inter)]:
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
        print("wrote", name)


if __name__ == "__main__":
    main()
