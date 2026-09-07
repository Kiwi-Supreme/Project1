"""Regenerates the report's DFD, Class/Module, and Sequence diagrams at the
framework level (CPU prototype vs. proposed GPU/CUDA backend shown as two
options under one pipeline, not two separate systems). Gantt (fig1),
Architecture/pipeline (fig_pipeline), and Use Case (fig4) are reused as-is
from the earlier work -- their content already reads at the right level."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)


def box(ax, x, y, w, h, text, fc="#EAF3F0", ec="#2F6F5E", fontsize=9.5, weight="normal", dashed=False):
    ls = (0, (5, 3)) if dashed else "solid"
    p = FancyBboxPatch((x, y), w, h, fc=fc, ec=ec, lw=1.3, linestyle=ls,
                        boxstyle="round,pad=0.02,rounding_size=0.04")
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, weight=weight)


def arrow(ax, p1, p2, text=None, fontsize=8):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13, lw=1.15, color="#333333")
    ax.add_patch(a)
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.09, text, ha="center", va="bottom", fontsize=fontsize, color="#333333")


def new_ax(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ---------------- Fig 3: Data Flow Diagram (framework level) ----------------
fig, ax = new_ax(9.4, 5.6)

u = box(ax, 0.3, 4.0, 1.6, 1.0, "User", fc="#FDF3E3", ec="#9C6A16")
p1 = box(ax, 2.3, 4.0, 2.3, 1.0, "1.0\nCollect Input\n(NL or manual)", fc="#E7F0FB", ec="#2B5F8A")
p2 = box(ax, 5.0, 4.0, 2.3, 1.0, "2.0\nExtract & Validate\nParameters (SLM)", fc="#E7F0FB", ec="#2B5F8A")
d1 = box(ax, 2.3, 2.5, 2.3, 0.8, "D1  Parameter\nSchema", fc="#F1EAFB", ec="#6B4FA0", fontsize=8.5)
p3 = box(ax, 5.0, 1.1, 2.3, 1.0, "3.0\nConfigure & Execute\nSimulation", fc="#E7F0FB", ec="#2B5F8A")
d2 = box(ax, 7.6, 1.1, 1.5, 1.0, "D2\nTrajectory +\nEnergy", fc="#FBEAE8", ec="#B0392F", fontsize=7.8)
p4 = box(ax, 2.3, 1.1, 2.3, 1.0, "4.0\nVisualize\nResults", fc="#E7F0FB", ec="#2B5F8A")
note = box(ax, 5.0, 0.05, 3.6, 0.75, "3.0 backend: CPU (this prototype) or\nGPU/CUDA (proposed direction)",
           fc="#FFFFFF", ec="#888888", fontsize=7.3)

arrow(ax, (1.9, 4.5), (2.3, 4.5), "description /\nform values")
arrow(ax, (4.6, 4.5), (5.0, 4.5), "raw params")
arrow(ax, (5.6, 4.0), (3.9, 3.3), "reads")
arrow(ax, (6.15, 4.0), (6.15, 2.1), "validated params")
arrow(ax, (7.3, 1.6), (7.6, 1.6), "writes")
for start_x in (5.0,):
    ax.plot([7.6, 7.6, 4.6], [1.85, 2.25, 2.25], color="#333333", lw=1.0)
ax.annotate("", xy=(4.6, 2.1), xytext=(4.6, 2.25),
            arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.0))
ax.text(6.1, 2.32, "read for display", fontsize=7.5, ha="center", color="#333333")
arrow(ax, (2.3, 1.6), (1.1, 4.0), "3D view +\nenergy chart")

ax.set_title("Fig. 3. Data Flow Diagram (Level 1)", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_dfd_v2.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Fig 5: Conceptual Framework / Class-Module Diagram ----------------
fig, ax = new_ax(9.6, 5.6)

box(ax, 0.3, 4.1, 2.7, 1.1, "LanguageUnderstanding\n+ extract(text): Params\n(prototype: rule-based;\ntarget: local SLM)", fc="#F1EAFB", ec="#6B4FA0", fontsize=8.3)
box(ax, 3.35, 4.1, 2.6, 1.1, "ParameterValidator\n+ validate(Params): bool\nphysical feasibility checks", fc="#F1EAFB", ec="#6B4FA0", fontsize=8.3)
box(ax, 6.3, 4.1, 3.0, 1.1, "SimulationConfig\nmodel, state, container,\nN, dt, total_time, ...", fc="#E3F5EC", ec="#22885F", fontsize=8.3)

box(ax, 0.9, 2.3, 3.2, 1.1, "SimulationEngine  (interface)\n+ run(SimulationConfig): Trajectory", fc="#E7F0FB", ec="#2B5F8A", fontsize=8.5, weight="bold")
box(ax, 0.3, 0.4, 3.1, 1.2, "CPUEngine\n(IMPLEMENTED\nthis prototype)\nLennard-Jones / Hard-Sphere", fc="#E3F5EC", ec="#22885F", fontsize=8.3, weight="bold")
box(ax, 3.7, 0.4, 3.1, 1.2, "CUDAEngine\n(PROPOSED,\nfuture work)\nGPU-accelerated kernels",
    fc="#FBEAE8", ec="#B0392F", fontsize=8.3, weight="bold", dashed=True)

box(ax, 7.3, 2.3, 2.0, 1.1, "Trajectory\npositions, energy\nover time", fc="#FBEAE8", ec="#B0392F", fontsize=8.3)
box(ax, 6.7, 0.4, 2.9, 1.2, "Visualizer\n+ render(Trajectory)\ninteractive 3D + energy chart", fc="#E7F0FB", ec="#2B5F8A", fontsize=8.3)

arrow(ax, (1.65, 4.1), (1.65, 3.4))
ax.text(1.75, 3.75, "produces", fontsize=7.5, color="#333333")
arrow(ax, (4.65, 4.1), (3.6, 3.4))
arrow(ax, (7.8, 4.1), (4.3, 3.4), "configures")
arrow(ax, (1.9, 2.3), (1.9, 1.6), "implements")
arrow(ax, (3.5, 2.3), (5.25, 1.6), "implements\n(planned)")
arrow(ax, (2.5, 2.3), (7.8, 2.75), "produces")
arrow(ax, (8.1, 2.3), (8.1, 1.6))

ax.set_title("Fig. 5. Conceptual Framework / Module Overview", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig5_class_v2.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Fig 6: Sequence Diagram (framework level) ----------------
fig, ax = new_ax(9.8, 6.0)

lanes = [("User", 0.9), ("Interface", 2.6), ("Language\nUnderstanding", 4.5),
         ("Simulation\nEngine", 6.6), ("Visualization", 8.7)]
top, bottom = 5.2, 0.4
for name, x in lanes:
    ax.add_patch(FancyBboxPatch((x - 0.75, top), 1.5, 0.5, fc="#EAF3F0", ec="#2F6F5E", lw=1.2,
                                 boxstyle="round,pad=0.02,rounding_size=0.04"))
    ax.text(x, top + 0.25, name, ha="center", va="center", fontsize=8, weight="bold")
    ax.plot([x, x], [bottom, top], color="#AAAAAA", lw=1.0, linestyle="--")

msgs = [
    (0.9, 2.6, 4.7, "describe simulation (NL or form)"),
    (2.6, 4.5, 4.3, "raw description / parameters"),
    (4.5, 4.5, 3.8, "extract + validate parameters"),
    (4.5, 2.6, 3.3, "structured, validated configuration"),
    (2.6, 6.6, 2.8, "run(configuration)"),
    (6.6, 6.6, 2.3, "execute (CPU prototype / GPU-CUDA future)"),
    (6.6, 8.7, 1.7, "real trajectory + energy"),
    (8.7, 2.6, 1.1, "render 3D view + energy chart"),
]
for x1, x2, y, text in msgs:
    arrow(ax, (x1, y), (x2, y), text, fontsize=7.3)

ax.set_title("Fig. 6. Sequence Diagram — Running a Simulation", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig6_sequence_v2.png"), bbox_inches="tight")
plt.close(fig)

print("done")
