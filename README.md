# AI-Assisted Generation of CUDA-Based Molecular Dynamics Simulations from Natural-Language Descriptions

**B.Tech (CSE) — BCSE497J Project-I**
Shivani Srivastava (23BDS0085) · Faculty Guide: Dr. Vijayasherly V

A local, browser-based tool that turns a plain-English description into a real molecular
dynamics simulation, run by a compiled C++ engine, and shown back as an interactive 3D
animation of the actual particle trajectories. Every parameter the description sets can
then be adjusted with a slider, which re-runs the simulation.

Everything in this project runs on one machine, offline. No external AI API, no cloud
service, no GPU required.

---

## 1. What the project does

1. You describe a simulation in plain English (*"simulate 250 particles inside a box,
   behaving like a liquid"*) and press **Read Text & Run Simulation**.
2. A small local, rule-based language component reads the sentence and extracts
   structured parameters (particle count, state of matter, container, model, ...). What
   it understood is listed in the Messages panel and loaded into the sliders.
3. Those parameters — whether they came from the sentence or from a slider — are checked
   by a shared validator before anything runs, so an unrunnable request is rejected with
   a specific reason.
4. The validated parameters are handed to a **compiled C++ molecular dynamics engine**,
   which actually computes the physics: forces, collisions, integration, boundaries.
5. The engine writes the real particle positions over time and the real system energy
   to two files.
6. The frontend loads those files and plays them back: a rotate/zoom 3D view of the
   actual particle trajectories, and a chart of the actual energy over time.

Nothing about the visualization is invented in the browser — every particle position and
every energy value came out of the C++ engine.

## 2. Architecture

```
frontend/                  Plain HTML/CSS/JS. No framework, no build step, no web fonts.
  index.html                A single desktop-style window: a column of tool panels on
                             the left, the viewport on the right, Messages along the
                             bottom.
  css/style.css              All layout and styling. Flat grey panels, system fonts.
  js/api.js                  Calls the backend's three endpoints.
  js/scene3d.js               Hand-written 3D renderer: rotate/zoom camera, container
                               mesh, balls drawn at true radius, speed colouring, bonds.
  js/trajectoryPlayer.js       Plays back the REAL trajectory frames through scene3d.js,
                               and works out which particles are close enough to bond.
  js/energyChart.js            Draws the REAL energy-vs-time chart, with a hover readout.
  js/app.js                    Wires the window together: reads the controls, calls the
                               API, feeds results to the viewport and the chart.

backend/                   Python (FastAPI). The "conductor" -- it never does physics itself.
  app.py                     The three HTTP endpoints + serves the frontend.
  nlp/extractor.py            Natural-language -> structured parameters (local, rule-based).
  validation/schema.py        Parameter range + feasibility checks (pydantic).
  engine/runner.py             Writes a config file, runs the compiled engine, reads results.
  config/config_defaults.py    Solid/liquid/gas density & temperature presets.

engine_cpp/                 The actual simulation. C++, compiled once, reused for every run.
  src/particle.h              One particle's position/velocity/force.
  src/config.h/.cpp            Reads the "key=value" config file the backend writes.
  src/initialize.h/.cpp        Builds the starting arrangement for solid/liquid/gas.
  src/forces.h/.cpp            Lennard-Jones forces, gravity, hard-sphere collisions.
  src/boundary.h/.cpp          Periodic wrap, reflective cuboid, reflective sphere.
  src/integrator.h/.cpp         Velocity-Verlet time-stepping.
  src/trajectory_writer.h/.cpp  Writes trajectory.json and energy.csv.
  src/main.cpp                  Orchestrates the above into the actual simulation loop.
                                 Takes an optional random seed so a run can be repeated
                                 exactly (the tests rely on this; 0 = seed from the clock).
  build.sh                    Compiles everything into ./md_engine.

configs/                    Example "key=value" config files you can run by hand.
tests/                      pytest suite -- 35 tests covering validation, extraction, and
                             the compiled engine (states of matter, energy conservation,
                             reproducibility).
deliverables/               The Review-2 report and presentation, plus the matplotlib
                             scripts that generate every figure in them.
runs/                       Created at runtime -- one folder per simulation request.
```

**The flow, end to end:**

```
User types a description, or moves a slider
        |
        v
POST /api/extract   (description only)   --> nlp/extractor.py
        |
        v
POST /api/validate / POST /api/simulate  --> validation/schema.py
        |                                      (one validator, whichever the
        |                                       values came from)
        v
engine/runner.py writes config.txt, runs engine_cpp/md_engine
        |
        v
md_engine.exe actually computes the simulation, writes
runs/<id>/trajectory.json and runs/<id>/energy.csv
        |
        v
Backend reads those files and returns them as the API response
        |
        v
Frontend: scene3d.js + trajectoryPlayer.js play the real trajectory,
          energyChart.js plots the real energy series
```

## 3. Natural-language input

`backend/nlp/extractor.py` is a **rule-based (regex + keyword) extractor**, not a neural
language model. This was a deliberate choice for this prototype, not a shortcut:

- it needs no model download and no extra compiler toolchain, so the whole project sets
  up in minutes on any machine;
- for a small, fixed vocabulary of simulation terms ("liquid", "sphere", "300 particles",
  "temperature of 1.2", ...), a handful of regular expressions cover the same ground a
  tiny language model would, and every match is easy to read and explain line by line;
- it satisfies the actual requirement -- everything runs locally, with no network call
  and no external API.

It reads one sentence and returns whichever fields it recognises (particle count, model,
state of matter, container on/off, container shape, density, temperature/speed, timestep,
total time). Anything it doesn't find is left for the shared defaults / state presets to
fill in -- and everything it does find is loaded into the sliders on the left, where it
stays fully editable before and after a run.

Three rules keep the matching honest. Each one is there because the simpler version of it
got a real sentence wrong, and each has a regression test in `tests/test_extractor.py`:

1. **Whole words only.** Plain substring matching found "sphere" inside "atmosphere", so
   "a gas in the atmosphere" came back as a spherical container.
2. **Negation is respected.** "not solid but liquid" used to return *solid*, because
   "solid" appears first in the sentence.
3. **A number is only read when its own keyword sits next to it.** The run-length pattern
   keyed off the bare word "for", so "run a simulation for 300 particles" was read as a
   300-time-unit run.

It also reads written-out numbers ("two hundred particles"), and it returns a plain-English
note for every decision it made -- which the Messages panel prints, so how a sentence was
read is visible rather than something to be taken on trust.

**Upgrade path:** because the rest of the system only ever calls
`extract_parameters(text) -> dict`, swapping in a real small local language model later
(e.g. a quantized model run through `llama.cpp`) means replacing the inside of that one
function -- nothing else in the backend or frontend would need to change.

## 4. Adjusting the parameters directly

The **Simulation** panel holds the same fields as sliders: particle count, interaction
model, state of matter, boundary (periodic / cuboid / sphere), container size, density
and temperature (or particle speed for Hard-Sphere), timestep, and run length. Each
slider's range is the validator's own range, so a control cannot be pushed to a value the
backend would reject.

Sliders and the typed description both end up as the same parameter dictionary, checked
by the same validator -- there is exactly one definition of "a valid request" in this
project.

Because the engine runs a simulation and then hands back the finished result, a slider
cannot alter a run that is already playing. So when a slider is released, the app re-runs
the simulation with the new value and swaps in the new result -- that is what makes a
slider change visible rather than merely noted. The "Re-run automatically when a slider
changes" checkbox turns this off for long runs; the **Run Simulation** button then does it
on demand. A 250-particle, 3-time-unit run takes roughly 4 seconds on the development
machine; the 500-particle, 20-time-unit worst case is far slower.

## 5. The C++ simulation engine

The engine is a single compiled program (`engine_cpp/md_engine`) that reads a small
`key=value` config file and writes `trajectory.json` + `energy.csv`. It is **not**
recompiled per request -- only the config changes between runs, which keeps the actual
simulation code fixed, hand-verified, and easy to trust.

It supports two interaction models:

- **Lennard-Jones** — the standard MD potential (attraction at medium range, repulsion at
  short range), integrated with velocity-Verlet. This is a direct continuation of the
  hand-written, hand-debugged C++ code written during a 2024 summer internship at IIT
  Bombay (that internship's report is not part of this repository) -- the force
  calculation and lattice initialization are the same proven physics, refactored to take
  runtime parameters instead of hardcoded constants, with container/state-of-matter
  support added.
- **Hard-Sphere** — rigid spheres with no potential energy, moving in straight lines and
  bouncing elastically off each other and the walls. Simpler than Lennard-Jones (no
  pairwise force calculation), and its total energy is *exactly* conserved by the
  collision math, which makes it a clean, easy-to-explain correctness check on its own.

and two boundary types:

- **Periodic** (container off) — particles that leave one side of the (invisible) box
  reappear on the other side, exactly like the original 2024 code.
- **Container** (on) — a real, visible boundary. Two shapes are supported:
  - **Cuboid** — particles bounce elastically off six flat walls.
  - **Sphere** — particles bounce elastically off a spherical shell.

### How solid / liquid / gas are represented

This is real physics, not three cosmetic presets:

| State | What actually happens |
|---|---|
| **Solid** | A tight, ordered lattice (spacing derived from the requested density). No gravity is applied, so the block simply stays where it starts and vibrates in place -- a real, low-temperature Lennard-Jones lattice is naturally stable on its own. |
| **Liquid** | A looser, jittered lattice confined to roughly the bottom of the container at start, **plus a small constant gravity and a tiny velocity-damping term applied only in this state**, for as long as a container is enabled. Since the walls and Lennard-Jones forces are perfectly elastic, gravity alone would just make the block bounce forever at the same height -- the damping term stands in for the energy real liquids lose to internal friction, which is what makes it actually settle instead of bouncing. |
| **Gas** | Particles placed randomly through the *entire* available volume (rejection-sampled so no two start on top of each other), with a higher starting speed and no gravity -- so it visibly fills the whole container rather than clustering. |

### How the three states are told apart on screen

The physics above puts the particles in genuinely different places, but position alone is
a weak cue -- a screen full of identical dots looks much the same whatever it is doing.
Three things are drawn from real engine output to make the difference readable, all
toggled from the **Display Types** panel:

- **Ball size is the real particle size.** At 1.0x each ball is drawn at its true radius
  (0.5 sigma), so how tightly a state packs is visible directly. The default 0.55x shrinks
  them so the bonds underneath show through.
- **Colour is the particle's real speed.** The engine writes each particle's speed into
  `trajectory.json` alongside its position, and the viewer maps it onto a single
  dark-to-light blue ramp. A cold solid is uniformly dark, a hot gas is bright, a liquid
  is mixed.
- **A bond is drawn between any two particles closer than the cut-off** (1.35 sigma by
  default). This is the clearest of the three: a solid shows a connected lattice, a liquid
  a dense shifting cluster, a gas almost nothing.

The readout strip under the viewport puts a number on it: **mean neighbours per particle**.
Measured on a 250-particle run in a 10-sigma box, that is about 5.0 for the solid (a
simple-cubic lattice), 5.7 for the liquid (disordered, but compressed by gravity), and 1.9
for the gas.

Because gravity and damping only apply to the liquid state, its energy plot is expected
to drift downward as it settles -- that's the system doing real dissipative work, not a
bug. The gas state and any periodic (container-off) run are genuine NVE simulations, and
their total energy stays flat, which is the actual correctness proof: `tests/test_engine_smoke.py`
checks this directly (total energy drift under 0.5 reduced units over a full run).

## 6. Validation

`backend/validation/schema.py` checks, before anything is simulated:

- particle count (1–500 for this prototype), density, temperature/speed, timestep, and
  total time are all inside physically sensible ranges;
- the interaction cutoff is smaller than half the box size (container size, or the
  density-derived box when periodic) -- otherwise a particle could interact with its own
  periodic or reflected image, which would silently double-count forces.

Both the typed description and the sliders go through this exact function, via
`/api/validate` (checked live as a slider moves) and again inside
`/api/simulate` (so nothing invalid ever reaches the engine, even if the frontend check
was skipped).

## 7. Frontend <-> backend communication

Three JSON endpoints, called from `frontend/js/api.js`:

- `POST /api/extract` — `{ text }` -> `{ params, notes }` (draft parameters from a
  sentence, plus a line-by-line account of how it was read)
- `POST /api/validate` — parameters -> `{ valid, errors, params }`
- `POST /api/simulate` — parameters -> `{ params, trajectory, energy, run_seconds }`

`trajectory` is the parsed `trajectory.json` (box size, sigma, container shape, and a list
of per-particle `[x, y, z, speed]` entries for each saved frame); `energy` is the parsed
`energy.csv` rows. `frontend/js/trajectoryPlayer.js` normalizes those real coordinates
into the fixed `[-1, 1]` space the 3D renderer draws, and steps through the real frames
on playback -- there is no random or simulated motion anywhere in the frontend.

## 8. Installing and running

**Requirements:** Python 3.10+, a C++ compiler (g++/MinGW on Windows, or any g++/clang on
Linux/macOS). No GPU, no internet connection needed at runtime.

```bash
# 1. Build the simulation engine (once)
cd engine_cpp
bash build.sh          # produces ./md_engine (or md_engine.exe on Windows)
cd ..

# 2. Install backend dependencies
python -m pip install -r backend/requirements.txt

# 3. Run the app
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# 4. Open it
# http://localhost:8000
```

Running the tests -- 35 of them, all passing:

```bash
python -m pip install pytest
python -m pytest tests/
```

(`tests/test_engine_smoke.py` is skipped automatically if the engine hasn't been built
yet. Those tests pin the engine's random seed, so a run that passes once passes every
time -- without that, the starting arrangement is randomised and results vary run to run.)

## 9. Current CPU implementation

Everything above runs on the CPU. The Lennard-Jones force loop is the O(N²) pairwise
calculation used in the original 2024 code -- fine for this prototype's range (up to ~500
particles, a few reduced time units), which finishes in a few seconds on a normal laptop.

## 10. Future extension: CUDA / GPU acceleration

The long-term goal (stated in the original project proposal) is to accelerate the same
simulation with CUDA. This prototype's engine is deliberately structured to make that a
contained change, not a rewrite:

- `forces.cpp`'s `compute_lj_forces()` is the one O(N²) hotspot -- exactly the function
  that would become a CUDA kernel (per-particle force accumulation is embarrassingly
  parallel, one thread per particle, the same structure attempted in the 2024
  internship's CUDA port).
- `boundary.cpp` and `integrator.cpp` are both already per-particle, independent
  operations -- also natural CUDA kernels.
- `main.cpp` only orchestrates *which* function runs each step; swapping the CPU
  implementations of `compute_lj_forces`, `apply_*_boundary`, and `begin_step`/`finish_step`
  for CUDA equivalents (with host/device memory transfer wrapping the same call sites)
  would not require changing the config format, the file outputs, the backend, or the
  frontend at all.
- The 2024 internship CUDA code is a useful starting reference for that port, though it
  is explicitly documented there as not yet compiling (a missing `*` in a `cudaMalloc`
  cast, and unresolved `atomicAdd(double)` portability) -- real debugging work, not a
  drop-in replacement, which is why it's future work rather than part of this prototype.

No GPU or CUDA toolkit is required to build, run, or demonstrate this project today.
#   p r o j e c t - 1 - - - t y p e - 2  
 