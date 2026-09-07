"""
make_ppt_diagram_v4.py

A slide-proportioned version of the report's Fig. 2 (system architecture).

The report figure is drawn portrait, to sit in a column of A4 text. A slide is
landscape and is read from a distance, so the same diagram needs wider, shorter
layers and noticeably larger type. This draws the same four-layer architecture,
with the same conventions -- solid border = implemented, dashed = proposed --
so the deck and the report show a reader the same picture.

Run:  python deliverables/make_ppt_diagram_v4.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from diagram_style import *  # noqa: F401,F403

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures")
os.makedirs(OUT, exist_ok=True)


def architecture_slide():
    fig, ax = new_figure(9.2, 5.8)

    group_frame(ax, 50, 50, 97, 95, edge="#9AA5B1", dashed=True, lw=1.5)
    ax.text(3.8, 96.6, "LOCAL MACHINE  —  no network, no external AI API",
            ha="left", va="center", family=FONT, fontsize=8.6, color=MUTED,
            fontweight="bold")

    LX, LW = 48, 88

    # ---- Presentation ----------------------------------------------------
    group_frame(ax, LX, 84, LW, 20, dashed=False, lw=1.2, fill="#FEFAF3",
                edge=INPUT_EDGE, fontsize=8.6, label_color="#8A6220",
                label="PRESENTATION LAYER   browser")
    box(ax, 18, 81, 25, 13, "Setup panel\nnatural-language\nor manual entry",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=9.2)
    box(ax, 48, 81, 25, 13, "Review panel\nlive feasibility\ncheck",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=9.2)
    box(ax, 78, 81, 25, 13, "Run panel\n3D trajectory\n+ energy chart",
        fill=INPUT_FILL, edge=INPUT_EDGE, fontsize=9.2)

    # ---- Application -----------------------------------------------------
    group_frame(ax, LX, 58, LW, 22, dashed=False, lw=1.2, fill="#F6F9FC",
                edge=LOGIC_EDGE, fontsize=8.6, label_color="#1D4E7E",
                label="APPLICATION LAYER   Python · FastAPI")
    box(ax, 18, 55.5, 25, 13,
        "Language understanding\nextracts parameters\nonly — never physics",
        fill=LANG_FILL, edge=LANG_EDGE, fontsize=9.2)
    box(ax, 48, 55.5, 25, 13,
        "Parameter validation\nphysical feasibility\nbefore anything runs",
        fill=LOGIC_FILL, edge=LOGIC_EDGE, fontsize=9.2)
    box(ax, 78, 55.5, 25, 13,
        "Run orchestration\nconfigure · launch\n· collect results",
        fill=LOGIC_FILL, edge=LOGIC_EDGE, fontsize=9.2)

    # ---- Execution -------------------------------------------------------
    group_frame(ax, LX, 32, LW, 21, dashed=False, lw=1.2, fill="#F5FAF8",
                edge=ENGINE_EDGE, fontsize=8.6, label_color="#156046",
                label="EXECUTION LAYER   fixed, hand-verified engine")
    box(ax, 27, 29.5, 38, 13, "", fill=ENGINE_FILL, edge=ENGINE_EDGE, lw=1.8)
    ax.text(27, 33.0, "CPU ENGINE  ·  IMPLEMENTED", ha="center", va="center",
            family=FONT, fontsize=9.6, color=INK, fontweight="bold")
    ax.text(27, 27.6,
            "C++11, compiled once\nLennard-Jones and Hard-Sphere",
            ha="center", va="center", family=FONT, fontsize=8.8, color=INK,
            linespacing=1.7)

    box(ax, 72, 29.5, 34, 13, "", fill=FUTURE_FILL, edge=FUTURE_EDGE, lw=1.8,
        dashed=True)
    ax.text(72, 33.0, "GPU / CUDA  ·  PROPOSED", ha="center", va="center",
            family=FONT, fontsize=9.6, color=INK, fontweight="bold")
    ax.text(72, 27.6,
            "same interface, same config\nforce loop becomes kernels",
            ha="center", va="center", family=FONT, fontsize=8.8, color=INK,
            linespacing=1.7)

    # ---- Output ----------------------------------------------------------
    group_frame(ax, LX, 9, LW, 13, dashed=False, lw=1.2, fill="#F7F8FA",
                edge=DATA_EDGE, fontsize=8.6, label_color="#465361",
                label="RUN OUTPUT")
    box(ax, 32, 6.5, 30, 7, "trajectory.json", fill=DATA_FILL, edge=DATA_EDGE,
        fontsize=9.0)
    box(ax, 68, 6.5, 28, 7, "energy.csv", fill=DATA_FILL, edge=DATA_EDGE,
        fontsize=9.0)

    # ---- Connectors ------------------------------------------------------
    arrow(ax, (18, 74.5), (18, 62), label=None)
    ax.text(19.6, 68.5, "description", ha="left", va="center", family=FONT,
            fontsize=8.0, color=MUTED)
    arrow(ax, (48, 74.5), (48, 62), label=None)
    ax.text(49.6, 68.5, "parameters", ha="left", va="center", family=FONT,
            fontsize=8.0, color=MUTED)
    arrow(ax, (30.7, 55.5), (35.3, 55.5), label=None)
    arrow(ax, (60.7, 55.5), (65.3, 55.5), label=None)

    elbow(ax, [(78, 49), (78, 45), (27, 45), (27, 36)], label=None)
    ax.text(52, 47.0, "validated configuration", ha="center", va="center",
            family=FONT, fontsize=8.0, color=MUTED,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none"))
    elbow(ax, [(60, 45), (72, 45), (72, 36)], dashed=True)

    arrow(ax, (24, 23), (24, 10), label=None)
    ax.text(22.4, 17.0, "writes", ha="right", va="center", family=FONT,
            fontsize=8.0, color=MUTED)
    elbow(ax, [(40, 23), (40, 18.5), (62, 18.5), (62, 10)], label=None)
    elbow(ax, [(84, 23), (84, 18.5), (76, 18.5), (76, 10)], dashed=True)

    elbow(ax, [(82, 6.5), (94.5, 6.5), (94.5, 81), (90.7, 81)], label=None)
    ax.text(96.4, 44.0, "read back and visualised", ha="center", va="center",
            family=FONT, fontsize=8.0, color=MUTED, rotation=90)

    path = os.path.join(OUT, "fig2_architecture_slide.png")
    save(fig, path, dpi=220)
    return path


if __name__ == "__main__":
    p = architecture_slide()
    from PIL import Image
    with Image.open(p) as im:
        print(f"pixels {im.size}, aspect {im.size[0] / im.size[1]:.3f}")
