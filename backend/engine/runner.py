"""
engine/runner.py

The bridge between the web backend and the compiled C++ simulation.
For one simulation request, this module:
  1. writes the validated parameters to a small config file the engine
     can read,
  2. runs the compiled engine as a subprocess and waits for it to finish,
  3. reads back the two files it produced (trajectory.json, energy.csv)
     and hands them to the caller as plain Python data.

This is the ONLY place that talks to the C++ program. Nothing else in
the backend knows or cares that the simulation is a separate executable.
"""

import csv
import json
import os
import subprocess
import time
import uuid

from backend.validation.schema import SimParams

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine_cpp")
RUNS_DIR = os.path.join(PROJECT_ROOT, "runs")

# On Windows the compiled binary has a .exe suffix; on Linux/macOS it doesn't.
_ENGINE_CANDIDATES = ["md_engine.exe", "md_engine"]


class EngineRunError(Exception):
    """Raised when the C++ engine can't be found, times out, or exits with an error."""
    pass


def _find_engine_binary() -> str:
    for name in _ENGINE_CANDIDATES:
        path = os.path.join(ENGINE_DIR, name)
        if os.path.isfile(path):
            return path
    raise EngineRunError(
        "Simulation engine not found. Build it first: "
        "run engine_cpp/build.sh (or compile engine_cpp/src/*.cpp with g++)."
    )


def _write_config_file(params: SimParams, output_dir: str, config_path: str):
    """Writes the simple 'key=value' text file the C++ engine reads.
    This mirrors SimConfig::load_config() in engine_cpp/src/config.cpp --
    the key names here must match the ones that file expects."""
    lines = [
        f"model={params.model}",
        f"state={params.state}",
        f"container_enabled={'true' if params.container_enabled else 'false'}",
        f"container_shape={params.container_shape}",
        f"particle_count={params.particle_count}",
        f"container_size={params.container_size}",
        f"density={params.density}",
        f"temperature={params.temperature}",
        f"particle_speed={params.particle_speed}",
        f"timestep={params.timestep}",
        f"total_time={params.total_time}",
        f"epsilon={params.epsilon}",
        f"sigma={params.sigma}",
        f"cutoff={params.cutoff}",
        f"seed={params.seed}",
        f"output_dir={output_dir}",
    ]
    with open(config_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _read_energy_csv(path: str):
    """Turns energy.csv into a list of {step, time, potential, kinetic, total} dicts."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "step": int(row["step"]),
                "time": float(row["time"]),
                "potential": float(row["potential"]),
                "kinetic": float(row["kinetic"]),
                "total": float(row["total"]),
            })
    return rows


def run_simulation(params: SimParams, timeout_seconds: int = 60) -> dict:
    """
    Runs one simulation end to end and returns:
        {
          "trajectory": <parsed trajectory.json, including "frames">,
          "energy": [ {step, time, potential, kinetic, total}, ... ],
          "run_seconds": <how long the engine actually took>
        }
    Raises EngineRunError if the engine can't run or fails.
    """
    engine_path = _find_engine_binary()

    # Each request gets its own folder so simultaneous runs never collide.
    run_id = uuid.uuid4().hex[:12]
    output_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(output_dir, exist_ok=True)
    config_path = os.path.join(output_dir, "config.txt")

    _write_config_file(params, output_dir, config_path)

    start = time.time()
    try:
        result = subprocess.run(
            [engine_path, config_path],
            cwd=ENGINE_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        raise EngineRunError(f"Simulation timed out after {timeout_seconds}s -- try fewer particles or a shorter run.")
    run_seconds = time.time() - start

    if result.returncode != 0:
        raise EngineRunError(f"Simulation engine failed: {result.stderr.strip() or result.stdout.strip()}")

    trajectory_path = os.path.join(output_dir, "trajectory.json")
    energy_path = os.path.join(output_dir, "energy.csv")

    if not os.path.isfile(trajectory_path) or not os.path.isfile(energy_path):
        raise EngineRunError("Simulation engine finished but did not produce the expected output files.")

    with open(trajectory_path) as f:
        trajectory = json.load(f)
    energy = _read_energy_csv(energy_path)

    return {
        "trajectory": trajectory,
        "energy": energy,
        "run_seconds": round(run_seconds, 2),
    }
