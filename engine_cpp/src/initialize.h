// initialize.h
//
// Builds the starting arrangement of particles. This is where "solid",
// "liquid", and "gas" actually become different simulations rather than
// different labels -- each one gets a different starting layout and a
// different starting speed, which is what the physics then acts on.

#ifndef INITIALIZE_H
#define INITIALIZE_H

#include <vector>
#include "particle.h"
#include "config.h"

// Works out the size of the simulation space in simulation units:
// - if a container is enabled, this is just its configured size.
// - if not (periodic mode), the box is sized from particle count and
//   density, exactly like the original 2024 code did.
double compute_box_length(const SimConfig& cfg);

// Creates the initial particle positions and velocities for the given
// state of matter, container shape, and box size. This is the single
// entry point main.cpp calls; it dispatches to init_solid / init_liquid
// / init_gas below based on cfg.state.
std::vector<Particle> initialize_particles(const SimConfig& cfg, double box_length);

#endif
