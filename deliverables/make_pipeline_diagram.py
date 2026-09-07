"""Redraws the Slide 8 framework diagram to be backend-agnostic: CPU (this
review's prototype) and CUDA/GPU (the intended direction) shown as two
swappable execution options under one pipeline, not two separate projects."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)


def box(ax, x, y, w, h, text, fc="#EAF3F0", ec="#2F6F5E", fontsize=10, weight="normal"):
    p = FancyBboxPatch((x, y), w, h, fc=fc, ec=ec, lw=1.3, boxstyle="round,pad=0.02,rounding_size=0.04")
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, weight=weight)
    return (x, y, w, h)


def arrow(ax, p1, p2, text=None, fontsize=8):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=14, lw=1.2, color="#333333")
    ax.add_patch(a)
    if text:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx, my + 0.1, text, ha="center", va="bottom", fontsize=fontsize, color="#333333")


fig, ax = plt.subplots(figsize=(10, 6.4), dpi=200)
ax.set_xlim(0, 10)
ax.set_ylim(0, 6.4)
ax.axis("off")

nl = box(ax, 0.3, 5.0, 2.6, 0.9, "Natural-Language\nDescription", fc="#FDF3E3", ec="#9C6A16", fontsize=9)
man = box(ax, 0.3, 3.9, 2.6, 0.9, "Manual Parameter\nEntry", fc="#FDF3E3", ec="#9C6A16", fontsize=9)
slm = box(ax, 3.4, 4.45, 2.8, 1.1, "Local Language\nUnderstanding (SLM)\nextracts parameters only", fc="#F1EAFB", ec="#6B4FA0", fontsize=9)
val = box(ax, 3.4, 3.1, 2.8, 0.9, "Parameter Validation\n(physical feasibility)", fc="#F1EAFB", ec="#6B4FA0", fontsize=9)
cfg = box(ax, 3.4, 1.9, 2.8, 0.9, "Simulation Configuration\n(fixed, hand-verified logic)", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)
cpu = box(ax, 2.4, 0.4, 2.3, 1.0, "CPU Execution\n(THIS REVIEW'S\nPROTOTYPE)", fc="#E3F5EC", ec="#22885F", fontsize=8.5, weight="bold")
gpu = box(ax, 5.1, 0.4, 2.3, 1.0, "GPU / CUDA Execution\n(INTENDED DIRECTION,\nFUTURE WORK)", fc="#FBEAE8", ec="#B0392F", fontsize=8.5, weight="bold")
out = box(ax, 7.1, 3.1, 2.6, 0.9, "Real Trajectory +\nEnergy Output", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)
viz = box(ax, 7.1, 4.45, 2.6, 1.1, "Interactive 3D\nVisualization", fc="#E7F0FB", ec="#2B5F8A", fontsize=9)

arrow(ax, (2.9, 5.45), (3.4, 5.0))
arrow(ax, (2.9, 4.35), (3.4, 5.0))
arrow(ax, (4.8, 4.45), (4.8, 4.0))
arrow(ax, (4.8, 3.1), (4.8, 2.8))
arrow(ax, (4.0, 1.9), (3.55, 1.4))
arrow(ax, (5.6, 1.9), (6.25, 1.4))

# "writes" paths routed BELOW everything and up the right margin, so they
# never cross the Simulation Configuration box.
for start_x, label_y in [(4.7, 0.15), (7.4, 0.15)]:
    ax.plot([start_x, start_x, 8.4, 8.4], [0.9, 0.15, 0.15, 3.1],
            color="#333333", lw=1.1, zorder=1)
ax.annotate("", xy=(8.4, 3.1), xytext=(8.4, 3.0),
            arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.1))
ax.text(8.4, 0.02, "writes", ha="center", fontsize=8, color="#333333")

arrow(ax, (8.4, 4.0), (8.4, 4.45))

ax.text(4.8, 5.9, "Two swappable execution backends,\none pipeline", ha="center", fontsize=9.5, style="italic", color="#444444")
ax.set_title("Fig. Proposed Framework — Natural-Language / SLM to Simulation Pipeline", fontsize=11, weight="bold", pad=14)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_pipeline.png"), bbox_inches="tight")
plt.close(fig)
print("wrote fig_pipeline.png")
