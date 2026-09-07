// boundary.h
//
// Everything to do with the edges of the simulation: wrapping particles
// around (periodic boundary) or bouncing them off real walls (a cuboid or
// spherical container). These functions only ever touch position and
// velocity -- they don't know about forces or energy.

#ifndef BOUNDARY_H
#define BOUNDARY_H

#include <vector>
#include "particle.h"

// Periodic boundary: a particle that leaves one side of the box
// reappears on the opposite side. This is what "container off" means --
// there is no visible wall, the box just tiles infinitely.
void apply_periodic_boundary(std::vector<Particle>& particles, double box_length);

// Reflective cuboid container: a real box from (0,0,0) to (L,L,L).
// A particle that reaches a wall bounces back elastically (its velocity
// component perpendicular to that wall flips sign).
void apply_reflective_cuboid(std::vector<Particle>& particles, double box_length);

// Reflective spherical container: a real sphere of radius R centered at
// (R,R,R). A particle that reaches the sphere's surface bounces back by
// reflecting its velocity across the surface normal at that point.
void apply_reflective_sphere(std::vector<Particle>& particles, double radius);

#endif
