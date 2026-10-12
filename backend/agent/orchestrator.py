"""
agent/orchestrator.py

Natural language  ->  validated simulation parameters.

    sentence
       |  1. understand   rule-based reader, plus (optionally) a local LLM whose
       |                  output is verified (agent/llm.py)
       |  2. identify     substance names -> entries of the chemical knowledge base
       |  3. retrieve     mass, sigma/epsilon, charges, melting/boiling/critical points...
       |  4. decide       phase, density, box, number of particles, run length --
       |                  from the knowledge base, not from the language model
       |  5. complete     defaults are applied AND reported; anything that cannot
       |                  be defaulted safely becomes a QUESTION for the user
       v
    {params, notes, extras, questions}   (the shape /api/extract returns)

`params` use the interface's reduced units of the reference substance; `extras`
carries the chemistry (components, reactive flag, state presets) that the
interface echoes back with every request, so a slider move keeps the substance.
"""

import re

from backend.agent import llm as llm_mod
from backend.agent import quantities as Q
from backend.knowledge import phase
from backend.knowledge.kb import get_kb, normalise_text
from backend.nlp import extractor as legacy
from backend.units import Reference, NA

DEFAULT_N_ATOMIC = 250
DEFAULT_N_WATER = 100
REACTIVE_UNITS = 20           # stoichiometric units: 20 x (2 H2 + O2) = 60 molecules
HIGH_TEMPERATURE_K = 5000.0   # what "high temperature" means for a ps-scale reactive run
DT_TARGET_FS = 2.0

_STOP = {"a", "an", "the", "some", "this", "that", "of", "particles", "particle", "atoms", "atom", "molecules", "molecule",
         "system", "box", "container", "liquid", "gas", "solid", "fluid", "simulation", "lennard", "hard", "sphere",
         "spheres", "points", "ions", "model", "crystal", "periodic", "random", "many", "few", "two", "three"}


# ----------------------------------------------------------------- understanding --
def _count_before(text, start):
    m = re.search(r"(\d+)\s*(?:(?:atoms?|molecules?|particles?|ions?|units?)\s+(?:of\s+)?)?$", text[:start])
    return int(m.group(1)) if m else None


def understand_rules(text):
    """Deterministic reading of the sentence."""
    kb = get_kb()
    t = normalise_text(text)
    mols, elems = kb.find_mentions(t)
    comps, seen = [], set()
    for m in mols:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        comps.append({"id": m["id"], "count": _count_before(t, m["start"]), "quote": m["quote"]})
    draft = {"components": comps, "elements": [e for e in elems], "temperature_K": Q.temperature_K(t),
             "pressure_atm": Q.pressure_atm(t), "duration_fs": Q.duration_fs(t), "box_A": Q.box_length_A(t),
             "density_g_cm3": Q.density_g_cm3(t), "timestep_fs": Q.timestep_fs(t), "reactive": None}
    m = re.search(r"\b(react\w*|combust\w*|burn\w*|ignit\w*|explo\w*|oxidi[sz]\w*)\b", t, re.IGNORECASE)
    if m:
        draft["reactive"] = True
        draft["reactive_quote"] = m.group(0)
    return draft


def understand(text, llm=None):
    """Rules first; the (verified) LLM draft only fills what the rules missed."""
    kb = get_kb()
    draft = understand_rules(text)
    notes = []
    raw = llm(text) if llm else llm_mod.ollama_chat(text)
    if raw is not None:
        d2, rejected = llm_mod.guard(raw, normalise_text(text), kb)
        have = {c["id"] for c in draft["components"]}
        for c in d2["components"]:
            if c["id"] not in have:
                draft["components"].append(c)
                notes.append(f"language model: substance '{c['quote']}' accepted after knowledge-base verification")
        for k in ("temperature_K", "pressure_atm", "duration_fs", "box_A"):
            if draft[k][0] is None and d2[k]:
                draft[k] = d2[k]
                notes.append(f"language model: {k} = {d2[k][0]:.4g} (from \"{d2[k][1]}\")")
        if d2["reactive"] and not draft["reactive"]:
            draft["reactive"] = True
        notes += [f"language model output rejected: {r}" for r in rejected]
    return draft, notes


# ---------------------------------------------------------------------- helpers --
def _ref_for(kb, mid):
    model = kb.model(mid)
    site = model["sites"][0]
    return Reference(site["sigma_A"], site["epsilon_kcal_mol"], kb.molecule(mid)["molar_mass_g_mol"])


def _number_density_A3(kb, mol, T, P, state):
    rho = phase.mass_density_g_cm3(mol, T, P, state)
    if rho is None:
        return None
    return rho * NA / mol["molar_mass_g_mol"] * 1e-24            # molecules per A^3


def _largest_remainder(weights, total):
    s = float(sum(weights))
    raw = [total * w / s for w in weights]
    out = [max(1, int(r)) for r in raw]
    while sum(out) < total:
        out[max(range(len(raw)), key=lambda i: raw[i] - out[i])] += 1
    return out


def _presets(kb, primary, ref):
    """Typical (T*, rho*) for the Solid / Liquid / Gas buttons of THIS substance."""
    mol = kb.molecule(primary)
    lj, hs = {}, {}
    for st in ("solid", "liquid", "gas"):
        tc = phase.typical_conditions(mol, st)
        if not tc:
            continue
        n = _number_density_A3(kb, mol, tc[0], tc[1], st)
        if n is None:
            continue
        ts = ref.T_to_star(tc[0])
        lj[st] = {"density": round(min(max(n * ref.sigma ** 3, 1e-4), 1.2), 6), "temperature": round(min(max(ts, 0.05), 200.0), 4)}
        hs[st] = {"particle_speed": round(min(max((3 * ts) ** 0.5, 0.05), 20.0), 4)}
    return {"lennard_jones": lj, "hard_sphere": hs}


# -------------------------------------------------------------------- main entry --
def interpret(text, llm=None):
    kb = get_kb()
    notes, questions, assumptions = [], [], []
    draft, llm_notes = understand(text, llm)
    notes += llm_notes
    params = {}
    t = normalise_text(text)

    # ---- model / state / container (shared language rules) -----------------------
    model, matched = legacy._find_keyword({"hard sphere": "hard_sphere", "billiard": "hard_sphere", "elastic collision": "hard_sphere",
                                           "elastic collisions": "hard_sphere", "lennard jones": "lennard_jones"}, t)
    params["model"] = model or "lennard_jones"
    state_word, state_quote = legacy._find_keyword({
        "solid": "solid", "crystal": "solid", "crystalline": "solid", "lattice": "solid", "frozen": "solid", "ice": "solid",
        "liquid": "liquid", "fluid": "liquid", "molten": "liquid", "gas": "gas", "gaseous": "gas", "vapor": "gas",
        "vapour": "gas", "steam": "gas"}, t)
    shape_text = re.sub(legacy._whole_word_pattern("hard sphere"), " ", t, flags=re.IGNORECASE)
    off_phrase = legacy._mentions_any(["periodic", "no container", "open space", "unbounded", "infinite", "bulk"], shape_text)
    on_phrase = legacy._mentions_any(["box", "container", "cube", "cubic", "cuboid", "sphere", "spherical", "jar", "vessel", "tank",
                                      "flask", "walls", "walled", "enclosed"], shape_text)
    container = bool(on_phrase) and not off_phrase
    shape, _ = legacy._find_keyword({"sphere": "sphere", "spherical": "sphere", "ball": "sphere", "round": "sphere", "flask": "sphere",
                                     "cube": "cuboid", "cubic": "cuboid", "cuboid": "cuboid", "box": "cuboid", "rectangular": "cuboid"}, shape_text)
    params["container_enabled"] = container
    params["container_shape"] = shape or "cuboid"

    # ---- identify the substances -----------------------------------------------------
    comps = draft["components"]
    expanded = []
    for c in comps:
        mol = kb.molecule(c["id"])
        if mol.get("dissociates_into"):
            n = c["count"]
            for ion, k in mol["dissociates_into"].items():
                expanded.append({"id": ion, "count": n * k if n else None, "quote": c["quote"]})
            notes.append(f"\"{c['quote']}\" is an ionic compound: modelled as dissolved {' + '.join(kb.molecule(i)['name'] for i in mol['dissociates_into'])} "
                         "(ionic bond: electronegativity difference "
                         f"{mol['polarity']['max_bond_electronegativity_difference']})")
        else:
            expanded.append(c)
    comps = expanded

    if not comps:
        elems = draft.get("elements") or []
        if elems:
            e = kb.element(elems[0]["symbol"])
            questions.append(f"{e['name']} ({e['symbol']}, Z = {e['atomic_number']}, {e['series'].lower()}) is in the knowledge base as an element, "
                             f"but there is no validated molecular-dynamics force field for it. Please name one of: {', '.join(kb.suggestions())}.")
        else:
            m = re.search(r"\b(?:simulate|model|run|show|study|create)\s+(?:a\s+|an\s+|the\s+|some\s+|\d+\s+)?([a-z][a-z\-]{3,})", t, re.IGNORECASE)
            if m and m.group(1).lower() not in _STOP:
                questions.append(f"I do not recognise '{m.group(1)}' as a substance in the chemical knowledge base. "
                                 f"Please name one of: {', '.join(kb.suggestions())}.")
        if not questions:
            comps = [{"id": "argon", "count": None, "quote": None}]
            assumptions.append("no substance named: using argon, the classic Lennard-Jones reference fluid")
        else:
            return {"params": {}, "notes": notes, "extras": {}, "questions": questions}

    for c in comps:
        if kb.model(c["id"]) is None:
            questions.append(f"'{kb.molecule(c['id'])['name']}' has no validated force-field model. Supported: {', '.join(kb.suggestions())}.")
    if questions:
        return {"params": {}, "notes": notes, "extras": {}, "questions": questions}

    ids = [c["id"] for c in comps]
    for c in comps:
        mol, model_ = kb.molecule(c["id"]), kb.model(c["id"])
        site = model_["sites"][0]
        notes.append(f"Identified: {mol['name']} ({mol['formula']}) — {mol['category'].replace('_', ' ')}"
                     + (f", from \"{c['quote']}\"" if c.get("quote") else "")
                     + f"; M = {mol['molar_mass_g_mol']:.3f} u, {'polar' if mol['polarity']['polar'] else 'non-polar'}, "
                       f"forces: {', '.join(i.replace('_', ' ') for i in mol['intermolecular_forces'])}")
        notes.append(f"Knowledge base → model: {model_['type']}, sigma = {site['sigma_A']:.3f} A, "
                     + (f"epsilon/k = {site['epsilon_K']:.1f} K" if 'epsilon_K' in site else f"epsilon = {site['epsilon_kcal_mol']:.4f} kcal/mol")
                     + (f", charge {site['charge']:+g} e" if site.get('charge') else "") + f" [{model_['source'].split(' (as')[0][:70]}]")

    primary = next((c["id"] for c in comps if kb.model(c["id"])["type"] in ("lj_sphere", "rigid_molecule_tip3p")), comps[0]["id"])
    pmol = kb.molecule(primary)
    ref = _ref_for(kb, primary)
    notes.append(f"Reduced units of the interface are those of {pmol['name']}: sigma = {ref.sigma:.3f} A, epsilon/k = {ref.eps_over_k:.1f} K, "
                 f"tau = {ref.tau_fs:.0f} fs")

    # ---- reactivity --------------------------------------------------------------------------
    reactive = bool(draft.get("reactive")) and len(ids) >= 2
    if draft.get("reactive") and len(ids) < 2:
        notes.append("A reaction needs at least two substances; running ordinary molecular dynamics.")
    if reactive and not all(kb.molecule(i)["reactivity"].get("reaxff_supported") for i in ids):
        notes.append("The reactive force field (ReaxFF CHO) does not cover every element involved: running NON-reactive molecular dynamics.")
        reactive = False

    # ---- ions need a solvent ----------------------------------------------------------------------
    has_ions = any(kb.molecule(i)["category"] == "ion" for i in ids)
    if has_ions and "water" not in ids:
        questions.append("Ions need a polar solvent. Add water, e.g. 'sodium chloride dissolved in water'.")

    # ---- temperature -----------------------------------------------------------------------------------
    T_K = None
    t_quote = None
    if draft["temperature_K"] and draft["temperature_K"][0] is not None:
        T_K, t_quote = draft["temperature_K"]
        notes.append(f"Temperature = {T_K:.2f} K (from \"{t_quote}\")")
    star_T, tq = legacy._find_number(r"(?:temperature|temp|\bT\*?)\s*(?:of|=|:|at)?\s*([\d.]+)", t)
    reduced_T = None
    if T_K is None and star_T is not None:
        reduced_T = star_T
        notes.append(f"Temperature T* = {star_T} (no unit given: read as reduced units, from \"{tq}\")")
    state_phys = None
    P_atm, p_quote = draft["pressure_atm"] if draft["pressure_atm"] else (None, None)
    if T_K is None and reduced_T is None:
        if reactive:
            if re.search(r"\b(high|hot|elevated|extreme)\s+temperature", t, re.IGNORECASE) or re.search(r"\bhot\b", t, re.IGNORECASE):
                T_K = HIGH_TEMPERATURE_K
                assumptions.append(f"\"high temperature\" taken as {T_K:.0f} K: picosecond-scale reactive runs only show reactions at very high "
                                   "temperature (accelerated kinetics; the mechanism at ordinary temperature may differ)")
            else:
                questions.append("At what temperature should the reaction be simulated? (Reactions in a picosecond simulation need roughly 4000–5000 K; "
                                 "add e.g. 'at 5000 K' to the description.)")
                T_K = HIGH_TEMPERATURE_K
        elif state_word:
            tc = phase.typical_conditions(pmol, state_word)
            if tc:
                T_K, P_atm = tc[0], P_atm or tc[1]
                assumptions.append(f"temperature {T_K:.1f} K and pressure {P_atm:g} atm chosen so that {pmol['name']} is a {state_word} (knowledge base)")
            else:
                assumptions.append(f"{pmol['name']} has no {state_word} state at ordinary pressure in the knowledge base; using room temperature")
        if T_K is None:
            T_K = 298.15
            assumptions.append("temperature not given: assumed room temperature, 298.15 K")
    if P_atm is None:
        P_atm = 1.0
        if draft["density_g_cm3"] is None and draft["box_A"] is None:
            assumptions.append("pressure not given: assumed 1 atm")
    if T_K is None and reduced_T is not None:
        T_K = ref.T_from_star(reduced_T)
    T_star = ref.T_to_star(T_K)

    # ---- phase of the main substance at these conditions ---------------------------------------------------
    solvent = kb.molecule("water") if "water" in ids else pmol
    state_phys = phase.state_at(solvent, T_K, P_atm) if solvent.get("thermo") else "gas"
    shown_state = {"supercritical": "gas"}.get(state_phys, state_phys)
    if state_phys == "unknown":
        shown_state = state_word or "liquid"
    if state_word and state_word != shown_state and (draft["temperature_K"] or reduced_T is not None) and not reactive:
        assumptions.append(f"you asked for a {state_word}, but {solvent['name']} at {T_K:.1f} K and {P_atm:g} atm is a {state_phys}; "
                           "the simulation uses the physical state at those conditions")
    if reactive:
        shown_state = "gas"
    notes.append(f"Knowledge base: {solvent['name']} at {T_K:.1f} K and {P_atm:g} atm is a {state_phys}")

    # ---- number of particles ------------------------------------------------------------------------------------
    explicit = [c["count"] for c in comps]
    total_hint = None
    if all(x is None for x in explicit):
        total_hint, _q = legacy._find_particle_count(t)
    if reactive:
        react = next((r for r in kb.interactions.get("reactions", []) if {k for k, v in r["stoich"].items() if v < 0} == set(ids)), None)
        weights = [abs(react["stoich"][i]) for i in ids] if react else [1] * len(ids)
        default_counts = [w * REACTIVE_UNITS for w in weights]
    elif "water" in ids:
        nw = DEFAULT_N_WATER
        default_counts = []
        for i in ids:
            if i == "water":
                default_counts.append(nw)
            elif kb.molecule(i)["category"] == "ion":
                default_counts.append(max(1, round(nw / 50)))          # about 1 mol/L
            else:
                default_counts.append(max(1, round(nw / 50)))
    else:
        default_counts = [DEFAULT_N_ATOMIC // len(ids)] * len(ids)
        default_counts[0] += DEFAULT_N_ATOMIC - sum(default_counts)
    if all(x is None for x in explicit):
        if total_hint:
            counts = _largest_remainder(default_counts, total_hint)
        else:
            counts = default_counts
            assumptions.append(f"number of particles not given: {sum(counts)} ({', '.join(f'{n} {kb.molecule(i)['name'].lower()}' for i, n in zip(ids, counts))})")
    else:
        k0 = next(i for i, x in enumerate(explicit) if x)
        scale = explicit[k0] / default_counts[k0]
        counts = [x if x else max(1, round(d * scale)) for x, d in zip(explicit, default_counts)]
    # ion charge balance
    charges = [kb.molecule(i).get("net_charge", 0) for i in ids]
    net = sum(q * n for q, n in zip(charges, counts))
    if net != 0 and any(q > 0 for q in charges) and any(q < 0 for q in charges):
        if any(c["count"] for c in comps if kb.molecule(c["id"])["category"] == "ion") and len({n for q, n in zip(charges, counts) if q}) > 1:
            questions.append(f"The requested ions are not electrically neutral (net charge {net:+d} e). Use equal numbers of positive and negative ions.")
    N = sum(counts)
    N = min(N, 500)
    if sum(counts) > 500:
        counts = _largest_remainder(counts, 500)
        assumptions.append("number of particles limited to 500 in this application")

    # ---- density / box ----------------------------------------------------------------------------------------------
    n_A3 = None
    mean_mass = sum(kb.molecule(i)["molar_mass_g_mol"] * n for i, n in zip(ids, counts)) / N
    if draft["box_A"] and draft["box_A"][0]:
        L_A = draft["box_A"][0]
        n_A3 = N / L_A ** 3
        notes.append(f"Box edge = {L_A:.1f} A (from \"{draft['box_A'][1]}\"): number density {n_A3:.4g} per A^3")
        container = True if container or on_phrase else container
    elif draft["density_g_cm3"] and draft["density_g_cm3"][0]:
        n_A3 = draft["density_g_cm3"][0] * NA / mean_mass * 1e-24
        notes.append(f"Density = {draft['density_g_cm3'][0]:.4g} g/cm3 (from \"{draft['density_g_cm3'][1]}\")")
    else:
        star_rho, rq = legacy._find_number(r"densit\w*\s*(?:of|=|:|at)?\s*([\d.]+)", t)
        if star_rho is not None:
            n_A3 = star_rho / ref.sigma ** 3
            notes.append(f"Density ρ* = {star_rho} (no unit given: reduced units, from \"{rq}\")")
        elif reactive:
            n_A3 = 0.33 / ref.sigma ** 3
            assumptions.append("reactive run: compressed to ρ* = 0.33 (about thousands of atm) so that molecules meet within picoseconds")
        else:
            if state_phys == "supercritical" or shown_state == "gas":
                n_A3 = P_atm * 101325.0 / (1.380649e-23 * T_K) * 1e-30
                if (state_phys == "unknown"):
                    n_A3 = None
            else:
                n_A3 = _number_density_A3(kb, solvent, T_K, P_atm, state_phys)
            if n_A3 is None:
                questions.append(f"The knowledge base has no density for {solvent['name']} as a {state_phys}; give a density or box size.")
                n_A3 = 0.8 / ref.sigma ** 3
    rho_star = n_A3 * ref.sigma ** 3
    rho_clamped = min(max(rho_star, 1e-4), 1.2)
    if abs(rho_clamped - rho_star) / rho_star > 1e-9:
        assumptions.append(f"density ρ* = {rho_star:.3g} is outside the interface range (0.0001–1.2): limited to {rho_clamped:.3g}")
    rho_star = rho_clamped
    box_sigma = (N / rho_star) ** (1.0 / 3.0)
    if container and params["container_shape"] == "sphere":
        box_sigma *= (6.0 / 3.141592653589793) ** (1.0 / 3.0)       # diameter of the sphere with the same volume as the cube
    walled = container and not ("water" in ids or has_ions or reactive)
    if walled:
        # Particles cannot reach the zone next to a Lennard-Jones wall (~0.8 sigma on each side), so the
        # container is made 1 sigma larger than N/rho would give: the density the particles actually
        # experience is then the one requested.
        box_sigma += 1.0
        notes.append("Walled container enlarged by 1 sigma to allow for the wall's excluded zone (so the effective density is the requested one)")
    box_sigma = min(max(box_sigma, 2.0), 300.0)

    # ---- time ----------------------------------------------------------------------------------------------------------------
    if draft["timestep_fs"] and draft["timestep_fs"][0]:
        dt_fs = draft["timestep_fs"][0]
    else:
        dt_fs = DT_TARGET_FS
    dt_star = min(max(dt_fs / ref.tau_fs, 0.0001), 0.005)
    if draft["duration_fs"] and draft["duration_fs"][0]:
        total_star = draft["duration_fs"][0] / ref.tau_fs
        notes.append(f"Run length = {draft['duration_fs'][0] / 1000:.3g} ps (from \"{draft['duration_fs'][1]}\")")
    else:
        legacy_t, lq = legacy._find_number(r"(?:for|over|during|run(?:ning)?\s+for|lasting)\s+(?:about\s+|roughly\s+)?([\d.]+)\s*(?:reduced\s+)?(?:time\s+units?|units?)\b", t)
        if legacy_t is not None:
            total_star = legacy_t
            notes.append(f"Run length = {legacy_t} tau (from \"{lq}\")")
        else:
            default_ps = 5.0 if reactive else 40.0
            total_star = default_ps * 1000.0 / ref.tau_fs
            assumptions.append(f"run length not given: {default_ps:g} ps")
    if total_star > 20.0:
        assumptions.append(f"run length limited to 20 tau = {20 * ref.tau_fs / 1000:.1f} ps (interface maximum)")
    total_star = min(max(total_star, 0.1), 20.0)

    # ---- assemble parameters ---------------------------------------------------------------------------------------------------
    params["state"] = shown_state if shown_state in ("solid", "liquid", "gas") else (state_word or "liquid")
    params["particle_count"] = N
    params["density"] = round(rho_star, 6)
    params["temperature"] = round(min(max(T_star, 0.05), 200.0), 4)
    params["particle_speed"] = round(min(max((3 * T_star) ** 0.5, 0.05), 20.0), 4)
    params["container_size"] = round(box_sigma, 3)
    params["timestep"] = round(dt_star, 5)
    params["total_time"] = round(total_star, 3)
    if T_star > 200 or T_star < 0.05:
        assumptions.append(f"T* = {T_star:.3g} is outside the interface range (0.05–200): limited")
    if "water" in ids or has_ions or reactive:
        params["container_enabled"] = False if not container else params["container_enabled"]
    extras = {"sim": {"components": [{"species": i, "fraction": float(n)} for i, n in zip(ids, counts)], "reactive": reactive},
              "presets": _presets(kb, primary, ref), "substance": pmol["name"], "assumptions": assumptions}
    for a in assumptions:
        notes.append("Assumption: " + a)
    notes.append(f"Resulting setup: {N} particles, T = {T_K:.1f} K (T* = {T_star:.3g}), ρ* = {rho_star:.4g}, "
                 f"{'reactive MD (ReaxFF)' if reactive else params['model'].replace('_', ' ')}")
    return {"params": params, "notes": notes, "extras": extras, "questions": questions}
