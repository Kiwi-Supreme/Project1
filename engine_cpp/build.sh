#!/bin/bash
# Compiles the C++ molecular dynamics engine into a single executable
# called md_engine (md_engine.exe on Windows).
#
# -O2         : optimize for speed -- the force loop is O(particles^2)
#               per step, so this matters even for a small demo.
# -std=c++11  : the language standard the code is written against.
set -e
cd "$(dirname "$0")"

SOURCES="src/main.cpp src/config.cpp src/initialize.cpp src/forces.cpp src/boundary.cpp src/integrator.cpp src/trajectory_writer.cpp"

g++ -O2 -std=c++11 -Wall $SOURCES -o md_engine

echo "Built ./md_engine"
