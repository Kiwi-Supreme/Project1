// integrator.h
//
// Advances the simulation by one timestep. This uses the velocity-Verlet
// method, the standard way to integrate Newton's equations of motion in
// molecular dynamics: it updates velocity using the force at the start
// of the step, moves the particles, then updates velocity again using
// the force at the new positions. It's a direct, more explicit version
// of the position-only Verlet method used in the original 2024 code --
// keeping velocity as its own value (instead of recovering it from two
// positions) makes wall bounces and gravity straightforward to add.

#ifndef INTEGRATOR_H
#define INTEGRATOR_H

#include <vector>
#include "particle.h"

// First half of a velocity-Verlet step: nudge every velocity by half a
// timestep's worth of the current force, then move the particle.
// Call this, then apply boundary conditions, then recompute forces,
// then call finish_step() below.
void begin_step(std::vector<Particle>& particles, double dt);

// Second half of a velocity-Verlet step: finish updating velocity using
// the newly recomputed force.
void finish_step(std::vector<Particle>& particles, double dt);

// Scales every velocity by `factor` (slightly less than 1). A real
// liquid settles at the bottom of its container because collisions
// lose a little energy each time; our wall bounces and particle
// collisions are perfectly elastic (no loss), so without this the
// particles would bounce forever at the same height instead of
// settling. A tiny, constant damping stands in for that lost energy.
void apply_damping(std::vector<Particle>& particles, double factor);

#endif
