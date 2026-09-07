"""
make_report_diagrams_v4.py

Regenerates all six figures used in the Project-I report, in their current
(v4) form. Run it from anywhere:

    python deliverables/make_report_diagrams_v4.py

Output goes to deliverables/figures/*_v4.png.

Why v4 exists: the earlier figure sets were correct in outline but not in
notation -- the "class diagram" was a module sketch rather than UML, the DFD
used closed boxes for data stores, the sequence diagram had no activation
bars and drew self-messages as floating text, and one use case overflowed the
system boundary. This version redraws all six to standard notation and, just
as importantly, to match what the code in backend/, engine_cpp/ and frontend/
actually does (module names, endpoint names, file names).

Shared conventions (see diagram_style.py):
  * SOLID border  = implemented and demonstrated in this project.
  * DASHED border = proposed / future work (GPU-CUDA engine, full local SLM).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagram_style import *  # noqa: F401,F403

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)


# ==========================================================================
# Fig. 1 -- Project Plan (Gantt chart)
# ==========================================================================
def fig1_gantt():
    """Relative project weeks only. No calendar dates are shown, because no
    fixed calendar start date is claimed anywhere in the report."""
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    fig.patch.set_facecolor("white")

    phases = [
        # (label, start week, duration, workstream)
        ("Study and re-baseline the 2024 C++ MD code",  0, 2, "study"),
        ("Define parameter schema and project scope",   1, 2, "study"),
        ("Parameterised C++ simulation engine",         2, 3, "engine"),
        ("Boundary modes and states of matter",         3, 3, "engine"),
        ("Local rule-based extraction module",          4, 2, "language"),
        ("Shared feasibility validation layer",         5, 2, "language"),
        ("Backend orchestration (FastAPI endpoints)",   5, 2, "system"),
        ("Browser interface and 3D trajectory viewer",  6, 3, "system"),
        ("Automated testing and physical verification", 8, 2, "verify"),
        ("Documentation and Review-2 deliverables",     9, 2, "verify"),
    ]

    colors = {
        "study":    ("#DDE6EF", "#26619C"),
        "engine":   ("#D8EDE3", "#1B7A5A"),
        "language": ("#E7DFF5", "#6B4FA8"),
        "system":   ("#FBEBD5", "#B07D2B"),
        "verify":   ("#F5DCDA", "#B3261E"),
    }
    names = {
        "study": "Analysis and design",
        "engine": "Simulation engine",
        "language": "Language understanding and validation",
        "system": "System integration and interface",
        "verify": "Verification and documentation",
    }

    n = len(phases)
    for i, (label, start, dur, kind) in enumerate(phases):
        y = i  # phase 1 at the top, which is how a Gantt chart is read
        fill, edge = colors[kind]
        ax.barh(y, dur, left=start, height=0.55, color=fill, edgecolor=edge,
                linewidth=1.3, zorder=3)
        ax.text(start + dur / 2, y, f"W{start + 1}–W{start + dur}",
                va="center", ha="center", fontsize=8.0, family=FONT,
                color=edge, fontweight="bold", zorder=5)

    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{i + 1}.  {lbl}" for i, (lbl, *_r) in enumerate(phases)],
                       fontsize=9.6, family=FONT, color=INK)
    ax.invert_yaxis()
    ax.set_ylim(n - 0.4, -0.8)

    ax.set_xlim(0, 11.15)
    ax.set_xticks(range(0, 12))
    ax.set_xticklabels([f"W{i + 1}" if i < 11 else "" for i in range(12)],
                       fontsize=9.2, family=FONT, color=INK)
    ax.set_xlabel("Project week (relative)", fontsize=10.0, family=FONT,
                  color=INK, labelpad=6)

    ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)

    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=colors[k][0],
                             edgecolor=colors[k][1], linewidth=1.2)
               for k in names]
    ax.legend(handles, list(names.values()), loc="upper center",
              bbox_to_anchor=(0.42, -0.14), ncol=3, frameon=False,
              prop={"family": FONT, "size": 8.6}, handlelength=1.4,
              columnspacing=1.4)

    fig.tight_layout()
    save(fig, os.path.join(OUT, "fig1_gantt_v4.png"))


# ==========================================================================
# Fig. 2 -- System Architecture (layered)
# ==========================================================================
def fig2_architecture():
    """A layered view: what runs where, and which stage the proposed CUDA
    backend would replace. Everything sits inside one machine boundary --
    that is the point of the diagram, not an incidental decoration."""
    fig, ax = new_figure(7.6, 8.4)

    group_frame(ax, 50, 50.5, 97, 95, edge="#9AA5B1", dashed=True, lw=1.4)
    ax.text(3.6, 96.4, "LOCAL MACHINE  —  no network, no external AI API",
            ha="left", va="center", family=FONT, fontsize=8.0, color=MUTED,
            fontweight="bold")

    LX, LW = 48, 88

    # ---- Presentation ----------------------------------------------------
    group_frame(ax, LX, 84, LW, 16, dashed=False, lw=1.1, fill="#FEFAF3",
                edge=INPUT_EDGE, fontsize=7.8, label_color="#8A6220",
                label="PRESENTATION LAYER   browser · HTML / CSS / JS")
    box(ax, 18, 82, 25, 11,
        "Setup panel\nnatural-language box\nand manual form",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=8.0)
    box(ax, 48, 82, 25, 11,
        "Review panel\nlive feasibility check\nbefore anything runs",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=8.0)
    box(ax, 78, 82, 25, 11,
        "Run panel\nscene3d.js\ntrajectoryPlayer.js\nenergyChart.js",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=8.0)

    # ---- Application -----------------------------------------------------
    group_frame(ax, LX, 57, LW, 26, dashed=False, lw=1.1, fill="#F6F9FC",
                edge=LOGIC_EDGE, fontsize=7.8, label_color="#1D4E7E",
                label="APPLICATION LAYER   Python · FastAPI")
    box(ax, 19, 61.5, 27, 11,
        "Language understanding\nnlp/extractor.py\nparameters only",
        fill=LANG_FILL, edge=LANG_EDGE, fontsize=8.0)
    box(ax, 48, 61.5, 25, 11,
        "Parameter validation\nvalidation/schema.py\nfeasibility checks",
        fill=LOGIC_FILL, edge=LOGIC_EDGE, fontsize=8.0)
    box(ax, 78, 61.5, 25, 11,
        "Run orchestration\nengine/runner.py\nlaunch · collect",
        fill=LOGIC_FILL, edge=LOGIC_EDGE, fontsize=8.0)
    box(ax, 19, 49.5, 27, 7, "State presets\nconfig_defaults.py",
        fill=DATA_FILL, edge=DATA_EDGE, fontsize=7.6)
    box(ax, 78, 49.5, 25, 7, "runs/<id>/config.txt",
        fill=DATA_FILL, edge=DATA_EDGE, fontsize=7.6)

    # ---- Execution -------------------------------------------------------
    group_frame(ax, LX, 29, LW, 21, dashed=False, lw=1.1, fill="#F5FAF8",
                edge=ENGINE_EDGE, fontsize=7.8, label_color="#156046",
                label="EXECUTION LAYER   fixed, hand-verified engine")
    box(ax, 27, 27, 38, 16, "", fill=ENGINE_FILL, edge=ENGINE_EDGE, lw=1.7)
    ax.text(27, 32.4, "CPU ENGINE  ·  IMPLEMENTED", ha="center", va="center",
            family=FONT, fontsize=8.4, color=INK, fontweight="bold")
    ax.text(27, 25.4,
            "C++11, compiled once\nLennard-Jones and Hard-Sphere\n"
            "velocity-Verlet integration\nperiodic / walled boundaries",
            ha="center", va="center", family=FONT, fontsize=7.6, color=INK,
            linespacing=1.7)

    box(ax, 72, 27, 34, 16, "", fill=FUTURE_FILL, edge=FUTURE_EDGE, lw=1.7,
        dashed=True)
    ax.text(72, 32.4, "GPU / CUDA  ·  PROPOSED", ha="center", va="center",
            family=FONT, fontsize=8.4, color=INK, fontweight="bold")
    ax.text(72, 25.4,
            "same interface and\nsame config format\n"
            "force loop and integrator\nbecome CUDA kernels",
            ha="center", va="center", family=FONT, fontsize=7.6, color=INK,
            linespacing=1.7)

    # ---- Output artefacts ------------------------------------------------
    group_frame(ax, LX, 9.5, LW, 13, dashed=False, lw=1.1, fill="#F7F8FA",
                edge=DATA_EDGE, fontsize=7.8, label_color="#465361",
                label="RUN OUTPUT   one folder per request")
    box(ax, 30, 7.5, 30, 7, "trajectory.json\nreal particle positions",
        fill=DATA_FILL, edge=DATA_EDGE, fontsize=7.6)
    box(ax, 68, 7.5, 28, 7, "energy.csv\nreal energy per frame",
        fill=DATA_FILL, edge=DATA_EDGE, fontsize=7.6)

    # ---- Connectors ------------------------------------------------------
    arrow(ax, (18, 76.5), (18, 67), label="POST /api/extract",
          fontsize=7.2, label_dy=0.8)
    arrow(ax, (48, 76.5), (48, 67),
          label="POST /api/validate\nPOST /api/simulate", fontsize=7.2,
          label_dy=0.8)
    arrow(ax, (78, 67), (78, 76.3),
          label="real trajectory\n+ energy (JSON)", fontsize=7.2,
          label_dy=-0.8)

    arrow(ax, (19, 53), (19, 56), label=None)
    ax.text(20.6, 54.6, "state defaults", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)

    arrow(ax, (32.6, 61.5), (35.4, 61.5), label=None)
    ax.text(34, 51.5, "draft\nparameters", ha="center", va="center",
            family=FONT, fontsize=7.0, color=INK, linespacing=1.35,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none"))
    arrow(ax, (60.6, 61.5), (65.4, 61.5), label=None)
    ax.text(58, 51.5, "validated\nparameters", ha="center", va="center",
            family=FONT, fontsize=7.0, color=INK, linespacing=1.35,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none"))

    arrow(ax, (78, 56), (78, 53.2), label=None)
    ax.text(79.6, 54.6, "writes", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)

    elbow(ax, [(65.4, 49.5), (58, 49.5), (58, 41.5), (27, 41.5), (27, 35.2)],
          label=None)
    ax.text(43, 43.2, "launched as a subprocess",
            ha="center", va="center", family=FONT, fontsize=7.0, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none"))
    elbow(ax, [(58, 41.5), (72, 41.5), (72, 35.2)], dashed=True)

    arrow(ax, (22, 19), (22, 11.2), label=None)
    ax.text(20.4, 17.6, "writes", ha="right", va="center", family=FONT,
            fontsize=7.0, color=MUTED)
    elbow(ax, [(36, 19), (36, 16.2), (62, 16.2), (62, 11.2)], label=None)
    elbow(ax, [(84, 19), (84, 16.2), (76, 16.2), (76, 11.2)], dashed=True)

    elbow(ax, [(82, 7.5), (94.5, 7.5), (94.5, 61.5), (90.7, 61.5)], label=None)
    ax.text(96.6, 34.0, "output read back by runner.py", ha="center",
            va="center", family=FONT, fontsize=7.0, color=MUTED, rotation=90)

    save(fig, os.path.join(OUT, "fig2_architecture_v4.png"))

# ==========================================================================
# Fig. 3 -- Level-1 Data Flow Diagram (Gane-Sarson notation)
# ==========================================================================
def fig3_dfd():
    fig, ax = new_figure(7.6, 5.6)

    sharp_box(ax, 8, 85, 13, 9, "User", fill=INPUT_FILL, edge=INPUT_EDGE,
              fontsize=10, bold=True, lw=1.6)
    ax.text(8, 76.8, "external entity", ha="center", va="center", family=FONT,
            fontsize=7.0, color=MUTED, style="italic")

    process(ax, 33, 85, 26, 13, "1.0", "Capture Simulation\nRequest")
    process(ax, 63, 85, 24, 13, "2.0", "Extract Parameters\nfrom Description",
            fill=LANG_FILL, edge=LANG_EDGE)
    process(ax, 63, 60, 24, 13, "3.0", "Validate Parameter\nFeasibility")
    process(ax, 63, 33, 24, 13, "4.0", "Configure and Execute\nSimulation",
            fill=ENGINE_FILL, edge=ENGINE_EDGE)
    process(ax, 20, 11, 24, 13, "5.0", "Render Trajectory\nand Energy")

    datastore(ax, 88, 85, 20, 7.5, "D1", "State-of-matter\npresets", fontsize=8.0)
    datastore(ax, 24, 33, 30, 7.5, "D2", "Run configuration\nconfig.txt", fontsize=8.0)
    datastore(ax, 63, 11, 34, 8.5, "D3",
              "Trajectory and energy\ntrajectory.json · energy.csv",
              fontsize=8.0)

    # --- flows ---
    arrow(ax, (14.5, 85), (19.8, 85), label="description or\nform values",
          fontsize=7.4, label_dy=9.8)
    arrow(ax, (46.2, 85), (50.8, 85), label=None)
    ax.text(48.5, 94.0, "free-text description", ha="center", va="center",
            family=FONT, fontsize=7.4, color=INK)
    arrow(ax, (77.8, 85), (75.2, 85), label=None)
    ax.text(88, 77.4, "state defaults for\nsolid / liquid / gas", ha="center",
            va="center", family=FONT, fontsize=7.2, color=MUTED,
            linespacing=1.4)

    elbow(ax, [(33, 78.4), (33, 64), (50.8, 64)],
          label="manual\nparameters", label_at=0, label_dx=-1.6,
          label_ha="right", fontsize=7.4, label_dy=0)
    arrow(ax, (63, 78.4), (63, 66.6), label="draft parameters",
          fontsize=7.4, label_dx=1.6, label_dy=0, label_ha="left")
    arrow(ax, (63, 53.4), (63, 39.6), label="validated\nparameters",
          fontsize=7.4, label_dx=1.6, label_dy=0, label_ha="left")

    arrow(ax, (50.8, 35.2), (39.2, 35.2), label="writes config.txt",
          fontsize=7.4, label_dy=2.4)
    arrow(ax, (39.2, 30.8), (50.8, 30.8), label="read at start-up",
          fontsize=7.4, label_dy=-2.4)

    arrow(ax, (63, 26.4), (63, 15.4), label="real trajectory\n+ energy frames",
          fontsize=7.4, label_dx=1.6, label_dy=0, label_ha="left")
    arrow(ax, (45.8, 11), (32.2, 11), label="playback data", fontsize=7.4,
          label_dy=2.6)

    elbow(ax, [(8, 11), (3.6, 11), (3.6, 80.3)], label=None)
    ax.text(5.2, 48, "3D view and\nenergy chart", ha="left", va="center",
            family=FONT, fontsize=7.4, color=INK, linespacing=1.4,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="none"))

    note(ax, 88, 34, 20, 15,
         "Process 4.0 backend:\nCPU (this prototype)\nor GPU / CUDA\n(proposed)",
         fontsize=7.4)

    ax.text(86, 20, "Gane–Sarson notation", ha="left", va="center",
            family=FONT, fontsize=7.4, color=MUTED, fontweight="bold")
    sharp_box(ax, 88.4, 16, 3.6, 2.4, "", fill=INPUT_FILL, edge=INPUT_EDGE,
              lw=1.1)
    ax.text(91.4, 16, "external entity", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)
    box(ax, 88.4, 12, 3.6, 2.4, "", fill=LOGIC_FILL, edge=LOGIC_EDGE, lw=1.1,
        radius=0.4)
    ax.text(91.4, 12, "numbered process", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)
    mini_datastore(ax, 88.4, 8, 4.4, 2.4)
    ax.text(91.4, 8, "data store", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)

    save(fig, os.path.join(OUT, "fig3_dfd_v4.png"))


# ==========================================================================
# Fig. 4 -- Use Case Diagram
# ==========================================================================
def fig4_usecase():
    fig, ax = new_figure(7.2, 5.6)

    actor(ax, 11, 52, "User\n(student / researcher)", scale=1.5)

    group_frame(ax, 61, 49, 76, 94, edge=INK, dashed=False, lw=1.5,
                fill="#FCFDFE")
    ax.text(61, 92.0, "AI-Assisted Molecular Dynamics Simulation System",
            ha="center", va="center", family=FONT, fontsize=9.4,
            fontweight="bold", color=INK, zorder=6)
    ax.plot([25, 97], [88.5, 88.5], color=GRID, lw=1.0, zorder=5)

    primary = [
        (80, "Describe Simulation\nin Natural Language"),
        (67, "Enter Parameters\nManually"),
        (54, "Choose Model, State\nand Container"),
        (41, "Review and Confirm\nParameters"),
        (25, "Run Molecular\nDynamics Simulation"),
    ]
    for y, t in primary:
        usecase(ax, 45, y, 28, 10.5, t)
        ax.plot([16, 31], [52, y], color=LINE, lw=1.2, zorder=2)

    usecase(ax, 79, 80, 28, 10.5, "Extract Parameters\nfrom Description")
    usecase(ax, 79, 41, 28, 10.5, "Validate Physical\nFeasibility")
    usecase(ax, 79, 25, 28, 10.5, "Execute Simulation")

    usecase(ax, 62, 12.0, 24, 10, "Execute on CPU")
    ax.text(62, 5.4, "implemented", ha="center", va="center", family=FONT,
            fontsize=7.2, color=ENGINE_EDGE, fontweight="bold", zorder=6)
    ax.add_patch(Ellipse((87, 12.0), 20, 10, facecolor=FUTURE_FILL,
                         edgecolor=FUTURE_EDGE, linewidth=1.4,
                         linestyle=(0, (4, 2.5)), zorder=3))
    ax.text(87, 12.0, "Execute on\nGPU / CUDA", ha="center", va="center",
            fontsize=8.6, family=FONT, color=INK, linespacing=1.4, zorder=4)
    ax.text(87, 5.4, "«proposed»", ha="center", va="center", family=FONT,
            fontsize=7.2, color=FUTURE_EDGE, fontweight="bold", zorder=6)

    for y in (80, 41, 25):
        arrow(ax, (59, y), (64.8, y), style="->", dashed=True, lw=1.2,
              label="«include»", fontsize=7.4, label_dy=2.1)

    arrow(ax, (65, 16.6), (74.8, 19.9), style="-|>", hollow=True, lw=1.3,
          color=INK)
    arrow(ax, (86, 17.0), (81.8, 19.9), style="-|>", hollow=True, lw=1.3,
          color=INK)
    ax.text(69.0, 21.5, "generalization", ha="center", va="center",
            family=FONT, fontsize=7.0, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none"), zorder=6)

    save(fig, os.path.join(OUT, "fig4_usecase_v4.png"))


# ==========================================================================
# Fig. 5 -- UML Class Diagram
# ==========================================================================
def fig5_class():
    """Class names, attributes and operations are taken directly from the
    source files, so the diagram and the code can be checked against each
    other line by line."""
    fig, ax = new_figure(7.0, 8.6)

    LH, PAD = 2.0, 1.4

    def place(x, w, top, name, attrs, ops, **kw):
        head = (2 if kw.get("stereotype") else 1) * LH + 2 * PAD
        h = head + (2 * PAD + max(len(attrs), 1) * LH) \
                 + (2 * PAD + max(len(ops), 1) * LH)
        uml_class(ax, x, top - h / 2, w, name, attrs, ops,
                  fontsize=7.6, line_h=LH, pad=PAD, **kw)
        return top, top - h

    # ---------- application layer (Python) --------------------------------
    place(17, 28, 98, "ParameterExtractor",
          ["- keyword_maps : dict", "- number_patterns : regex"],
          ["+ extract_parameters(text)"],
          fill=LANG_FILL, edge=LANG_EDGE, header_fill="#E3DAF3")

    place(50, 32, 98, "SimParams",
          ["+ model, state", "+ container_enabled", "+ container_shape",
           "+ particle_count, size", "+ density, temperature",
           "+ particle_speed", "+ timestep, total_time",
           "+ epsilon, sigma, cutoff"],
          ["+ check_particle_count()", "+ check_cutoff_fits_box()",
           "+ validate_params(dict)"],
          stereotype="«pydantic model»", fill=LOGIC_FILL, edge=LOGIC_EDGE)

    place(85, 28, 98, "StatePresets",
          ["- LJ_STATE_PRESETS", "- HARD_SPHERE_PRESETS"],
          ["+ get_state_preset(...)"],
          fill=DATA_FILL, edge=DATA_EDGE, header_fill="#E6E9ED")

    place(85, 28, 78, "SimulationRunner",
          ["- engine_path", "- runs_dir"],
          ["+ run_simulation(SimParams)", "- write_config_file()",
           "- read_energy_csv()"],
          fill=LOGIC_FILL, edge=LOGIC_EDGE)

    # ---------- execution layer (C++) -------------------------------------
    place(17, 30, 78, "SimConfig",
          ["+ model, state : string", "+ container_enabled : bool",
           "+ particle_count : int", "+ timestep, total_time",
           "+ epsilon, sigma, cutoff"],
          ["+ load_config(path)"],
          fill=ENGINE_FILL, edge=ENGINE_EDGE, header_fill="#D5EBE1")

    place(50, 32, 53, "SimulationEngine", ["—"],
          ["+ run(SimConfig) : Trajectory"],
          stereotype="«interface»", name_italic=True, edge=INK,
          header_fill="#EDEFF2")

    place(17, 26, 52, "Particle",
          ["+ x, y, z : double", "+ vx, vy, vz : double",
           "+ fx, fy, fz : double"], ["—"],
          fill=ENGINE_FILL, edge=ENGINE_EDGE, header_fill="#D5EBE1")

    place(85, 30, 52, "TrajectoryWriter",
          ["- trajectory_file", "- energy_file"],
          ["+ write_frame(particles)", "+ write_energy(...)", "+ close()"],
          fill=DATA_FILL, edge=DATA_EDGE, header_fill="#E6E9ED")

    place(22, 36, 28, "CPUEngine",
          ["- particles : vector<Particle>", "- box_length : double",
           "- periodic : bool"],
          ["+ run(SimConfig) : Trajectory", "+ initialize_particles()",
           "+ compute_lj_forces()  — O(N²)",
           "+ resolve_hard_sphere_collisions()",
           "+ begin_step() / finish_step()"],
          fill=ENGINE_FILL, edge=ENGINE_EDGE, header_fill="#D5EBE1",
          tag="IMPLEMENTED", tag_color=ENGINE_EDGE)

    place(76, 32, 28, "CUDAEngine",
          ["- d_particles : Particle*", "- grid, block : dim3"],
          ["+ run(SimConfig) : Trajectory", "+ lj_force_kernel<<<>>>()",
           "+ integrate_kernel<<<>>>()", "+ boundary_kernel<<<>>>()"],
          stereotype="«proposed · future work»", dashed=True,
          fill=FUTURE_FILL, edge=FUTURE_EDGE, header_fill="#F6DAD7",
          tag="NOT IMPLEMENTED", tag_color=FUTURE_EDGE)

    # ---------- relationships ---------------------------------------------
    arrow(ax, (31.2, 92.0), (33.8, 92.0), style="->", dashed=True, lw=1.2,
          label="«create»", fontsize=7.0, label_dy=0)
    arrow(ax, (70.8, 92.0), (66.2, 92.0), style="->", dashed=True, lw=1.2,
          label="«defaults»", fontsize=7.0, label_dy=0)

    arrow(ax, (70.8, 70.0), (66.2, 70.0), style="-|>", lw=1.3,
          label="reads", fontsize=7.0, label_dy=0)

    arrow(ax, (70.8, 60.5), (32.2, 60.5), style="-|>", lw=1.3,
          label="writes runs/<id>/config.txt", fontsize=7.0, label_dy=1.9)

    arrow(ax, (22, 55.6), (38, 53.0), style="-|>", lw=1.3)
    ax.text(33.0, 57.6, "configures", ha="center", va="center", family=FONT,
            fontsize=7.0, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none"))

    arrow(ax, (22, 28.0), (44.0, 36.6), style="-|>", dashed=True, hollow=True,
          lw=1.4, color=INK)
    ax.text(31.0, 34.0, "«realize»", ha="center", va="center", family=FONT,
            fontsize=7.0, color=MUTED, rotation=21,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none"))
    arrow(ax, (76, 28.0), (56.0, 36.6), style="-|>", dashed=True, hollow=True,
          lw=1.4, color=INK)
    ax.text(64.5, 32.6, "«realize»", ha="center", va="center", family=FONT,
            fontsize=7.0, color=MUTED, rotation=-23,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none"))

    ax.plot([9, 9], [28.0, 33.6], color=LINE, lw=1.3, zorder=5)
    diamond(ax, 9, 29.4, size=1.4, filled=True, color=LINE)
    ax.text(10.4, 30.2, "1", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)
    ax.text(10.4, 32.8, "1..*", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)

    elbow(ax, [(40, 18), (50, 18), (50, 34), (69.6, 34)], label=None)
    ax.text(52.0, 20.0, "writes frames", ha="left", va="center", family=FONT,
            fontsize=7.0, color=MUTED)

    arrow(ax, (85, 52.0), (85, 57.4), style="->", dashed=True, lw=1.2)
    ax.text(83.4, 55.0, "reads back", ha="right", va="center", family=FONT,
            fontsize=7.0, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                      edgecolor="none"))

    legend(ax, 42.0, 10.5, [
        (ENGINE_FILL, ENGINE_EDGE, False, "Implemented"),
        (FUTURE_FILL, FUTURE_EDGE, True, "Proposed"),
    ], fontsize=7.0, dy=4.0)

    save(fig, os.path.join(OUT, "fig5_class_v4.png"))

# ==========================================================================
# Fig. 6 -- Sequence Diagram
# ==========================================================================
def fig6_sequence():
    fig, ax = new_figure(7.8, 7.2)

    TOP, BOT = 97.0, 2.0
    x = {"user": 7.0, "ui": 21.0, "api": 35.0, "nlp": 49.0, "val": 63.0,
         "run": 77.0, "eng": 91.0}

    lifeline(ax, x["user"], TOP, BOT, "User", w=11.5, fill=INPUT_FILL,
             edge=INPUT_EDGE, fontsize=8.0)
    lifeline(ax, x["ui"], TOP, BOT, "Web UI", sub="browser", w=12.0,
             fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=8.0)
    lifeline(ax, x["api"], TOP, BOT, "Backend", sub="app.py", w=12.0,
             fontsize=8.0)
    lifeline(ax, x["nlp"], TOP, BOT, "Extractor", sub="extractor.py", w=12.0,
             fill=LANG_FILL, edge=LANG_EDGE, fontsize=8.0)
    lifeline(ax, x["val"], TOP, BOT, "Validator", sub="schema.py", w=12.0,
             fontsize=8.0)
    lifeline(ax, x["run"], TOP, BOT, "Runner", sub="runner.py", w=12.0,
             fontsize=8.0)
    lifeline(ax, x["eng"], TOP, BOT, "MD Engine", sub="C++", w=12.0,
             fill=ENGINE_FILL, edge=ENGINE_EDGE, fontsize=8.0)

    activation(ax, x["ui"], 88.0, 3.5, w=1.6, fill="#F5E7CE", edge=INPUT_EDGE)
    activation(ax, x["api"], 81.0, 5.5, w=1.6)

    activation(ax, x["user"], 88.8, 86.5, w=1.6, fill="#F5E7CE",
               edge=INPUT_EDGE)
    message(ax, x["user"] + 0.8, x["ui"] - 0.8, 88.0,
            "1: describe it, or fill in the form", fontsize=7.6)

    fragment(ax, 36.0, 74.0, 42.0, 21.0, "opt",
             "[natural-language path]", fontsize=7.4)
    message(ax, x["ui"] + 0.8, x["api"] - 0.8, 78.5, "2: POST /api/extract",
            fontsize=7.6)
    message(ax, x["api"] + 0.8, x["nlp"] - 0.8, 74.5,
            "2.1: extract_parameters(text)", fontsize=7.6)
    activation(ax, x["nlp"], 74.5, 70.5, fill="#E3DAF3", edge=LANG_EDGE)
    message(ax, x["nlp"] - 0.8, x["api"] + 0.8, 70.5, "draft parameters",
            dashed=True, fontsize=7.6)
    message(ax, x["api"] - 0.8, x["ui"] + 0.8, 66.5,
            "editable draft for the Review step", dashed=True, fontsize=7.6)

    message(ax, x["ui"] + 0.8, x["api"] - 0.8, 59.5, "3: POST /api/validate",
            fontsize=7.6)
    message(ax, x["api"] + 0.8, x["val"] - 0.8, 55.5,
            "3.1: validate_params(params)", fontsize=7.6)
    activation(ax, x["val"], 55.5, 46.0)
    self_message(ax, x["val"] + 0.8, 53.5,
                 "range checks +\nminimum-image rule", w=4.0, h=3.4,
                 fontsize=7.2, text_side="left")
    message(ax, x["val"] - 0.8, x["api"] + 0.8, 45.0, "(params, errors)",
            dashed=True, fontsize=7.6)
    message(ax, x["api"] - 0.8, x["ui"] + 0.8, 41.5,
            "pass / fail, with reasons", dashed=True, fontsize=7.6)

    activation(ax, x["user"], 39.3, 37.0, w=1.6, fill="#F5E7CE",
               edge=INPUT_EDGE)
    message(ax, x["user"] + 0.8, x["ui"] - 0.8, 38.5, "4: confirm and run",
            fontsize=7.6)
    message(ax, x["ui"] + 0.8, x["api"] - 0.8, 35.0, "5: POST /api/simulate",
            fontsize=7.6)
    message(ax, x["api"] + 0.8, x["val"] - 0.8, 31.5,
            "5.1: validate_params()  — again", fontsize=7.6)
    activation(ax, x["val"], 31.5, 28.0)
    message(ax, x["val"] - 0.8, x["api"] + 0.8, 28.0, "valid", dashed=True,
            fontsize=7.6)

    message(ax, x["api"] + 0.8, x["run"] - 0.8, 24.5,
            "5.2: run_simulation(params)", fontsize=7.6)
    activation(ax, x["run"], 24.5, 7.5)
    self_message(ax, x["run"] + 0.8, 22.5, "write config.txt", w=3.4, h=2.6,
                 fontsize=7.2, text_side="left")

    message(ax, x["run"] + 0.8, x["eng"] - 0.8, 18.0,
            "5.3: exec md_engine", fontsize=7.6)
    activation(ax, x["eng"], 18.0, 10.0, fill="#D5EBE1", edge=ENGINE_EDGE)

    fragment(ax, 92.0, 15.2, 13.0, 6.6, "loop", "", fontsize=7.2)
    self_message(ax, x["eng"] + 0.8, 16.6,
                 "compute forces · integrate\napply boundary · dump frame",
                 w=3.0, h=2.6, fontsize=7.2, text_side="left")

    message(ax, x["eng"] - 0.8, x["run"] + 0.8, 10.0,
            "exit 0 · output files written", dashed=True, fontsize=7.6)
    message(ax, x["run"] - 0.8, x["api"] + 0.8, 7.5,
            "real trajectory + energy rows", dashed=True, fontsize=7.6)
    message(ax, x["api"] - 0.8, x["ui"] + 0.8, 5.5, "JSON response",
            dashed=True, fontsize=7.6)
    message(ax, x["ui"] - 0.8, x["user"] + 0.8, 3.5,
            "6: 3D playback + chart", dashed=True, fontsize=7.6)

    save(fig, os.path.join(OUT, "fig6_sequence_v4.png"))

if __name__ == "__main__":
    fig1_gantt()
    fig2_architecture()
    fig3_dfd()
    fig4_usecase()
    fig5_class()
    fig6_sequence()
    print("\nAll six report figures regenerated into", OUT)
