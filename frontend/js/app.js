// app.js
//
// Wires the interface together: reads what the user typed or set, sends
// it to the local backend, and shows back whatever the backend (and, for
// a real run, the C++ engine) actually returned. No particle position and
// no energy value in this file is invented here -- everything displayed
// came from an API response.

(function () {
  "use strict";

  // Mirrors backend/config/config_defaults.py, purely so picking a state
  // moves the sliders straight away. The backend is still the authority:
  // /api/validate and /api/simulate re-check everything that is sent.
  const STATE_PRESETS = {
    lennard_jones: {
      solid: { density: 1.0, temperature: 0.2 },
      liquid: { density: 0.8, temperature: 1.0 },
      gas: { density: 0.2, temperature: 2.5 },
    },
    hard_sphere: {
      solid: { particle_speed: 0.3 },
      liquid: { particle_speed: 1.2 },
      gas: { particle_speed: 2.4 },
    },
  };

  // Every parameter slider in one table: which elements it owns, how its
  // value is read, and how it is written out. Adding a parameter to the
  // interface means adding one row here and one block of markup.
  const SLIDERS = {
    particle_count: { input: "s-n", out: "v-n", read: (v) => parseInt(v, 10), show: (v) => String(v) },
    // density spans four orders of magnitude (a dilute gas to a dense liquid), so the slider runs on log10(rho*)
    density:        { input: "s-density", out: "v-density", read: (v) => Math.pow(10, parseFloat(v)), write: (v) => Math.log10(v),
                      show: (v) => (v >= 0.1 ? v.toFixed(2) : v.toPrecision(2)) },
    temperature:    { input: "s-temp", out: "v-temp", read: parseFloat, show: (v) => v.toFixed(2) },
    particle_speed: { input: "s-speed", out: "v-speed", read: parseFloat, show: (v) => v.toFixed(2) },
    container_size: { input: "s-size", out: "v-size", read: parseFloat, show: (v) => v.toFixed(1) },
    timestep:       { input: "s-dt", out: "v-dt", read: parseFloat, show: (v) => v.toFixed(4) },
    total_time:     { input: "s-tmax", out: "v-tmax", read: parseFloat, show: (v) => v.toFixed(1) },
  };

  const DEFAULTS = {
    model: "lennard_jones", state: "liquid", boundary: "cuboid",
    particle_count: 250, density: 0.8, temperature: 1.0, particle_speed: 1.2,
    container_size: 10.0, timestep: 0.001, total_time: 3.0,
  };

  // The chemistry the description resolved to (substances, reactive flag, state presets). The sliders only
  // hold numbers, so this is echoed back with every request to keep the substance the user asked for.
  let extras = null;

  let lastGraphs = {};         // measured-property graphs of the run on screen (Analysis tab)
  let analysisChoice = "thermo";
  let hasRun = false;          // has a simulation ever completed?
  let running = false;         // is one in flight right now?
  let rerunTimer = null;
  let draggingFrame = false;

  function $(id) { return document.getElementById(id); }

  // ---------------- the Messages log ----------------

  function log(text, kind) {
    const el = $("message-log");
    const line = document.createElement("div");
    if (kind) line.className = kind;
    line.textContent = text;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  }

  // ---------------- reading and writing the controls ----------------

  function radioValue(name) {
    const checked = document.querySelector(`input[name="${name}"]:checked`);
    return checked ? checked.value : null;
  }

  function setRadio(name, value) {
    const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (el) el.checked = true;
  }

  function sliderValue(key) {
    const spec = SLIDERS[key];
    return spec.read($(spec.input).value);
  }

  function setSlider(key, value) {
    const spec = SLIDERS[key];
    const input = $(spec.input);
    // Clamped to the slider's own range, which is set from the validator's
    // limits -- so a number picked out of the description can never push a
    // control past what the backend would accept.
    const raw = spec.write ? spec.write(value) : value;
    const clamped = Math.min(parseFloat(input.max), Math.max(parseFloat(input.min), raw));
    input.value = clamped;
    refreshSliderLabel(key);
    return clamped;
  }

  function refreshSliderLabel(key) {
    const spec = SLIDERS[key];
    $(spec.out).textContent = spec.show(spec.read($(spec.input).value));
  }

  function gatherParams() {
    const boundary = radioValue("boundary");
    return Object.assign({
      model: radioValue("model"),
      state: radioValue("state"),
      container_enabled: boundary !== "periodic",
      container_shape: boundary === "sphere" ? "sphere" : "cuboid",
      particle_count: sliderValue("particle_count"),
      container_size: sliderValue("container_size"),
      density: sliderValue("density"),
      temperature: sliderValue("temperature"),
      particle_speed: sliderValue("particle_speed"),
      timestep: sliderValue("timestep"),
      total_time: sliderValue("total_time"),
    }, extras && extras.sim ? extras.sim : {});
  }

  // Loads whatever the description produced into the controls. Anything
  // the sentence didn't mention is simply left as it is.
  function applyParamsToControls(params) {
    if (params.model) setRadio("model", params.model);
    if (params.state) setRadio("state", params.state);
    if (typeof params.container_enabled === "boolean") {
      setRadio("boundary", params.container_enabled
        ? (params.container_shape === "sphere" ? "sphere" : "cuboid")
        : "periodic");
    }
    Object.keys(SLIDERS).forEach((key) => {
      if (params[key] != null) setSlider(key, params[key]);
    });
    syncModelFields();
  }

  function applyStatePreset() {
    const model = radioValue("model"), state = radioValue("state");
    // presets for the substance in the description come from the knowledge base; generic ones otherwise
    const fromKb = extras && extras.presets && extras.presets[model] && extras.presets[model][state];
    const preset = fromKb || STATE_PRESETS[model][state];
    Object.keys(preset).forEach((key) => setSlider(key, preset[key]));
  }

  // Density/temperature belong to Lennard-Jones; particle speed belongs to
  // Hard-Sphere. Only the ones the chosen model actually uses are shown.
  function syncModelFields() {
    const model = radioValue("model");
    document.querySelectorAll(".ctl[data-model]").forEach((el) => {
      el.hidden = el.dataset.model !== model;
    });
    $("s-size").closest(".ctl").hidden = radioValue("boundary") === "periodic";
  }

  // ---------------- validation (the same check /api/simulate runs) ----------------

  let validateTimer = null;

  function scheduleValidate() {
    clearTimeout(validateTimer);
    validateTimer = setTimeout(validateNow, 250);
  }

  async function validateNow() {
    const box = $("validate-status");
    try {
      const { valid, errors, warnings, params } = await API.validateParameters(gatherParams());
      if (valid) {
        const boxLength = params.container_enabled
          ? params.container_size
          : Math.cbrt(params.particle_count / params.density);
        box.className = "status good";
        box.textContent = `Valid. Box edge ${boxLength.toFixed(2)}σ, cut-off ${params.cutoff}σ ` +
                          `(must stay under half the box, ${(boxLength / 2).toFixed(2)}σ).`;
        if (warnings && warnings.length) {
          box.innerHTML = escapeHtml(box.textContent) + `<ul>${warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`;
        }
      } else {
        box.className = "status bad";
        box.innerHTML = `<strong>Cannot run — ${errors.length} problem${errors.length > 1 ? "s" : ""}:</strong>` +
                        `<ul>${errors.map((e) => `<li>${escapeHtml(e)}</li>`).join("")}</ul>`;
      }
      return valid;
    } catch (e) {
      box.className = "status bad";
      box.textContent = "Cannot reach the local backend — is the server running?";
      return false;
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // ---------------- the 3D view and playback ----------------

  const scene = new Scene3D($("particle-canvas"));
  const player = new TrajectoryPlayer(scene);
  const chart = new EnergyChart($("energy-canvas"));
  const analysisA = new PlotChart($("analysis-canvas-a"));
  const analysisB = new PlotChart($("analysis-canvas-b"));
  const sweepA = new PlotChart($("sweeps-canvas-a"));
  const sweepB = new PlotChart($("sweeps-canvas-b"));

  function animationLoop() {
    player.tick();
    scene.draw();
    updateReadout();
    requestAnimationFrame(animationLoop);
  }

  function updateReadout() {
    const total = player.frameCount();
    $("ro-frame").textContent = total ? `${player.frameIndex + 1} / ${total}` : "0 / 0";
    $("v-frame").textContent = total ? `${player.frameIndex + 1} / ${total}` : "0 / 0";
    if (!draggingFrame && total) $("s-frame").value = player.frameIndex;

    $("ro-neigh").textContent = total ? player.stats.neighbours.toFixed(1) : "—";
    $("ro-speed").textContent = total ? player.stats.meanSpeed.toFixed(2) : "—";
  }

  // ---------------- running a simulation ----------------

  async function runSimulation(reason) {
    if (running) return;
    const params = gatherParams();

    if (!(await validateNow())) {
      log("Run cancelled — the parameters are not valid (see the box above the View panel).", "err");
      return;
    }

    running = true;
    $("run-btn").disabled = true;
    $("read-run-btn").disabled = true;
    log(`Running: ${params.state}, ${params.model}, ${params.particle_count} particles, ` +
        `${params.container_enabled ? params.container_shape : "periodic"}, t = ${params.total_time}` +
        (reason ? `  [${reason}]` : ""));

    try {
      const result = await API.runSimulation(params);
      player.load(result.trajectory);
      chart.setData(result.energy);
      lastGraphs = result.graphs || {};
      showAnalysis();

      $("s-frame").max = Math.max(0, result.trajectory.frames.length - 1);
      $("s-frame").value = 0;
      $("ro-state").textContent = (result.properties && result.properties.label) || result.params.state;
      $("ro-n").textContent = result.params.particle_count;

      player.playing = true;
      $("play-btn").textContent = "Pause";
      hasRun = true;

      log(`Done in ${result.run_seconds}s — ${result.trajectory.frames.length} frames, ` +
          `${result.energy.length} energy points.`, "ok");
      log(`Mean neighbours per particle: ${player.stats.neighbours.toFixed(1)} ` +
          `(solid packs tightest, a gas has almost none).`);
      // measured quantities and the scientific explanation: chemical -> properties -> physics -> forces -> observed
      (result.report || []).forEach((line) => log("  " + line));
    } catch (e) {
      log("Simulation failed: " + e.message, "err");
    } finally {
      running = false;
      $("run-btn").disabled = false;
      $("read-run-btn").disabled = false;
    }
  }

  // A slider was let go. If a run already exists, redo it with the new
  // value so the change is actually visible rather than just noted.
  function scheduleRerun(what) {
    if (!$("auto-rerun").checked || !hasRun) return;
    clearTimeout(rerunTimer);
    rerunTimer = setTimeout(() => runSimulation(what + " changed"), 450);
  }

  // ---------------- reading the description ----------------

  async function readAndRun() {
    const text = $("f-text").value.trim();
    if (!text) { log("Nothing to read — the description box is empty.", "err"); return; }

    $("read-run-btn").disabled = true;
    try {
      const { params, notes, extras: found, questions } = await API.extractParameters(text);
      log("Reading description locally…");
      (notes || []).forEach((note) => log("  " + note));
      // something essential is missing: ask, and wait for the user to add it to the description
      if (questions && questions.length) {
        questions.forEach((q) => log("? " + q, "err"));
        log("Add the answer to the description and press Read Text & Run Simulation again.");
        return;
      }
      extras = found;
      applyParamsToControls(params);
      await validateNow();
      await runSimulation("from description");
    } catch (e) {
      log("Could not read that description: " + e.message, "err");
    } finally {
      $("read-run-btn").disabled = false;
    }
  }

  // ---------------- wiring ----------------

  // parameter sliders: live label while dragging, re-run once released
  Object.keys(SLIDERS).forEach((key) => {
    const input = $(SLIDERS[key].input);
    input.addEventListener("input", () => { refreshSliderLabel(key); scheduleValidate(); });
    input.addEventListener("change", () => scheduleRerun(key.replace(/_/g, " ")));
  });

  document.querySelectorAll('input[name="model"]').forEach((el) => {
    el.addEventListener("change", () => {
      syncModelFields(); applyStatePreset(); scheduleValidate(); scheduleRerun("model");
    });
  });
  document.querySelectorAll('input[name="state"]').forEach((el) => {
    el.addEventListener("change", () => {
      applyStatePreset(); scheduleValidate(); scheduleRerun("state");
    });
  });
  document.querySelectorAll('input[name="boundary"]').forEach((el) => {
    el.addEventListener("change", () => {
      syncModelFields(); scheduleValidate(); scheduleRerun("boundary");
    });
  });

  $("read-run-btn").addEventListener("click", readAndRun);
  $("run-btn").addEventListener("click", () => runSimulation(null));
  $("clear-log-btn").addEventListener("click", () => { $("message-log").innerHTML = ""; });
  $("reset-params-btn").addEventListener("click", () => {
    setRadio("model", DEFAULTS.model);
    setRadio("state", DEFAULTS.state);
    setRadio("boundary", DEFAULTS.boundary);
    extras = null;
    Object.keys(SLIDERS).forEach((key) => setSlider(key, DEFAULTS[key]));
    syncModelFields();
    scheduleValidate();
    log("Values reset to defaults.");
  });

  // --- View panel: camera ---
  function syncCameraLabels() {
    $("v-yaw").textContent = Math.round(scene.target.yaw * 180 / Math.PI) + "°";
    $("v-pitch").textContent = Math.round(scene.target.pitch * 180 / Math.PI) + "°";
    $("v-zoom").textContent = scene.target.dist.toFixed(1);
  }
  function syncCameraSliders() {
    $("s-yaw").value = Math.round(scene.target.yaw * 180 / Math.PI);
    $("s-pitch").value = Math.round(scene.target.pitch * 180 / Math.PI);
    $("s-zoom").value = scene.target.dist.toFixed(1);
    syncCameraLabels();
  }
  scene.onViewChange = syncCameraSliders;

  $("s-yaw").addEventListener("input", (e) => {
    scene.target.yaw = parseFloat(e.target.value) * Math.PI / 180; syncCameraLabels();
  });
  $("s-pitch").addEventListener("input", (e) => {
    scene.target.pitch = parseFloat(e.target.value) * Math.PI / 180; syncCameraLabels();
  });
  $("s-zoom").addEventListener("input", (e) => {
    scene.target.dist = parseFloat(e.target.value); syncCameraLabels();
  });
  $("autorotate").addEventListener("change", (e) => { scene.autoRotate = e.target.checked; });
  $("reset-view-btn").addEventListener("click", () => { scene.resetView(); syncCameraSliders(); });

  // --- View panel: playback ---
  $("play-btn").addEventListener("click", () => {
    player.playing = !player.playing;
    $("play-btn").textContent = player.playing ? "Pause" : "Play";
  });
  $("restart-btn").addEventListener("click", () => {
    player.restart();
    player.playing = true;
    $("play-btn").textContent = "Pause";
  });
  $("s-playspeed").addEventListener("input", (e) => {
    player.speed = parseFloat(e.target.value);
    $("v-playspeed").textContent = player.speed.toFixed(2).replace(/0$/, "") + "×";
  });
  $("s-frame").addEventListener("pointerdown", () => {
    draggingFrame = true;
    player.playing = false;
    $("play-btn").textContent = "Play";
  });
  window.addEventListener("pointerup", () => { draggingFrame = false; });
  $("s-frame").addEventListener("input", (e) => { player.setFrame(parseInt(e.target.value, 10)); });

  // --- Display Types ---
  document.querySelectorAll("#display-types input[data-show]").forEach((el) => {
    el.addEventListener("change", () => { scene.show[el.dataset.show] = el.checked; });
  });
  $("s-psize").addEventListener("input", (e) => {
    scene.ballScale = parseFloat(e.target.value);
    $("v-psize").textContent = scene.ballScale.toFixed(1) + "×";
  });
  $("s-bond").addEventListener("input", (e) => {
    const value = parseFloat(e.target.value);
    $("v-bond").textContent = value.toFixed(2) + "σ";
    player.setBondCutoff(value);
  });

  // --- tabs ---
  const TABS = ["3d", "energy", "analysis", "sweeps"];
  function selectTab(which) {
    TABS.forEach((t) => {
      $("tab-" + t).setAttribute("aria-selected", String(t === which));
      $("view-" + t).hidden = t !== which;
    });
    resizeViews();
  }
  TABS.forEach((t) => $("tab-" + t).addEventListener("click", () => selectTab(t)));

  // --- two-chart area shared by the Analysis and Experiments tabs ---
  function showCharts(chartA, chartB, noteEl, graphs, emptyMessage) {
    const list = graphs.filter(Boolean);
    chartB.canvas.hidden = list.length < 2;
    if (!list.length) {
      chartA.setGraph(null, emptyMessage);
      noteEl.textContent = emptyMessage;
    } else {
      chartA.setGraph(list[0]);
      chartB.setGraph(list.length > 1 ? list[1] : null);
      noteEl.textContent = list.map((g) => g.caption).join("  ");
    }
    chartA.resize();
    chartB.resize();
  }

  // --- Analysis tab: what was measured in the run on screen ---
  const ANALYSIS_VIEWS = {
    thermo:  { keys: ["thermo_T", "thermo_P"], none: "No thermodynamic record for this run." },
    speed:   { keys: ["speed"], none: "Speed distribution is not available for this run (reactive runs mix atoms of different mass)." },
    rdf:     { keys: ["rdf"], none: "g(r) needs a periodic bulk system; it is not computed for walled containers, hard spheres or tiny systems." },
    msd:     { keys: ["msd"], none: "Mean-squared displacement needs a periodic bulk system; not computed for this run." },
    species: { keys: ["species"], none: "Species are only counted in reactive runs (e.g. 'hydrogen and oxygen reacting at high temperature')." },
  };
  function showAnalysis() {
    document.querySelectorAll("#analysis-bar button").forEach((b) => {
      const v = ANALYSIS_VIEWS[b.dataset.graph];
      b.setAttribute("aria-pressed", String(b.dataset.graph === analysisChoice));
      b.style.opacity = v.keys.some((k) => lastGraphs[k]) ? "1" : "0.5";
    });
    const v = ANALYSIS_VIEWS[analysisChoice];
    const empty = hasRun || Object.keys(lastGraphs).length ? v.none : "Run a simulation to see its measured properties.";
    showCharts(analysisA, analysisB, $("analysis-note"), v.keys.map((k) => lastGraphs[k]), empty);
  }
  document.querySelectorAll("#analysis-bar button").forEach((b) => {
    b.addEventListener("click", () => { analysisChoice = b.dataset.graph; showAnalysis(); });
  });

  // --- Experiments tab: several simulations, one quantity varied ---
  const EXPERIMENTS = {
    eos:       { run: "eos", show: ["eos"], hint: "Pressure against density at the current temperature, compared with the ideal-gas law and van der Waals (7 simulations, about 10 s)." },
    boyle:     { run: "boyle", show: ["boyle"], hint: "Squeeze a gas: pressure against volume at constant temperature, to test Boyle's law (6 simulations, about 10 s)." },
    charles:   { run: "charles", show: ["charles"], hint: "Heat a gas in a fixed box: pressure against temperature (Gay-Lussac; with Boyle's law it gives Charles's law) (6 simulations, about 10 s)." },
    heating:   { run: "heating", show: ["heating_U", "heating_D"], hint: "Heat a crystal of the current substance and watch it melt: energy and diffusion against temperature (8 simulations, about 30 s)." },
    heatcap:   { run: "heating", show: ["heat_capacity"], hint: "Heat capacity of a crystal measured two ways, against the theoretical 3 k_B and 3/2 k_B (uses the heating-curve runs, about 30 s)." },
    arrhenius: { run: "arrhenius", show: ["arrhenius"], hint: "Diffusion of the liquid at several temperatures: the slope of ln D against 1/T is the activation energy (5 simulations; about 15 s, or 2-3 min for water)." },
  };
  const sweepResults = {};      // run kind -> graphs
  let sweepChoice = "eos";
  let sweepRunning = false;

  function showSweeps() {
    document.querySelectorAll("#sweeps-bar button[data-exp]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.exp === sweepChoice)));
    const exp = EXPERIMENTS[sweepChoice];
    const done = sweepResults[exp.run];
    if (done) showCharts(sweepA, sweepB, $("sweeps-note"), exp.show.map((k) => done[k]), "No result.");
    else showCharts(sweepA, sweepB, $("sweeps-note"), [], exp.hint + " Press Run experiment.");
  }
  document.querySelectorAll("#sweeps-bar button[data-exp]").forEach((b) => {
    b.addEventListener("click", () => { sweepChoice = b.dataset.exp; showSweeps(); });
  });

  async function runSweep() {
    if (sweepRunning) return;
    const exp = EXPERIMENTS[sweepChoice];
    const status = $("sweep-status");
    sweepRunning = true;
    $("sweep-run").disabled = true;
    status.textContent = "starting…";
    try {
      const components = extras && extras.sim ? extras.sim.components : null;
      const id = await API.startSweep(exp.run, components, sliderValue("temperature"));
      for (;;) {
        await new Promise((r) => setTimeout(r, 1500));
        const job = await API.getSweep(id);
        if (job.status === "running") { status.textContent = `running ${job.done} / ${job.total || "…"} simulations…`; continue; }
        if (job.status === "error") throw new Error(job.error);
        sweepResults[exp.run] = job.graphs;
        status.textContent = `done (${job.substance})`;
        log(`Experiment finished: ${sweepChoice} for ${job.substance}.`, "ok");
        break;
      }
    } catch (e) {
      status.textContent = "";
      log("Experiment failed: " + e.message, "err");
    } finally {
      sweepRunning = false;
      $("sweep-run").disabled = false;
      showSweeps();
    }
  }
  $("sweep-run").addEventListener("click", runSweep);

  // --- keeping both canvases matched to the space the layout gives them ---
  function resizeViews() {
    scene.resize();
    chart.resize();
    [analysisA, analysisB, sweepA, sweepB].forEach((c) => c.resize());
  }
  window.addEventListener("resize", resizeViews);
  if (window.ResizeObserver) {
    new ResizeObserver(resizeViews).observe(document.querySelector(".viewstack"));
  }

  // ---------------- start ----------------

  Object.keys(SLIDERS).forEach(refreshSliderLabel);
  syncModelFields();
  syncCameraSliders();
  showAnalysis();
  showSweeps();
  resizeViews();
  requestAnimationFrame(animationLoop);

  log("Ready. The description above is read on this machine — no external service is contacted.");
  validateNow().then(() => readAndRun());
})();
