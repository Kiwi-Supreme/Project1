"""
Generates the report's figures as plain PNG images using matplotlib only
(no internet, no external drawing tool). Run once; writes into
deliverables/figures/.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Ellipse
from matplotlib.lines import Line2D

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

BOX = dict(boxstyle="round,pad=0.35,rounding_size=0.08", linewidth=1.3)


def box(ax, x, y, w, h, text, fc="#EAF3F0", ec="#2F6F5E", fontsize=10, weight="normal"):
    p = FancyBboxPatch((x, y), w, h, fc=fc, ec=ec, lw=1.3, boxstyle="round,pad=0.02,rounding_size=0.04")
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
             weight=weight, wrap=True)
    return (x, y, w, h)


def arrow(ax, p1, p2, text=None, fontsize=8, style="-|>"):
    a = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=14, lw=1.2, color="#333333")
    ax.add_patch(a)
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.08, text, ha="center", va="bottom", fontsize=fontsize, color="#333333")


def new_ax(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


# ---------------- Figure 2: System Architecture ----------------
fig, ax = new_ax(9, 6)

fb = box(ax, 0.5, 4.6, 3.2, 1.0, "Frontend\n(HTML / CSS / JavaScript)\nSetup - Review - Run UI", fc="#E7F0FB", ec="#2B5F8A")
be = box(ax, 3.3, 3.0, 2.6, 1.0, "Backend (Python, FastAPI)\n/api/extract  /api/validate\n/api/simulate", fc="#FDF3E3", ec="#9C6A16")
nlp = box(ax, 0.5, 3.0, 2.4, 0.8, "Local NLP Extractor\n(rule-based, offline)", fc="#F1EAFB", ec="#6B4FA0")
val = box(ax, 0.5, 1.9, 2.4, 0.8, "Parameter Validator\n(pydantic, shared)", fc="#F1EAFB", ec="#6B4FA0")
eng = box(ax, 3.3, 1.0, 2.6, 1.0, "C++ Simulation Engine\n(compiled once, md_engine)\nLJ / Hard-Sphere, boundaries", fc="#E3F5EC", ec="#22885F")
out = box(ax, 6.3, 1.0, 2.2, 1.0, "trajectory.json\nenergy.csv", fc="#FBEAE8", ec="#B0392F", fontsize=9)
viz = box(ax, 6.3, 3.6, 2.2, 1.4, "3D Renderer +\nTrajectory Player +\nEnergy Chart\n(real data playback)", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)

arrow(ax, (2.1, 4.6), (2.1, 3.8), "text / form")
arrow(ax, (2.9, 3.4), (3.3, 3.4), "extract()")
arrow(ax, (1.7, 3.0), (1.7, 2.7))
arrow(ax, (2.9, 2.3), (3.3, 3.4), "validate()")
arrow(ax, (4.6, 3.0), (4.6, 2.0), "simulate()\nwrite config")
arrow(ax, (5.9, 1.5), (6.3, 1.5), "writes")
arrow(ax, (7.4, 2.0), (7.4, 3.6), "read files")
arrow(ax, (6.3, 4.1), (5.9, 3.6), "response JSON")
arrow(ax, (7.4, 4.6), (3.7, 5.1), "trajectory + energy")

ax.set_title("Fig. 2. System Architecture", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_architecture.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Figure 3: Data Flow Diagram (Level 0/1) ----------------
fig, ax = new_ax(9, 5.4)

u = box(ax, 0.3, 3.9, 1.6, 1.0, "User", fc="#FDF3E3", ec="#9C6A16")
p1 = box(ax, 2.3, 3.9, 2.2, 1.0, "1.0\nCollect Input\n(manual / NL)", fc="#E7F0FB", ec="#2B5F8A")
p2 = box(ax, 5.0, 3.9, 2.2, 1.0, "2.0\nExtract & Validate\nParameters", fc="#E7F0FB", ec="#2B5F8A")
d1 = box(ax, 2.3, 2.4, 2.2, 0.8, "D1  Parameter\nSchema / Presets", fc="#F1EAFB", ec="#6B4FA0", fontsize=9)
p3 = box(ax, 5.0, 1.0, 2.2, 1.0, "3.0\nRun MD\nSimulation", fc="#E7F0FB", ec="#2B5F8A")
d2 = box(ax, 7.6, 1.0, 1.4, 1.0, "D2\nTrajectory +\nEnergy Files", fc="#FBEAE8", ec="#B0392F", fontsize=8)
p4 = box(ax, 2.3, 1.0, 2.2, 1.0, "4.0\nVisualize\nResults", fc="#E7F0FB", ec="#2B5F8A")

arrow(ax, (1.9, 4.4), (2.3, 4.4), "description /\nform values")
arrow(ax, (4.5, 4.4), (5.0, 4.4), "raw params")
arrow(ax, (5.5, 3.9), (3.9, 3.2), "reads")
arrow(ax, (6.1, 3.9), (6.1, 2.0), "validated params")
arrow(ax, (7.2, 1.5), (7.6, 1.5), "writes")
ax.annotate("", xy=(5.2, 1.35), xytext=(7.6, 1.75),
            arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.2,
                             connectionstyle="arc3,rad=0.18"))
ax.text(6.55, 2.05, "read for display", ha="center", fontsize=8, color="#333333")
arrow(ax, (2.3, 1.5), (1.1, 3.9), "3D view +\nenergy chart", style="-|>")

ax.set_title("Fig. 3. Data Flow Diagram (Level 1)", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_dfd.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Figure 4: Use Case Diagram ----------------
fig, ax = new_ax(8, 6)

# actor (stick figure, simple)
ax.add_patch(Ellipse((1.0, 5.0), 0.5, 0.5, fc="#FDF3E3", ec="#9C6A16", lw=1.3))
ax.plot([1.0, 1.0], [4.75, 3.9], color="#9C6A16", lw=1.3)
ax.plot([0.6, 1.4], [4.4, 4.4], color="#9C6A16", lw=1.3)
ax.plot([1.0, 0.65], [3.9, 3.4], color="#9C6A16", lw=1.3)
ax.plot([1.0, 1.35], [3.9, 3.4], color="#9C6A16", lw=1.3)
ax.text(1.0, 3.1, "User", ha="center", fontsize=10, weight="bold")

boundary = FancyBboxPatch((2.6, 0.4), 5.1, 5.3, fc="none", ec="#333333", lw=1.2,
                           boxstyle="round,pad=0.02,rounding_size=0.05")
ax.add_patch(boundary)
ax.text(5.15, 5.85, "MD Simulation Prototype", ha="center", fontsize=10, weight="bold")

usecases = [
    "Describe Simulation\nin Natural Language",
    "Enter Parameters\nManually",
    "Review & Validate\nParameters",
    "Choose Model, State\n& Container",
    "Run Molecular\nDynamics Simulation",
    "View Interactive\n3D Trajectory",
    "View Energy-vs-Time\nChart",
]
ys = [5.2, 4.4, 3.6, 2.8, 2.0, 1.2, 0.6]
for text, yc in zip(usecases, ys):
    ax.add_patch(Ellipse((5.15, yc), 2.9, 0.66, fc="#E7F0FB", ec="#2B5F8A", lw=1.2))
    ax.text(5.15, yc, text, ha="center", va="center", fontsize=8)
    ax.plot([1.3, 3.6], [4.6, yc], color="#888888", lw=0.8)

ax.set_xlim(0, 8)
ax.set_ylim(0, 6.3)
ax.set_title("Fig. 4. Use Case Diagram", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig4_usecase.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Figure 5: Module / Class Overview ----------------
fig, ax = new_ax(9, 5.2)

box(ax, 0.4, 3.6, 2.4, 1.2, "Particle\n{x,y,z, vx,vy,vz,\nfx,fy,fz}", fc="#E3F5EC", ec="#22885F", fontsize=9)
box(ax, 3.1, 3.6, 2.4, 1.2, "SimConfig\nmodel, state, container,\nN, dt, total_time ...", fc="#E3F5EC", ec="#22885F", fontsize=9)
box(ax, 5.8, 3.6, 2.6, 1.2, "TrajectoryWriter\nwrite_frame()\nwrite_energy()", fc="#E3F5EC", ec="#22885F", fontsize=9)
box(ax, 0.4, 2.0, 2.9, 1.2, "SimParams (pydantic)\nrange + feasibility checks", fc="#F1EAFB", ec="#6B4FA0", fontsize=9)
box(ax, 3.6, 2.0, 2.9, 1.2, "extract_parameters()\nlocal rule-based NLP", fc="#F1EAFB", ec="#6B4FA0", fontsize=9)
box(ax, 6.8, 2.0, 1.9, 1.2, "run_simulation()\nengine runner", fc="#F1EAFB", ec="#6B4FA0", fontsize=8)
box(ax, 1.2, 0.4, 2.6, 1.2, "Scene3D\nrotate / zoom / render", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)
box(ax, 4.2, 0.4, 2.9, 1.2, "TrajectoryPlayer\nreal-frame playback", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)

ax.text(0.4, 5.0, "C++ engine", fontsize=9, style="italic", color="#22885F")
ax.text(0.4, 3.35, "Python backend", fontsize=9, style="italic", color="#6B4FA0")
ax.text(1.2, 1.75, "JavaScript frontend", fontsize=9, style="italic", color="#2B5F8A")

ax.set_title("Fig. 5. Module / Class Overview", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig5_class.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Figure 6: Sequence Diagram (Run flow) ----------------
fig, ax = new_ax(9.6, 6)

lanes = [("User", 0.9), ("Frontend", 2.7), ("Backend", 4.7), ("C++ Engine", 6.7), ("Output Files", 8.6)]
top, bottom = 5.6, 0.4
for name, x in lanes:
    ax.add_patch(FancyBboxPatch((x - 0.7, top), 1.4, 0.4, fc="#EAF3F0", ec="#2F6F5E", lw=1.2,
                                 boxstyle="round,pad=0.02,rounding_size=0.04"))
    ax.text(x, top + 0.2, name, ha="center", va="center", fontsize=8.5, weight="bold")
    ax.plot([x, x], [bottom, top], color="#AAAAAA", lw=1.0, linestyle="--")

msgs = [
    (0.9, 2.7, 5.1, "click 'Proceed with simulation'"),
    (2.7, 4.7, 4.7, "POST /api/simulate (params)"),
    (4.7, 4.7, 4.3, "validate_params()"),
    (4.7, 6.7, 3.7, "write config.txt, run md_engine"),
    (6.7, 8.6, 3.1, "write trajectory.json, energy.csv"),
    (8.6, 4.7, 2.5, "files ready"),
    (4.7, 2.7, 1.9, "{params, trajectory, energy}"),
    (2.7, 0.9, 1.3, "render 3D view + energy chart"),
]
for x1, x2, y, text in msgs:
    arrow(ax, (x1, y), (x2, y), text, fontsize=7.5)

ax.set_title("Fig. 6. Sequence Diagram - Running a Simulation", fontsize=11, weight="bold", pad=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig6_sequence.png"), bbox_inches="tight")
plt.close(fig)

# ---------------- Figure 1: Project Plan Gantt Chart ----------------
fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)

phases = [
    ("1. Study & baseline 2024 C++ code", 1, 1),
    ("2. Define simulation scope", 2, 1),
    ("3. Build parameterized C++ engine", 3, 2),
    ("4. Local NLP extraction module", 4, 2),
    ("5. Connect NLP output to engine", 5, 1),
    ("6. Backend integration (FastAPI)", 6, 1),
    ("7. Frontend build (HTML/CSS/JS)", 6, 2),
    ("8. 3D trajectory visualization", 7, 2),
    ("9. Testing (validation, engine, UI)", 9, 1),
    ("10. Review 2 preparation", 10, 1),
]
colors = plt.cm.get_cmap("tab10")
for i, (label, start, dur) in enumerate(phases):
    y = len(phases) - i
    ax.barh(y, dur, left=start, height=0.55, color=colors(i % 10), edgecolor="#333333", linewidth=0.8)
    ax.text(start + dur + 0.15, y, label, va="center", fontsize=8.5)

ax.set_yticks([])
ax.set_xlim(0.5, 15.5)
ax.set_ylim(0.3, len(phases) + 0.8)
ax.set_xticks(range(1, 11))
ax.set_xticklabels([f"Wk {w}" for w in range(1, 11)], fontsize=8.5)
ax.set_xlabel("Project Week", fontsize=9)
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)
ax.grid(axis="x", color="#DDDDDD", linewidth=0.6, zorder=0)
ax.set_axisbelow(True)
ax.set_title("Fig. 1. Project Plan (Gantt Chart)", fontsize=11, weight="bold", pad=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_gantt.png"), bbox_inches="tight")
plt.close(fig)

print("wrote figures to", OUT)
