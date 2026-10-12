# AI-Assisted Molecular Dynamics Simulations from Natural-Language Descriptions

**B.Tech (CSE) — BCSE497J Project-I**
Shivani Srivastava (23BDS0085) · Faculty Guide: Dr. Vijayasherly V

A local, browser-based tool. You describe a chemical system in plain English
(*"Simulate helium at room temperature"*, *"100 water molecules at 300 K"*, *"hydrogen and
oxygen reacting at high temperature"*). The system identifies the substances, looks their
properties up in a **chemical knowledge base**, turns them into simulation parameters, runs a
real **molecular-dynamics** calculation with LAMMPS, and plays the computed trajectory in the
interactive 3D view — with the measured physics and a scientific explanation in the Messages panel.

Everything runs on one machine, offline.

---

## 1. The idea in one picture

```
 "Simulate helium at room temperature."
          │
          ▼
  AI / language understanding        backend/agent/            (rules + optional local LLM, verified)
          │   which substances? which numbers, with which units?
          ▼
  CHEMICAL KNOWLEDGE BASE            chemical_knowledge/*.json (elements, molecules, force fields, interactions)
          │   helium: noble gas, monatomic, M = 4.0026 u, sigma = 2.551 A, eps/k = 10.2 K, Tc = 5.2 K ...
          ▼
  Decide the physical model          backend/engine/plan.py    (phase, density, box, T*, dt, engine)
          │   validated by backend/validation/ + backend/knowledge/checks.py
          ▼
  MOLECULAR DYNAMICS ENGINE          LAMMPS (classical + ReaxFF reactive); C++ engine for hard spheres
          │   forces F = -dU/dr  →  Newton's equations  →  velocity-Verlet  →  positions
          ▼
  Analysis + explanation             backend/analysis/report.py
          │   measured T, P, Z, speeds, g(r), diffusion, energies … in plain language
          ▼
  EXISTING INTERFACE                 frontend/  (3D view, Energy plot, Messages)
```

**The AI does not do the science.** It decides *which substance and which numbers the user
meant*. The knowledge base supplies the chemistry; the MD engine does the physics.

## 2. What is calculated and what is only displayed

| Calculated by the engine (real physics) | Computed in the analysis from that output | Only displayed |
|---|---|---|
| forces from the potentials (Lennard-Jones, Coulomb/PPPM, bond-order) | temperature, pressure, compressibility | the 3D picture (positions come from the engine) |
| particle positions and velocities, from Newton's laws, velocity-Verlet | radial distribution function, coordination numbers | camera, colours (speed ramp) |
| potential, kinetic and total energy | mean-squared displacement → diffusion coefficient | |
| thermostat, boundary conditions (periodic or LJ walls) | Maxwell–Boltzmann test of the speeds, energy conservation | |
| bond breaking/forming (ReaxFF, reactive runs only) | phase diagnosed from density and mobility | |

Nothing in the browser generates motion. Every position, speed and energy came from LAMMPS
(or the project's C++ hard-sphere engine).

## 3. Repository layout

```
chemical_knowledge/        THE KNOWLEDGE BASE (see its README for sources and schema)
  elements.json  molecules.json  force_parameters.json  interactions.json
  build_dataset.py         regenerates the JSON from published datasets (developer tool)

backend/                   Python (FastAPI) — the conductor; it never does physics itself
  app.py                     /api/extract, /api/validate, /api/simulate + serves the frontend
  agent/                     natural language → parameters
    orchestrator.py            sentence → substances → knowledge base → decisions → parameters / questions
    quantities.py              "300 K", "27 °C", "1 atm", "5 nm", "10 ps" → SI-style values
    llm.py                     optional local LLM (Ollama) + the guard that verifies its output
  knowledge/                 reading the knowledge base
    kb.py                      loads the JSON, finds substances in text
    phase.py                   phase / density at (T, P) from the stored tables
    checks.py                  domain validation (ions need water, quantum limit, phase conflicts …)
  engine/                    configuring and running MD
    plan.py                    parameters + knowledge base → real-unit simulation plan
    lammps_case.py             writes the LAMMPS data file and input script
    lammps_parse.py            reads LAMMPS output
    runner.py                  runs the engine, analyses, returns the interface's data format
  analysis/report.py         measured quantities and the explanation text
  validation/schema.py       range checks on every parameter
  units.py                   unit conversions and reduced-unit definitions
  nlp/extractor.py           the original substance-free rule reader (kept as the baseline)

engine_cpp/                the project's own small C++ engine (Hard-Sphere model)
frontend/                  the interface (unchanged design)
tests/                     pytest suite (knowledge base, language layer, physics laws, engine)
```

## 4. How a sentence becomes a simulation

1. **Understand** (`agent/orchestrator.py`). The rule-based reader finds substance names
   (by name, formula or alias, including `H₂O`, `CO2`, `NaCl`), quantities *with units*, a
   container, a state word, and whether a reaction is asked for. If a local language model is
   configured (`MD_LLM_MODEL`, served by Ollama) it reads the sentence too; its draft is
   **verified** (`agent/llm.py`): every substance must exist in the knowledge base, every number
   needs a unit and a quote that really occurs in the sentence, otherwise it is discarded.
   The rules take precedence; the model only fills gaps. Without a model, the rules work alone.
2. **Identify and retrieve.** Each substance is resolved in `molecules.json`; its category,
   mass, polarity, intermolecular forces, force-field model and thermodynamic data are read.
3. **Decide the physics.** From the knowledge base: the phase at the requested T and P, the
   density (hence box size), the number of particles, the time step, the run length, whether
   reactive MD is possible. Defaults are applied **and reported** as "Assumption" lines in the
   Messages panel; if something cannot be defaulted safely the system **asks**
   (a line starting with `?`; add the answer to the description and press the button again).
4. **Validate** (`validation/schema.py` ranges, `knowledge/checks.py` chemistry). Examples:
   ions without water, unbalanced charge, solid helium at room temperature, a time step too
   large for rigid water, a cutoff larger than half the box, quantum effects too strong for
   classical MD (thermal de Broglie wavelength > 0.3 of the atomic size).
5. **Run** (`engine/`). LAMMPS integrates Newton's equations; or the C++ engine for hard spheres.
6. **Analyse and explain** (`analysis/report.py`), then play back in the existing interface.

## 5. Why helium behaves differently from water (what the knowledge base changes)

| Knowledge-base fact | Effect in the simulation |
|---|---|
| mass 4.0 u vs 18.0 u vs 39.9 u (Ar) | velocities: `<v> = sqrt(8kT/πm)`; helium is 3.16× faster than argon at the same T |
| helium ε/k = 10 K, water ε/k ≈ 77 K + charges | kT/ε = 29 for helium at 298 K: attraction negligible, ideal gas (Z = 1.00); water: Coulomb dominates, hydrogen-bonded liquid |
| helium non-polar, monatomic | only London dispersion (Lennard-Jones) |
| water polar, partial charges, bent | Coulomb forces with PPPM, SHAKE-rigid, hydrogen bonds emerge (O–O peak ≈ 2.8 Å) |
| Na⁺ / Cl⁻ charged | ion–dipole attraction; hydration shells of ~6 waters |
| critical/melting/boiling points | which phase, which density, which warnings |
| H₂ + O₂ reactive, elements covered by ReaxFF | reactive MD is possible (otherwise non-reactive MD, clearly stated) |

## 6. Chemical reactions — what is and is not claimed

Classical molecular dynamics keeps bonds fixed: molecules cannot react. A reaction is therefore
**not** faked by making particles disappear. For substances whose elements the reactive force
field (ReaxFF, CHO parameters of Chenoweth, van Duin & Goddard 2008) covers, a request such as
*"hydrogen and oxygen reacting at high temperature"* runs **reactive MD**: the same Newtonian
dynamics, but the forces come from a bond-order potential that lets bonds break and form.
Species are counted from the bond network over time (`fix reaxff/species`) and the Messages panel
reports the products and intermediates (e.g. H₂O, HO, H₂O₂, H).

Limits, also printed with every reactive run:
* ReaxFF is an empirical model, not quantum mechanics.
* A picosecond run only shows reactions at very high temperature (about 4000–5000 K, with the gas
  compressed); mechanisms and rates are those of an accelerated simulation, **not** of ordinary
  temperatures. In a test, 40 H₂ + 20 O₂ at 3000 K for 5 ps did not react; at 5000 K, H₂O formed.
* Elements outside H/C/O (e.g. nitrogen) are not covered: the system says so and runs non-reactive MD.
* The enthalpy of the reaction shown (e.g. −483.6 kJ for 2 H₂ + O₂ → 2 H₂O) is computed from tabulated
  formation enthalpies, not from the simulation.

## 7. The interface

The interface is unchanged in design and layout. What changed is what flows through it:

* The sliders are in the reduced Lennard-Jones units of the **substance named in the description**
  (`T* = kT/ε`, `ρ* = Nσ³/V`, `σ`, `τ`), so the same slider position means different real temperatures and
  lengths for different substances. The Messages panel gives the real values (kelvin, ångström, picoseconds).
  Density uses a logarithmic slider because it spans dilute gases to liquids; slider ranges were widened
  (T* to 200, container to 300σ) so realistic conditions are reachable. These are the only edits to
  `frontend/index.html` besides one sentence of help text.
* Solid / Liquid / Gas pick conditions from the knowledge base for the current substance.
* The Messages panel shows: what was identified, assumptions, the explanation chain
  (Chemical → Properties → Physics → Forces → Simulation → Observed), and any questions.
* The status box under the controls also shows chemistry warnings.
* The substance comes only from the description; slider moves re-run with the same substance.

## 8. Installing and running

**Requirements:** Python 3.10+, a C++ compiler (for the hard-sphere engine). No GPU, no internet at run time.

```bash
# 1. Python dependencies, including LAMMPS (the MD engine) and an MPI runtime it needs
python -m pip install -r backend/requirements.txt

# 2. Build the small C++ engine used for the Hard-Sphere model (once)
cd engine_cpp && bash build.sh && cd ..

# 3. Run the app
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
# open http://localhost:8000
```

Notes
* LAMMPS is found via `$LAMMPS_BIN`, then `lmp` on the PATH, then the one installed by the pip package.
  The pip wheel was tested on Linux; on Windows install LAMMPS from its official installer and set `LAMMPS_BIN`.
  The ReaxFF parameter file is found in the pip package or via `$LAMMPS_POTENTIALS`.
* Optional language model: `ollama serve`, then `export MD_LLM_MODEL=<a model you have pulled>`. Nothing leaves the
  machine. Not set → the rule-based reader is used. (The LLM path is covered by tests with a stand-in model; it has not been
  evaluated against a particular real model.)
* To regenerate the knowledge base from its sources: `pip install -r requirements-dev.txt` then
  `python chemical_knowledge/build_dataset.py`.

Tests:

```bash
python -m pytest tests/                 # fast: knowledge base, language layer, physics laws, engine (≈ 15 s)
RUN_SLOW=1 python -m pytest tests/      # adds water / ion hydration / reactive runs (a few minutes)
```

## 9. Measured results (from the test runs)

| System | Result | Reference |
|---|---|---|
| 250 He, 298 K, 1 atm | T = 298 K, P = 0.99 atm, **Z = 1.00**, mean speed 1264 m/s | ideal gas; √(8kT/πm) = 1255 m/s |
| He vs Ar, same T | speed ratio 3.16 | √(m_Ar/m_He) = 3.16 |
| liquid argon, 86 K | g(r) first peak 1.10 σ, 11.7 neighbours; D ≈ 1.5×10⁻⁵ cm²/s; energy drift 0.001 % | FCC-like first shell: 12 |
| 100 TIP3P water, 300 K | O–O first peak 2.74 Å; D ≈ 4.5×10⁻⁵ cm²/s | experiment 2.8 Å; TIP3P literature ≈ 5×10⁻⁵ (small box lowers it) |
| NaCl in water | Na⁺–O 2.35 Å, ≈ 5.7 waters; Cl⁻–O 3.15 Å | typical hydration shell of ~6 |
| 40 H₂ + 20 O₂, 5000 K, 5 ps | 26 H₂O formed (+ HO, H₂O₂, H) | — |
| hard spheres, liquid density | speed distribution → Maxwell–Boltzmann (KS distance 0.61 → 0.02) | H-theorem |

## 10. Limitations

* Small molecules (H₂, O₂, N₂, CO₂, CH₄) are single spherical Lennard-Jones sites; Lennard-Jones sets are
  fitted to gas properties, so liquid-phase accuracy is approximate (e.g. N₂ at 20 atm gives Z ≈ 1.06 where
  experiment gives ≈ 1.0).
* Water is TIP3P (about 2× too fast diffusion). 100 molecules in a 14 Å box show finite-size effects.
* Light atoms at low temperature are quantum: classical MD is flagged unreliable there.
* Walls (Lennard-Jones 9-3) are available for non-molecular systems only; water, ions and reactive
  systems use periodic boundaries (stated when requested otherwise).
* Gas density at the requested pressure uses the ideal-gas law; the simulation measures the actual pressure.
* A single run has statistical error (the report gives error bars where they are estimated); runs are short
  (≤ 20 τ ≈ 35–40 ps) so slow processes are not sampled.
* Supported substances: He, Ne, Ar, Kr, Xe, H₂, O₂, N₂, CO₂, CH₄, H₂O, Na⁺, Cl⁻ (NaCl as ions in water).
  Other elements and compounds are *known* (elements.json) but have no validated force field and are refused.
* Up to 500 particles (150 atoms for reactive runs).

## 11. GPU / CUDA

Not implemented in this project. LAMMPS can be built with GPU packages; that was not attempted, and no
CUDA code is part of this repository.
