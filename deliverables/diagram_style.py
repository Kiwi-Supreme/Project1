"""
diagram_style.py

Shared drawing helpers for the report figures (make_report_diagrams_v4.py).

Everything here is plain matplotlib -- no Visio, no draw.io, no downloaded
images -- so every figure in the report can be regenerated from source at
any time. The helpers exist so that all six figures share one visual
language (same fonts, same line weights, same palette, same corner radius)
instead of each script inventing its own.

Two conventions are used consistently across every figure and are worth
knowing before reading them:

  * A SOLID border means "implemented and demonstrated in this project".
  * A DASHED border means "proposed / future work" -- the GPU-CUDA engine
    and the full local SLM. Nothing dashed is claimed as working.
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import (
    FancyBboxPatch, Rectangle, Ellipse, Circle, FancyArrowPatch, PathPatch
)
from matplotlib.path import Path


# --------------------------------------------------------------------------
# Palette -- muted, print-safe, and readable in greyscale (each fill has a
# clearly different lightness, so a black-and-white printout still separates
# the layers).
# --------------------------------------------------------------------------
INK = "#1F2933"        # primary text and strong borders
LINE = "#3E4C59"       # connector lines
MUTED = "#7B8794"      # secondary text, notes
GRID = "#CBD2D9"       # light rules and boundaries

INPUT_FILL, INPUT_EDGE = "#FDF3E3", "#B07D2B"      # user-facing input
LANG_FILL, LANG_EDGE = "#EFE8FA", "#6B4FA8"        # language understanding
LOGIC_FILL, LOGIC_EDGE = "#E4EEF9", "#26619C"      # orchestration / validation
ENGINE_FILL, ENGINE_EDGE = "#E3F3EC", "#1B7A5A"    # implemented computation
FUTURE_FILL, FUTURE_EDGE = "#FBE9E7", "#B3261E"    # proposed / future work
DATA_FILL, DATA_EDGE = "#F2F4F7", "#52606D"        # data stores / artefacts

FONT = "Arial"


def new_figure(width, height):
    """Creates a blank, axis-free canvas in a 0-100 x 0-100 coordinate space,
    so every figure positions boxes in the same easy-to-reason-about units."""
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_aspect("auto")
    fig.patch.set_facecolor("white")
    return fig, ax


def save(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.12,
                facecolor="white")
    plt.close(fig)
    print("wrote", path)


# --------------------------------------------------------------------------
# Basic shapes
# --------------------------------------------------------------------------
def box(ax, x, y, w, h, text, fill="white", edge=INK, fontsize=9,
        bold=False, dashed=False, radius=0.9, lw=1.4, text_color=INK,
        align="center", zorder=3):
    """A rounded rectangle with centred (or left-aligned) text inside it.
    x, y is the CENTRE of the box."""
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=lw, edgecolor=edge, facecolor=fill,
        linestyle=(0, (4, 2.5)) if dashed else "solid", zorder=zorder,
    )
    ax.add_patch(patch)
    if text:
        ha = "center" if align == "center" else "left"
        tx = x if align == "center" else x - w / 2 + 1.6
        ax.text(tx, y, text, ha=ha, va="center", fontsize=fontsize,
                family=FONT, color=text_color,
                fontweight="bold" if bold else "normal",
                linespacing=1.45, zorder=zorder + 1)
    return patch


def sharp_box(ax, x, y, w, h, text, fill="white", edge=INK, fontsize=9,
              bold=False, dashed=False, lw=1.4, zorder=3):
    """A square-cornered rectangle -- used for DFD external entities, which
    by Gane-Sarson convention are never rounded."""
    patch = Rectangle((x - w / 2, y - h / 2), w, h, linewidth=lw,
                      edgecolor=edge, facecolor=fill,
                      linestyle=(0, (4, 2.5)) if dashed else "solid",
                      zorder=zorder)
    ax.add_patch(patch)
    if text:
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                family=FONT, color=INK, fontweight="bold" if bold else "normal",
                linespacing=1.45, zorder=zorder + 1)
    return patch


def group_frame(ax, x, y, w, h, label=None, edge=GRID, label_color=MUTED,
                fontsize=8.5, dashed=True, lw=1.2, fill="none", label_dx=0):
    """A light background frame used to group related boxes into a layer or a
    system boundary. Drawn behind everything else."""
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0,rounding_size=1.2",
        linewidth=lw, edgecolor=edge, facecolor=fill,
        linestyle=(0, (5, 3)) if dashed else "solid", zorder=1,
    )
    ax.add_patch(patch)
    if label:
        ax.text(x - w / 2 + 1.4 + label_dx, y + h / 2 - 1.9, label,
                ha="left", va="center", fontsize=fontsize, family=FONT,
                color=label_color, fontweight="bold", zorder=2)
    return patch


def note(ax, x, y, w, h, text, fontsize=8, edge=MUTED, fill="#FBFCFD"):
    """A UML-style note box (folded corner), used for the CPU/GPU caveat."""
    fold = min(2.2, h * 0.42)
    pts = [
        (x - w / 2, y - h / 2), (x + w / 2, y - h / 2),
        (x + w / 2, y + h / 2 - fold), (x + w / 2 - fold, y + h / 2),
        (x - w / 2, y + h / 2), (x - w / 2, y - h / 2),
    ]
    ax.add_patch(PathPatch(Path(pts, [Path.MOVETO] + [Path.LINETO] * 5),
                           facecolor=fill, edgecolor=edge, linewidth=1.1,
                           zorder=3))
    ax.plot([x + w / 2 - fold, x + w / 2 - fold, x + w / 2],
            [y + h / 2, y + h / 2 - fold, y + h / 2 - fold],
            color=edge, linewidth=1.1, zorder=4)
    ax.text(x, y - fold * 0.18, text, ha="center", va="center",
            fontsize=fontsize, family=FONT, color=INK, linespacing=1.5,
            zorder=4)


def mini_datastore(ax, x, y, w, h):
    """A tiny open-ended store shape, for figure legends."""
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=DATA_FILL,
                           edgecolor="none", zorder=4))
    ax.plot([x - w / 2, x + w / 2], [y + h / 2, y + h / 2], color=DATA_EDGE,
            lw=1.2, zorder=5)
    ax.plot([x - w / 2, x + w / 2], [y - h / 2, y - h / 2], color=DATA_EDGE,
            lw=1.2, zorder=5)
    ax.plot([x - w / 2, x - w / 2], [y - h / 2, y + h / 2], color=DATA_EDGE,
            lw=1.2, zorder=5)


def datastore(ax, x, y, w, h, ident, text, fontsize=8.6):
    """Gane-Sarson open-ended data store: a rectangle open on the right, with
    the store's identifier in a small left compartment."""
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=DATA_FILL,
                           edgecolor="none", zorder=3))
    ax.plot([x - w / 2, x + w / 2], [y + h / 2, y + h / 2],
            color=DATA_EDGE, lw=1.4, zorder=4)
    ax.plot([x - w / 2, x + w / 2], [y - h / 2, y - h / 2],
            color=DATA_EDGE, lw=1.4, zorder=4)
    ax.plot([x - w / 2, x - w / 2], [y - h / 2, y + h / 2],
            color=DATA_EDGE, lw=1.4, zorder=4)
    div = x - w / 2 + 5.0
    ax.plot([div, div], [y - h / 2, y + h / 2], color=DATA_EDGE, lw=1.4,
            zorder=4)
    ax.text(x - w / 2 + 2.5, y, ident, ha="center", va="center",
            fontsize=fontsize, family=FONT, color=INK, fontweight="bold",
            zorder=5)
    ax.text(div + (x + w / 2 - div) / 2, y, text, ha="center", va="center",
            fontsize=fontsize, family=FONT, color=INK, linespacing=1.4,
            zorder=5)


def process(ax, x, y, w, h, number, text, fill=LOGIC_FILL, edge=LOGIC_EDGE,
            fontsize=8.8):
    """Gane-Sarson process: a rounded box split into a numbered top strip and
    a description below it."""
    box(ax, x, y, w, h, "", fill=fill, edge=edge, lw=1.5, radius=1.0)
    top = y + h / 2 - 3.2
    ax.plot([x - w / 2 + 0.15, x + w / 2 - 0.15], [top, top], color=edge,
            lw=1.2, zorder=4)
    ax.text(x, y + h / 2 - 1.6, number, ha="center", va="center",
            fontsize=fontsize, family=FONT, color=INK, fontweight="bold",
            zorder=5)
    ax.text(x, y - 1.5, text, ha="center", va="center", fontsize=fontsize,
            family=FONT, color=INK, linespacing=1.45, zorder=5)


def actor(ax, x, y, label, scale=1.0, color=INPUT_EDGE):
    """UML stick-figure actor."""
    s = scale
    ax.add_patch(Circle((x, y + 4.2 * s), 1.75 * s, facecolor=INPUT_FILL,
                        edgecolor=color, linewidth=1.6, zorder=4))
    ax.plot([x, x], [y + 2.4 * s, y - 2.0 * s], color=color, lw=1.6, zorder=4)
    ax.plot([x - 2.6 * s, x + 2.6 * s], [y + 1.0 * s, y + 1.0 * s],
            color=color, lw=1.6, zorder=4)
    ax.plot([x, x - 2.1 * s], [y - 2.0 * s, y - 5.6 * s], color=color, lw=1.6,
            zorder=4)
    ax.plot([x, x + 2.1 * s], [y - 2.0 * s, y - 5.6 * s], color=color, lw=1.6,
            zorder=4)
    ax.text(x, y - 7.8 * s, label, ha="center", va="top", fontsize=9.5,
            family=FONT, color=INK, fontweight="bold", zorder=4)


def usecase(ax, x, y, w, h, text, fontsize=8.8):
    ax.add_patch(Ellipse((x, y), w, h, facecolor=LOGIC_FILL,
                         edgecolor=LOGIC_EDGE, linewidth=1.4, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
            family=FONT, color=INK, linespacing=1.4, zorder=4)


# --------------------------------------------------------------------------
# Connectors
# --------------------------------------------------------------------------
def arrow(ax, start, end, label=None, style="-|>", dashed=False, color=LINE,
          lw=1.4, rad=0.0, label_pos=0.5, label_dx=0.0, label_dy=1.4,
          fontsize=8, label_ha="center", hollow=False, zorder=5,
          label_bg=True):
    """A connector between two points. `hollow` draws the open triangle head
    UML uses for generalization/realization."""
    # `color=` would override facecolor, which is exactly what an open
    # (generalization / realization) arrowhead needs to keep -- so set the
    # edge and face separately instead.
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle=style, mutation_scale=13,
        linewidth=lw, edgecolor=color,
        facecolor="white" if hollow else color,
        linestyle=(0, (4.5, 3)) if dashed else "solid",
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=0, shrinkB=0, zorder=zorder,
        joinstyle="miter",
    ))
    if label:
        lx = start[0] + (end[0] - start[0]) * label_pos + label_dx
        ly = start[1] + (end[1] - start[1]) * label_pos + label_dy
        ax.text(lx, ly, label, ha=label_ha, va="center", fontsize=fontsize,
                family=FONT, color=INK, linespacing=1.35, zorder=zorder + 1,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                          edgecolor="none", alpha=0.92) if label_bg else None)


def elbow(ax, points, label=None, style="-|>", dashed=False, color=LINE,
          lw=1.4, label_at=0, label_dx=0.0, label_dy=1.4, fontsize=8,
          label_ha="center", zorder=5):
    """An orthogonal (right-angle) connector through a list of waypoints --
    used wherever a straight line would cross another box."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs[:-1] + [xs[-1]], ys[:-1] + [ys[-1]], color=color, lw=lw,
            linestyle=(0, (4.5, 3)) if dashed else "solid",
            solid_capstyle="butt", zorder=zorder)
    ax.add_patch(FancyArrowPatch(points[-2], points[-1], arrowstyle=style,
                                 mutation_scale=13, linewidth=lw, color=color,
                                 linestyle="solid", shrinkA=0, shrinkB=0,
                                 zorder=zorder))
    if label:
        ax.text((xs[label_at] + xs[label_at + 1]) / 2 + label_dx,
                (ys[label_at] + ys[label_at + 1]) / 2 + label_dy, label,
                ha=label_ha, va="center", fontsize=fontsize, family=FONT,
                color=INK, linespacing=1.35, zorder=zorder + 1,
                bbox=dict(boxstyle="round,pad=0.22", facecolor="white",
                          edgecolor="none", alpha=0.92))


def diamond(ax, x, y, size=1.5, filled=True, color=LINE, angle=0.0):
    """UML aggregation (hollow) / composition (filled) diamond."""
    import math
    a = math.radians(angle)
    pts = []
    for dx, dy in [(0, size), (size * 0.62, 0), (0, -size), (-size * 0.62, 0)]:
        rx = dx * math.cos(a) - dy * math.sin(a)
        ry = dx * math.sin(a) + dy * math.cos(a)
        pts.append((x + rx, y + ry))
    ax.add_patch(PathPatch(
        Path(pts + [pts[0]], [Path.MOVETO] + [Path.LINETO] * 4),
        facecolor=color if filled else "white", edgecolor=color,
        linewidth=1.3, zorder=6))


def uml_class(ax, x, y, w, name, attrs, ops, stereotype=None, dashed=False,
              fill="white", edge=INK, header_fill="#EEF2F6",
              name_italic=False, fontsize=8.2, line_h=2.35, pad=1.3,
              tag=None, tag_color=None):
    """
    A proper three-compartment UML class box:
        +----------------------+
        |   <<stereotype>>     |
        |      ClassName       |
        +----------------------+
        |  - attribute : type  |
        +----------------------+
        |  + operation() : T   |
        +----------------------+
    Returns (top_y, bottom_y) so callers can attach relationships.
    Text is measured in the same 0-100 units the figure uses, so the box
    grows to fit whatever it is given.
    """
    head_lines = (1 if stereotype else 0) + 1
    head_h = pad * 2 + head_lines * line_h
    attr_h = pad * 2 + max(len(attrs), 1) * line_h
    ops_h = pad * 2 + max(len(ops), 1) * line_h
    h = head_h + attr_h + ops_h

    top = y + h / 2
    ls = (0, (4, 2.5)) if dashed else "solid"

    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=fill,
                           edgecolor=edge, linewidth=1.5, linestyle=ls,
                           zorder=3))
    ax.add_patch(Rectangle((x - w / 2, top - head_h), w, head_h,
                           facecolor=header_fill, edgecolor="none", zorder=2))
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor="none",
                           edgecolor=edge, linewidth=1.5, linestyle=ls,
                           zorder=4))

    for yy in (top - head_h, top - head_h - attr_h):
        ax.plot([x - w / 2, x + w / 2], [yy, yy], color=edge, lw=1.2,
                linestyle=ls, zorder=5)

    cy = top - pad - line_h / 2
    if stereotype:
        ax.text(x, cy, stereotype, ha="center", va="center", family=FONT,
                fontsize=fontsize - 0.4, color=MUTED, style="italic", zorder=6)
        cy -= line_h
    ax.text(x, cy, name, ha="center", va="center", family=FONT,
            fontsize=fontsize + 0.7, color=INK, fontweight="bold",
            style="italic" if name_italic else "normal", zorder=6)

    cy = top - head_h - pad - line_h / 2
    for a in attrs:
        ax.text(x - w / 2 + 1.3, cy, a, ha="left", va="center", family=FONT,
                fontsize=fontsize, color=INK, zorder=6)
        cy -= line_h

    cy = top - head_h - attr_h - pad - line_h / 2
    for o in ops:
        ax.text(x - w / 2 + 1.3, cy, o, ha="left", va="center", family=FONT,
                fontsize=fontsize, color=INK, zorder=6)
        cy -= line_h

    if tag:
        ax.text(x, top + 1.6, tag, ha="center", va="center", family=FONT,
                fontsize=fontsize - 0.2, color=tag_color or MUTED,
                fontweight="bold", zorder=6)

    return top, y - h / 2, h


def lifeline(ax, x, top, bottom, label, sub=None, w=13.5, head_h=5.4,
             fill=LOGIC_FILL, edge=LOGIC_EDGE, fontsize=8.6):
    """A UML sequence-diagram participant: a head box plus a dashed lifeline."""
    box(ax, x, top - head_h / 2, w, head_h, "", fill=fill, edge=edge, lw=1.4,
        radius=0.7)
    if sub:
        ax.text(x, top - head_h / 2 + 1.1, label, ha="center", va="center",
                family=FONT, fontsize=fontsize, color=INK, fontweight="bold",
                zorder=6)
        ax.text(x, top - head_h / 2 - 1.4, sub, ha="center", va="center",
                family=FONT, fontsize=fontsize - 1.2, color=MUTED, zorder=6)
    else:
        ax.text(x, top - head_h / 2, label, ha="center", va="center",
                family=FONT, fontsize=fontsize, color=INK, fontweight="bold",
                zorder=6)
    ax.plot([x, x], [top - head_h, bottom], color=MUTED, lw=1.1,
            linestyle=(0, (3, 3)), zorder=2)


def activation(ax, x, y_top, y_bottom, w=1.5, fill="#DDE6EF", edge=LOGIC_EDGE):
    """A UML execution-occurrence (activation) bar on a lifeline."""
    ax.add_patch(Rectangle((x - w / 2, y_bottom), w, y_top - y_bottom,
                           facecolor=fill, edgecolor=edge, linewidth=1.0,
                           zorder=4))


def message(ax, x1, x2, y, text, dashed=False, fontsize=8.2, dy=1.25,
            color=LINE, ha=None):
    """A synchronous call (solid, filled head) or a reply (dashed, open head)."""
    ax.add_patch(FancyArrowPatch(
        (x1, y), (x2, y), arrowstyle="-|>" if not dashed else "->",
        mutation_scale=12, linewidth=1.3, color=color,
        linestyle=(0, (4, 2.5)) if dashed else "solid", shrinkA=0, shrinkB=0,
        zorder=6))
    ax.text((x1 + x2) / 2, y + dy, text, ha=ha or "center", va="bottom",
            family=FONT, fontsize=fontsize, color=INK, zorder=7,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                      edgecolor="none", alpha=0.93))


def self_message(ax, x, y, text, w=6.0, h=3.0, fontsize=8.2,
                 text_side="right"):
    """A message a participant sends to itself, drawn as the standard UML
    right-angle loop back onto the same lifeline. `text_side` puts the label
    on whichever side has room -- the rightmost lifeline needs it on the
    left, or the label runs off the canvas."""
    ax.plot([x, x + w, x + w, x + 0.8], [y, y, y - h, y - h], color=LINE,
            lw=1.3, zorder=6, solid_capstyle="butt")
    ax.add_patch(FancyArrowPatch((x + 2.0, y - h), (x + 0.8, y - h),
                                 arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.3, color=LINE, shrinkA=0,
                                 shrinkB=0, zorder=6))
    if text_side == "right":
        ax.text(x + w + 1.2, y - h / 2, text, ha="left", va="center",
                family=FONT, fontsize=fontsize, color=INK, linespacing=1.4,
                zorder=7)
    else:
        ax.text(x - 1.8, y - h / 2, text, ha="right", va="center",
                family=FONT, fontsize=fontsize, color=INK, linespacing=1.4,
                zorder=7,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                          edgecolor="none", alpha=0.93))


def fragment(ax, x, y, w, h, kind, guard, fontsize=8.0, edge=MUTED):
    """A UML combined fragment (loop / alt / opt) -- the labelled rectangle
    with the pentagon operator tag in its top-left corner."""
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor="none",
                           edgecolor=edge, linewidth=1.1, zorder=3))
    tw, th = 7.2, 3.2
    tx, ty = x - w / 2, y + h / 2
    pts = [(tx, ty), (tx + tw, ty), (tx + tw, ty - th * 0.5),
           (tx + tw - 1.5, ty - th), (tx, ty - th)]
    ax.add_patch(PathPatch(Path(pts + [pts[0]],
                                [Path.MOVETO] + [Path.LINETO] * 5),
                           facecolor="white", edgecolor=edge, linewidth=1.1,
                           zorder=4))
    ax.text(tx + tw / 2 - 0.6, ty - th / 2, kind, ha="center", va="center",
            family=FONT, fontsize=fontsize, color=INK, fontweight="bold",
            zorder=5)
    ax.text(tx + tw + 1.4, ty - th / 2, guard, ha="left", va="center",
            family=FONT, fontsize=fontsize, color=MUTED, zorder=5)


def title(ax, text, subtitle=None, y=99.0):
    """Figure titles are intentionally NOT drawn inside the image -- the Word
    document supplies the numbered caption. This helper exists only for
    standalone previews and is unused by the report figures."""
    ax.text(50, y, text, ha="center", va="top", family=FONT, fontsize=12,
            fontweight="bold", color=INK)
    if subtitle:
        ax.text(50, y - 4, subtitle, ha="center", va="top", family=FONT,
                fontsize=9, color=MUTED)


def legend(ax, x, y, entries, fontsize=7.8, dy=3.4, swatch_w=3.6,
           swatch_h=2.0):
    """A small key. `entries` is a list of (fill, edge, dashed, label)."""
    for i, (fill, edge, dashed, label) in enumerate(entries):
        yy = y - i * dy
        ax.add_patch(FancyBboxPatch(
            (x, yy - swatch_h / 2), swatch_w, swatch_h,
            boxstyle="round,pad=0,rounding_size=0.5", linewidth=1.2,
            edgecolor=edge, facecolor=fill,
            linestyle=(0, (3, 2)) if dashed else "solid", zorder=5))
        ax.text(x + swatch_w + 1.4, yy, label, ha="left", va="center",
                family=FONT, fontsize=fontsize, color=INK, zorder=5)
