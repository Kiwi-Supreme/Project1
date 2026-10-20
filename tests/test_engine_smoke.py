"""
A smoke test for the compiled C++ engine: runs a small simulation end to
end and checks the output makes physical sense. This test is SKIPPED if
the engine hasn't been built yet (see engine_cpp/build.sh) rather than
failing, since building it is a separate manual step.

Every run here pins the engine's random seed. The starting arrangement is
randomised (jittered lattice positions, random velocity directions), so
without a fixed seed a test that checks "did the liquid settle far enough"
passes or fails depending on the draw -- which it did, intermittently,
before the seed was added.
"""

import json
import os
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine_cpp")
ENGINE_PATH = os.path.join(ENGINE_DIR, "md_engine.exe" if os.name == "nt" else "md_engine")

SEED = 20240525  # any fixed value; makes every run below repeatable

pytestmark = pytest.mark.skipif(not os.path.isfile(ENGINE_PATH), reason="engine not built yet -- run engine_cpp/build.sh")


def _run(tmp_path, config_text):
    output_dir = str(tmp_path)
    os.makedirs(output_dir, exist_ok=True)  # tests that need two runs pass sub-paths
    config_path = os.path.join(output_dir, "config.txt")
    with open(config_path, "w") as f:
        f.write(config_text + f"\nseed={SEED}\noutput_dir={output_dir}\n")

    result = subprocess.run([ENGINE_PATH, config_path], cwd=ENGINE_DIR, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr

    with open(os.path.join(output_dir, "trajectory.json")) as f:
        trajectory = json.load(f)
    with open(os.path.join(output_dir, "energy.csv")) as f:
        energy_lines = f.read().strip().splitlines()[1:]  # skip header
    return trajectory, energy_lines


def test_particle_count_matches_request(tmp_path):
    trajectory, _ = _run(tmp_path, "model=lennard_jones\nstate=gas\ncontainer_enabled=false\nparticle_count=64\ndensity=0.3\ntemperature=1.0\ntimestep=0.001\ntotal_time=0.5")
    assert len(trajectory["frames"][0]) == 64


def test_periodic_nve_run_conserves_energy(tmp_path):
    # No container, no gravity -> this should be a clean NVE run where
    # total energy barely drifts. This is the real correctness check.
    _, energy_lines = _run(tmp_path, "model=lennard_jones\nstate=liquid\ncontainer_enabled=false\nparticle_count=100\ndensity=0.8\ntemperature=1.0\ntimestep=0.001\ntotal_time=1.0")
    totals = [float(line.split(",")[4]) for line in energy_lines]
    drift = max(totals) - min(totals)
    assert drift < 0.5, f"total energy drifted by {drift}, expected a tightly conserved NVE run"


def test_hard_sphere_kinetic_energy_conserved(tmp_path):
    # Hard-Sphere has no potential energy, so total energy IS kinetic
    # energy -- elastic collisions should keep it essentially constant.
    _, energy_lines = _run(tmp_path, "model=hard_sphere\nstate=gas\ncontainer_enabled=true\ncontainer_shape=cuboid\nparticle_count=60\ncontainer_size=10.0\nparticle_speed=1.5\ntimestep=0.001\ntotal_time=0.5")
    totals = [float(line.split(",")[4]) for line in energy_lines]
    drift = max(totals) - min(totals)
    assert drift < 0.05, f"hard-sphere total kinetic energy drifted by {drift}, expected near-perfect conservation"


def test_particles_stay_inside_the_container_and_nothing_pulls_them_down(tmp_path):
    """Reflective walls confine every particle for the whole run. There is no gravity and no
    friction in the engine any more (they were non-physical stand-ins), so a liquid does not
    'settle': its mean height stays near the middle of the box."""
    trajectory, _ = _run(tmp_path, "model=lennard_jones\nstate=liquid\ncontainer_enabled=true\ncontainer_shape=cuboid\nparticle_count=150\ncontainer_size=10.0\ndensity=0.8\ntemperature=1.0\ntimestep=0.001\ntotal_time=2.0")
    box_length = trajectory["box_length"]
    for frame in trajectory["frames"]:
        for p in frame:
            assert all(-1e-9 <= c <= box_length + 1e-9 for c in p[:3]), "a particle escaped the container"
    heights = [p[1] for p in trajectory["frames"][-1]]
    assert 0.2 * box_length < sum(heights) / len(heights) < 0.8 * box_length, "no external field: mean height should not drift to the floor"


# The remaining tests build their config from a dict rather than one long
# escaped string -- easier to read, and the key names line up with
# engine_cpp/src/config.cpp.
def _cfg(**settings):
    return "\n".join("{}={}".format(key, value) for key, value in settings.items())


def test_same_seed_gives_an_identical_run(tmp_path):
    """Two runs of the same config must match exactly -- this is what lets
    every other test in this file assert anything about the result."""
    config = _cfg(model="lennard_jones", state="gas", container_enabled="false",
                  particle_count=40, density=0.4, temperature=1.0,
                  timestep=0.001, total_time=0.3)
    first, _ = _run(tmp_path / "a", config)
    second, _ = _run(tmp_path / "b", config)
    assert first["frames"] == second["frames"]


def test_frames_carry_position_and_speed(tmp_path):
    """Each particle is written as [x, y, z, speed]; the viewer colours by
    that fourth number, so it has to be present and physically sensible."""
    trajectory, _ = _run(tmp_path, _cfg(
        model="lennard_jones", state="gas", container_enabled="true",
        container_shape="cuboid", particle_count=50, container_size=10.0,
        density=0.3, temperature=1.0, timestep=0.001, total_time=0.3))

    assert trajectory["sigma"] > 0
    for particle in trajectory["frames"][0]:
        assert len(particle) == 4
        assert particle[3] >= 0.0

    # At temperature 1.0 the average speed should land near sqrt(3T) = 1.73.
    speeds = [p[3] for p in trajectory["frames"][0]]
    mean_speed = sum(speeds) / len(speeds)
    assert 0.8 < mean_speed < 3.0, "mean starting speed {} is not near the requested temperature".format(mean_speed)


def test_solid_keeps_its_shape(tmp_path):
    """A cold Lennard-Jones solid should vibrate in place, not expand or
    melt. Its bounding box at the end of the run should be close to the one
    it started with -- the check the solid state never had."""
    trajectory, _ = _run(tmp_path, _cfg(
        model="lennard_jones", state="solid", container_enabled="true",
        container_shape="cuboid", particle_count=125, container_size=12.0,
        density=1.0, temperature=0.2, timestep=0.001, total_time=2.0))

    def extent(frame):
        return [max(p[axis] for p in frame) - min(p[axis] for p in frame) for axis in (0, 1, 2)]

    start = extent(trajectory["frames"][0])
    end = extent(trajectory["frames"][-1])
    for axis in range(3):
        assert end[axis] < start[axis] * 1.6, (
            "the solid grew from {:.2f} to {:.2f} along axis {} -- it is not holding together"
            .format(start[axis], end[axis], axis))


def test_gas_fills_the_whole_container(tmp_path):
    """A gas should use the entire box, not sit in one corner -- the
    difference from the liquid case above is real, not cosmetic."""
    trajectory, _ = _run(tmp_path, _cfg(
        model="lennard_jones", state="gas", container_enabled="true",
        container_shape="cuboid", particle_count=150, container_size=10.0,
        density=0.2, temperature=2.5, timestep=0.001, total_time=2.0))

    last_frame = trajectory["frames"][-1]
    box_length = trajectory["box_length"]
    ys = [p[1] for p in last_frame]
    assert max(ys) > box_length * 0.8, "a gas should reach the top of the container"
    assert min(ys) < box_length * 0.2, "a gas should reach the bottom of the container"
