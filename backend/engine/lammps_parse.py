"""
engine/lammps_parse.py -- reads what LAMMPS wrote: the thermodynamic log, the
trajectory dump, and (for reactive runs) the species table.
"""

import numpy as np


def parse_thermo_blocks(text):
    """Every thermo block in a LAMMPS log, as a list of lists of row dicts."""
    blocks, cols, cur = [], None, None
    for line in text.splitlines():
        s = line.split()
        if s and s[0] == "Step" and "Temp" in s:
            cols, cur = s, []
            continue
        if cols is not None:
            if line.startswith("Loop time"):
                blocks.append((cols, cur))
                cols, cur = None, None
                continue
            try:
                vals = [float(x) for x in s]
            except ValueError:
                continue
            if len(vals) == len(cols):
                cur.append(vals)
    return [[dict(zip(cols, r)) for r in rows] for cols, rows in blocks]


def parse_thermo(text):
    """Rows of the LAST thermo block in a LAMMPS log (the production run)."""
    blocks = parse_thermo_blocks(text)
    return blocks[-1] if blocks else []


def parse_dump(path):
    """Returns (steps, data) with data shape (frames, atoms, 13) and columns
    id type x y z xu yu zu vx vy vz fx fy fz."""
    steps, frames = [], []
    with open(path) as f:
        lines = f.read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("ITEM: TIMESTEP"):
            steps.append(int(lines[i + 1]))
            n = int(lines[i + 3])
            block = lines[i + 9:i + 9 + n]
            frames.append(np.array([l.split() for l in block], dtype=float))
            i += 9 + n
        else:
            i += 1
    return steps, np.array(frames)


def parse_species(path):
    """Reactive runs: [(step, {formula: count})]."""
    out, header = [], None
    try:
        with open(path) as f:
            for line in f:
                s = line.split()
                if line.startswith("#"):
                    header = s[1:]
                elif s and header:
                    d = dict(zip(header, s))
                    step = int(d.pop("Timestep"))
                    d.pop("No_Moles", None)
                    d.pop("No_Specs", None)
                    out.append((step, {k: int(v) for k, v in d.items()}))
    except OSError:
        pass
    return out
