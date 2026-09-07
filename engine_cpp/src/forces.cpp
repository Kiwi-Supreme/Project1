// forces.cpp
//
// See forces.h for what each function is for.

#include "forces.h"
#include <cmath>

double compute_lj_forces(std::vector<Particle>& particles,
                          const SimConfig& cfg,
                          double box_length,
                          bool periodic) {
    size_t n = particles.size();

    // Forces start fresh every step -- whatever accumulates below (and
    // whatever apply_gravity() adds afterwards) is the total force used
    // by the integrator this step.
    for (size_t i = 0; i < n; i++) {
        particles[i].fx = particles[i].fy = particles[i].fz = 0.0;
    }

    double sigma6 = std::pow(cfg.sigma, 6);
    double rc = cfg.cutoff * cfg.sigma;
    double rc2 = rc * rc;
    // Energy is shifted so it's exactly zero at the cutoff distance --
    // otherwise the potential has a small jump right where we stop
    // counting interactions, which would show up as fake energy drift.
    double ecut = 4.0 * cfg.epsilon * (sigma6 * sigma6 / std::pow(rc2, 6) - sigma6 / std::pow(rc2, 3));

    double total_potential_energy = 0.0;

    // Every pair of particles is checked once (i, j) with j > i --
    // this is the O(N^2) approach used in the original 2024 code, which
    // is fine for the particle counts this prototype targets (<= 500).
    for (size_t i = 0; i < n - 1; i++) {
        for (size_t j = i + 1; j < n; j++) {
            double dx = particles[i].x - particles[j].x;
            double dy = particles[i].y - particles[j].y;
            double dz = particles[i].z - particles[j].z;

            if (periodic) {
                // Minimum-image convention: measure the distance to the
                // NEAREST periodic copy of particle j, not necessarily
                // the one stored directly.
                dx -= box_length * std::round(dx / box_length);
                dy -= box_length * std::round(dy / box_length);
                dz -= box_length * std::round(dz / box_length);
            }

            double r2 = dx * dx + dy * dy + dz * dz;
            if (r2 >= rc2 || r2 < 1e-12) continue; // outside cutoff, or same point

            double r2i = 1.0 / r2;
            double r6i = r2i * r2i * r2i;

            // Lennard-Jones force magnitude (derived from -d(potential)/dr).
            double force_scale = 48.0 * cfg.epsilon * r2i * r6i * sigma6 * (r6i * sigma6 - 0.5);

            double fx = force_scale * dx;
            double fy = force_scale * dy;
            double fz = force_scale * dz;

            // Newton's third law: equal and opposite force on the other particle.
            particles[i].fx += fx; particles[i].fy += fy; particles[i].fz += fz;
            particles[j].fx -= fx; particles[j].fy -= fy; particles[j].fz -= fz;

            total_potential_energy += 4.0 * cfg.epsilon * sigma6 * r6i * (sigma6 * r6i - 1.0) - ecut;
        }
    }

    return total_potential_energy;
}

void apply_gravity(std::vector<Particle>& particles, double gravity_strength) {
    // "y" is treated as the vertical axis throughout this project (the
    // 3D viewer also treats y as up), so gravity simply reduces fy.
    for (size_t i = 0; i < particles.size(); i++) {
        particles[i].fy -= gravity_strength;
    }
}

void resolve_hard_sphere_collisions(std::vector<Particle>& particles, double particle_radius) {
    size_t n = particles.size();
    double min_dist = 2.0 * particle_radius;

    for (size_t i = 0; i < n - 1; i++) {
        for (size_t j = i + 1; j < n; j++) {
            double dx = particles[j].x - particles[i].x;
            double dy = particles[j].y - particles[i].y;
            double dz = particles[j].z - particles[i].z;
            double dist = std::sqrt(dx * dx + dy * dy + dz * dz);

            if (dist < min_dist && dist > 1e-9) {
                // Unit vector along the line connecting the two centers.
                double nx = dx / dist, ny = dy / dist, nz = dz / dist;

                // Separate the two particles so they don't stay overlapped.
                double overlap = min_dist - dist;
                particles[i].x -= nx * overlap * 0.5;
                particles[i].y -= ny * overlap * 0.5;
                particles[i].z -= nz * overlap * 0.5;
                particles[j].x += nx * overlap * 0.5;
                particles[j].y += ny * overlap * 0.5;
                particles[j].z += nz * overlap * 0.5;

                // Equal-mass elastic collision: the velocity component
                // ALONG the line of centers is swapped between the two
                // particles; the component perpendicular to it is
                // untouched (that's the part a real billiard-ball
                // collision doesn't change either).
                double vi_n = particles[i].vx * nx + particles[i].vy * ny + particles[i].vz * nz;
                double vj_n = particles[j].vx * nx + particles[j].vy * ny + particles[j].vz * nz;

                double delta_i = vj_n - vi_n;
                double delta_j = vi_n - vj_n;

                particles[i].vx += delta_i * nx; particles[i].vy += delta_i * ny; particles[i].vz += delta_i * nz;
                particles[j].vx += delta_j * nx; particles[j].vy += delta_j * ny; particles[j].vz += delta_j * nz;
            }
        }
    }
}
