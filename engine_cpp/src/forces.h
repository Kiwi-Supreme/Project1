// forces.h
//
// The actual physics of how particles push and pull on each other.
// Two interaction models are supported:
//
//   - Lennard-Jones: a smooth potential (particles attract at medium
//     range, repel at short range). Used for the "Lennard-Jones" model.
//   - Hard-Sphere: particles have no force between them at all -- they
//     travel in straight lines and only interact through direct,
//     instantaneous collisions. Used for the "Hard-Sphere" model.

#ifndef FORCES_H
#define FORCES_H

#include <vector>
#include "particle.h"
#include "config.h"

// Computes the Lennard-Jones force on every particle from every other
// particle within the cutoff distance, and returns the total potential
// energy of the system. If `periodic` is true, distances are measured
// using the minimum-image convention (the periodic-boundary trick from
// the original 2024 implementation); otherwise plain straight-line
// distance is used, which is correct once particles are held inside a
// real container instead of wrapping.
double compute_lj_forces(std::vector<Particle>& particles,
                          const SimConfig& cfg,
                          double box_length,
                          bool periodic);

// Adds a small constant downward force to every particle, representing
// gravity. This is what makes a "liquid" (and a "solid") settle toward
// the bottom of a container instead of floating in the middle -- a gas
// gets no gravity, so it stays spread through the whole volume.
void apply_gravity(std::vector<Particle>& particles, double gravity_strength);

// Checks every pair of particles for a hard-sphere collision (their
// centers closer together than the sum of their radii) and resolves it
// with a perfectly elastic bounce: for equal-mass particles, the
// component of velocity along the line connecting their centers is
// swapped between the two particles. Also nudges overlapping particles
// apart so they don't stick together.
void resolve_hard_sphere_collisions(std::vector<Particle>& particles, double particle_radius);

#endif
