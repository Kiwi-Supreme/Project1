// integrator.cpp
//
// See integrator.h for the overview. Mass is treated as 1 for every
// particle (standard in reduced-unit molecular dynamics), so force and
// acceleration are numerically the same thing here.

#include "integrator.h"
#include <cstddef>
using std::size_t;

void begin_step(std::vector<Particle>& particles, double dt) {
    for (size_t i = 0; i < particles.size(); i++) {
        Particle& p = particles[i];

        // Half-step velocity update using the force from the previous step.
        p.vx += 0.5 * dt * p.fx;
        p.vy += 0.5 * dt * p.fy;
        p.vz += 0.5 * dt * p.fz;

        // Move the particle using its (now half-updated) velocity.
        p.x += dt * p.vx;
        p.y += dt * p.vy;
        p.z += dt * p.vz;
    }
}

void finish_step(std::vector<Particle>& particles, double dt) {
    for (size_t i = 0; i < particles.size(); i++) {
        Particle& p = particles[i];

        // Second half-step, using the force recomputed at the new position.
        p.vx += 0.5 * dt * p.fx;
        p.vy += 0.5 * dt * p.fy;
        p.vz += 0.5 * dt * p.fz;
    }
}

void apply_damping(std::vector<Particle>& particles, double factor) {
    for (size_t i = 0; i < particles.size(); i++) {
        particles[i].vx *= factor;
        particles[i].vy *= factor;
        particles[i].vz *= factor;
    }
}
