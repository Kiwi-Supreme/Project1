"""
Redesigns the Gantt chart, Level-1 DFD, and Class diagram to match the
reference conventions the user provided:
  - Gantt: Excel-style task table + date-axis bar chart (light green header,
    task/start/end columns, gridlines).
  - DFD: Gane-Sarson notation -- two-part numbered process boxes, open
    (top/bottom-only) data-store rectangles, square external entities.
  - Class diagram: proper UML -- 3-compartment class boxes (name /
    attributes / operations), +/- visibility, hollow-triangle generalization
    arrows for the two engine subclasses, dashed dependency arrows elsewhere.
"""
import os
import datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, Polygon
from matplotlib.lines import Line2D

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

GREEN_HEADER = "#2F6F5E"
GREEN_LIGHT = "#EAF3F0"
BORDER = "#B9C7C2"


# ============================================================
# Fig 1: Gantt chart, Excel-style
# ============================================================
tasks = [
    ("Phase 1 - Study & baseline 2024 C++ code", 0, 1),
    ("Phase 2 - Define simulation scope", 1, 1),
    ("Phase 3 - Build parameterized C++ engine", 2, 2),
    ("Phase 4 - Local language-extraction module", 4, 2),
    ("Phase 5 - Connect extraction to engine", 5, 1),
    ("Phase 6 - Backend integration", 6, 1),
    ("Phase 7 - Frontend build", 6, 2),
    ("Phase 8 - 3D trajectory visualization", 7, 2),
    ("Phase 9 - Testing (validation, engine, UI)", 9, 1),
    ("Phase 10 - Review preparation", 10, 1),
]
n_weeks = 11
row_h = 0.42
fig_h = 1.4 + row_h * (len(tasks) + 1)
fig, ax = plt.subplots(figsize=(11, fig_h), dpi=200)

# left task-name column + bar area, drawn as a bordered "worksheet"
task_col_w = 4.3
bar_area_w = n_weeks
total_w = task_col_w + bar_area_w
top_y = row_h * (len(tasks) + 1)

# header row
ax.add_patch(Rectangle((0, top_y - row_h), task_col_w, row_h, fc=GREEN_HEADER, ec="white", lw=1))
ax.text(0.1, top_y - row_h / 2, "Task", va="center", ha="left", fontsize=9.5, color="white", weight="bold")
for w in range(n_weeks):
    ax.add_patch(Rectangle((task_col_w + w, top_y - row_h), 1, row_h, fc=GREEN_HEADER, ec="white", lw=1))
    ax.text(task_col_w + w + 0.5, top_y - row_h / 2, f"Wk {w+1}", va="center", ha="center",
             fontsize=7, color="white", weight="bold")

for i, (name, start, dur) in enumerate(tasks):
    y = top_y - row_h * (i + 2)
    fc = "#FFFFFF" if i % 2 == 0 else "#F4F8F6"
    ax.add_patch(Rectangle((0, y), task_col_w, row_h, fc=fc, ec=BORDER, lw=0.8))
    ax.text(0.12, y + row_h / 2, name, va="center", ha="left", fontsize=8.3)
    for w in range(n_weeks):
        ax.add_patch(Rectangle((task_col_w + w, y), 1, row_h, fc=fc, ec=BORDER, lw=0.6))
    bar = Rectangle((task_col_w + start, y + row_h * 0.14), dur, row_h * 0.72,
                     fc="#3E8E7E", ec="#255B4F", lw=0.8)
    ax.add_patch(bar)

ax.set_xlim(0, total_w)
ax.set_ylim(0, top_y)
ax.axis("off")
ax.set_title("Fig. 1. Project Plan (Gantt Chart)", fontsize=12, weight="bold", pad=14, loc="center")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_gantt_v2.png"), bbox_inches="tight")
plt.close(fig)


# ============================================================
# Fig 3: Level-1 DFD, Gane-Sarson notation
# ============================================================
def entity(ax, x, y, w, h, text, fontsize=9):
    ax.add_patch(Rectangle((x, y), w, h, fc="#FDF3E3", ec="#9C6A16", lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, weight="bold")


def process(ax, x, y, w, h, number, name, fontsize=8.6):
    head_h = 0.34
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec="#2B5F8A", lw=1.4))
    ax.plot([x, x + w], [y + h - head_h, y + h - head_h], color="#2B5F8A", lw=1.2)
    ax.plot([x, x + head_h * 1.05], [y + h - head_h, y + h - head_h], color="#2B5F8A", lw=0)
    ax.add_patch(Rectangle((x, y + h - head_h), head_h * 1.3, head_h, fc="#E7F0FB", ec="#2B5F8A", lw=1.0))
    ax.text(x + head_h * 0.65, y + h - head_h / 2, number, ha="center", va="center", fontsize=8, weight="bold")
    ax.text(x + w / 2 + 0.15, y + (h - head_h) / 2, name, ha="center", va="center", fontsize=fontsize)


def datastore(ax, x, y, w, h, tag, name, fontsize=8.3):
    tab_w = 0.35
    ax.plot([x, x, x + tab_w], [y, y + h, y + h], color="#6B4FA0", lw=1.3)
    ax.plot([x, x, x + tab_w], [y, y, y], color="#6B4FA0", lw=1.3)
    ax.plot([x + tab_w, x + tab_w], [y, y + h], color="#6B4FA0", lw=1.3)
    ax.plot([x + tab_w, x + w], [y, y], color="#6B4FA0", lw=1.3)
    ax.plot([x + tab_w, x + w], [y + h, y + h], color="#6B4FA0", lw=1.3)
    ax.text(x + tab_w / 2, y + h / 2, tag, ha="center", va="center", fontsize=8, weight="bold")
    ax.text(x + tab_w + (w - tab_w) / 2, y + h / 2, name, ha="center", va="center", fontsize=fontsize)


def arrow(ax, p1, p2, text=None, fontsize=7.6):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12, lw=1.1, color="#333333")
    ax.add_patch(a)
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.09, text, ha="center", va="bottom", fontsize=fontsize, color="#333333")


fig, ax = plt.subplots(figsize=(10.4, 6.2), dpi=200)
ax.set_xlim(0, 10.4)
ax.set_ylim(0, 6.2)
ax.axis("off")

entity(ax, 0.3, 4.3, 1.6, 1.0, "User")
process(ax, 2.3, 4.3, 2.4, 1.0, "1.0", "Collect Input\n(NL or manual)")
process(ax, 5.1, 4.3, 2.6, 1.0, "2.0", "Extract & Validate\nParameters")
datastore(ax, 2.5, 2.8, 2.5, 0.75, "D1", "Parameter Schema")
process(ax, 5.1, 1.4, 2.6, 1.0, "3.0", "Configure &\nExecute Simulation")
datastore(ax, 8.0, 1.4, 2.1, 0.75, "D2", "Trajectory + Energy")
process(ax, 2.3, 1.4, 2.4, 1.0, "4.0", "Visualize Results")

arrow(ax, (1.9, 4.8), (2.3, 4.8), "description /\nform values")
arrow(ax, (4.7, 4.8), (5.1, 4.8), "raw params")
arrow(ax, (5.7, 4.3), (4.0, 3.55), "reads")
arrow(ax, (6.4, 4.3), (6.4, 2.4), "validated params")
arrow(ax, (7.7, 1.9), (8.0, 1.9), "writes")
ax.plot([8.5, 8.5, 4.7], [1.65, 1.15, 1.15], color="#333333", lw=1.0)
ax.annotate("", xy=(4.7, 1.4), xytext=(4.7, 1.15),
            arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.0))
ax.text(6.6, 0.95, "read for display", fontsize=7.6, ha="center", color="#333333")
arrow(ax, (2.3, 1.9), (1.1, 4.3), "3D view + energy chart")

# legend
ax.add_patch(Rectangle((0.3, 0.15), 0.35, 0.25, fc="#FDF3E3", ec="#9C6A16", lw=1.2))
ax.text(0.75, 0.27, "External Entity", fontsize=7.5, va="center")
ax.add_patch(Rectangle((2.6, 0.15), 0.35, 0.25, fc="white", ec="#2B5F8A", lw=1.2))
ax.text(3.05, 0.27, "Process", fontsize=7.5, va="center")
ax.text(5.0, 0.15, "D1", fontsize=7, ha="center", weight="bold")
ax.plot([5.2, 5.2, 5.55, 5.55, 5.2], [0.15, 0.4, 0.4, 0.15, 0.15], color="#6B4FA0", lw=1.2)
ax.text(6.0, 0.27, "Data Store", fontsize=7.5, va="center")

ax.set_title("Fig. 3. Level-1 Data Flow Diagram (Gane-Sarson Notation)", fontsize=11.5, weight="bold", pad=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig3_dfd_v3.png"), bbox_inches="tight")
plt.close(fig)


# ============================================================
# Fig 5: UML Class Diagram
# ============================================================
def uml_class(ax, x, y, w, h, name, attrs, ops, abstract=False, header_fc="#E7F0FB", ec="#2B5F8A"):
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=ec, lw=1.4))
    name_h = 0.42
    attr_h = 0.24 * max(len(attrs), 1) + 0.1
    ax.add_patch(Rectangle((x, y + h - name_h), w, name_h, fc=header_fc, ec=ec, lw=1.2))
    label = name if not abstract else f"«interface»\n{name}"
    ax.text(x + w / 2, y + h - name_h / 2, label, ha="center", va="center", fontsize=9.3, weight="bold")
    ax.plot([x, x + w], [y + h - name_h - attr_h, y + h - name_h - attr_h], color=ec, lw=1.0)
    ay = y + h - name_h - 0.16
    for a in attrs:
        ax.text(x + 0.12, ay, a, fontsize=7.6, va="center", family="monospace")
        ay -= 0.24
    oy = y + h - name_h - attr_h - 0.16
    for o in ops:
        ax.text(x + 0.12, oy, o, fontsize=7.6, va="center", family="monospace")
        oy -= 0.24


def generalization(ax, x1, y1, x2, y2, dashed=False):
    ax.plot([x1, x2], [y1, y2], color="#333333", lw=1.2, linestyle=(0, (5, 3)) if dashed else "solid")
    # hollow triangle at (x2, y2), pointing along the line direction
    import numpy as np
    dx, dy = x2 - x1, y2 - y1
    length = (dx**2 + dy**2) ** 0.5
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 0.18
    tip = (x2, y2)
    base1 = (x2 - ux * size * 1.8 + px * size, y2 - uy * size * 1.8 + py * size)
    base2 = (x2 - ux * size * 1.8 - px * size, y2 - uy * size * 1.8 - py * size)
    ax.add_patch(Polygon([tip, base1, base2], closed=True, fc="white", ec="#333333", lw=1.2, zorder=5))


def dependency(ax, x1, y1, x2, y2, text=None):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=12, lw=1.0,
                         color="#555555", linestyle=(0, (4, 3)))
    ax.add_patch(a)
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.1, text, fontsize=7.3, ha="center", color="#555555", style="italic")


fig, ax = plt.subplots(figsize=(11, 6.6), dpi=200)
ax.set_xlim(0, 11)
ax.set_ylim(0, 6.6)
ax.axis("off")

uml_class(ax, 0.3, 4.6, 2.9, 1.7, "LanguageUnderstanding",
          ["- mode: string  { rule-based | SLM }"],
          ["+ extract(text: string): ParamSet"], header_fc="#F1EAFB", ec="#6B4FA0")
uml_class(ax, 3.5, 4.6, 2.7, 1.5, "ParameterValidator",
          [],
          ["+ validate(p: ParamSet): bool"], header_fc="#F1EAFB", ec="#6B4FA0")
uml_class(ax, 6.5, 4.6, 4.2, 1.9, "SimulationConfig",
          ["- model: string", "- state: string", "- particleCount: int",
           "- timestep: float", "- totalTime: float"],
          [], header_fc="#E3F5EC", ec="#22885F")

uml_class(ax, 3.4, 2.85, 4.3, 1.15, "SimulationEngine", [],
          ["+ run(cfg: SimulationConfig): Trajectory"], abstract=True, header_fc="#E7F0FB", ec="#2B5F8A")

uml_class(ax, 0.3, 0.3, 3.9, 1.55, "CPUEngine  (implemented)",
          [], ["+ run(cfg: SimulationConfig): Trajectory"], header_fc="#E3F5EC", ec="#22885F")
ax.add_patch(Rectangle((4.5, 0.3), 3.9, 1.55, fc="#FBEAE8", ec="#B0392F", lw=1.4,
                        linestyle=(0, (5, 3))))
ax.text(4.5 + 3.9 / 2, 0.3 + 1.55 - 0.22, "CUDAEngine  (proposed)", ha="center", va="center",
        fontsize=9.3, weight="bold")
ax.plot([4.5, 4.5 + 3.9], [0.3 + 1.55 - 0.44, 0.3 + 1.55 - 0.44], color="#B0392F", lw=1.0)
ax.text(4.5 + 0.12, 0.3 + 1.55 - 0.65, "+ run(cfg: SimulationConfig): Trajectory", fontsize=7.6,
        family="monospace")

uml_class(ax, 8.9, 2.85, 2.0, 1.15, "Trajectory",
          ["- positions: list", "- energy: list"], [], header_fc="#FBEAE8", ec="#B0392F")
uml_class(ax, 8.6, 0.3, 2.3, 1.2, "Visualizer", [],
          ["+ render(t: Trajectory): void"], header_fc="#E7F0FB", ec="#2B5F8A")

# relationships
dependency(ax, 3.2, 5.45, 3.5, 5.45, "produces")
dependency(ax, 6.2, 5.3, 6.5, 5.5, "configures")
generalization(ax, 2.2, 1.85, 3.9, 2.85, dashed=True)
generalization(ax, 6.5, 1.85, 5.5, 2.85, dashed=True)
ax.text(2.4, 2.35, "realizes", fontsize=7.3, style="italic", color="#333333")
ax.text(6.1, 2.35, "realizes\n(planned)", fontsize=7.3, style="italic", color="#333333")
dependency(ax, 7.7, 3.4, 8.9, 3.4, "produces")
dependency(ax, 9.8, 2.85, 9.7, 1.5, "uses")

ax.set_title("Fig. 5. UML Class Diagram — Conceptual Framework", fontsize=12, weight="bold", pad=14)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig5_class_v3.png"), bbox_inches="tight")
plt.close(fig)

print("done")
