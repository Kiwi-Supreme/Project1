// initialize.cpp
//
// See initialize.h for the overview. The three functions at the bottom
// of this file (init_solid, init_liquid, init_gas) are where "state of
// matter" actually becomes real physics:
//
//   - solid  -> a tight, ordered lattice, small starting speed.
//   - liquid -> a loosely-packed cluster confined near the bottom of the
//               container, moderate starting speed, gravity (added in
//               main.cpp) keeps it there as the run continues.
//   - gas    -> particles scattered randomly through the WHOLE
//               container, higher starting speed, no gravity.
//
// Every one of these reads real values from SimConfig (particle count,
// density, container size/shape, temperature) -- nothing here is a
// fixed preset baked into the code.

#include "initialize.h"
#include <cmath>
#include <cstdlib>
#include <algorithm>

static double rand01() {
    return static_cast<double>(std::rand()) / (static_cast<double>(RAND_MAX) + 1.0);
}

double compute_box_length(const SimConfig& cfg) {
    if (cfg.container_enabled) {
        return cfg.container_size;
    }
    // No container: size the (invisible, periodic) box from particle
    // count and density, exactly like the original 2024 code did.
    return std::pow(static_cast<double>(cfg.particle_count) / cfg.density, 1.0 / 3.0);
}

// Removes any net drift (so the whole cloud of particles doesn't slide
// sideways) and rescales speeds so their average matches the requested
// temperature. This is the same technique the original 2024 code used.
static void assign_lj_velocities(std::vector<Particle>& particles, double temperature) {
    size_t n = particles.size();
    double sumv[3] = {0, 0, 0};
    double sumv2 = 0.0;

    for (size_t i = 0; i < n; i++) {
        particles[i].vx = rand01() - 0.5;
        particles[i].vy = rand01() - 0.5;
        particles[i].vz = rand01() - 0.5;
        sumv[0] += particles[i].vx;
        sumv[1] += particles[i].vy;
        sumv[2] += particles[i].vz;
        sumv2 += particles[i].vx * particles[i].vx + particles[i].vy * particles[i].vy + particles[i].vz * particles[i].vz;
    }

    sumv[0] /= n; sumv[1] /= n; sumv[2] /= n;
    sumv2 /= (3.0 * n);

    double scale = std::sqrt(temperature / sumv2);

    for (size_t i = 0; i < n; i++) {
        particles[i].vx = (particles[i].vx - sumv[0]) * scale;
        particles[i].vy = (particles[i].vy - sumv[1]) * scale;
        particles[i].vz = (particles[i].vz - sumv[2]) * scale;
    }
}

// Hard-Sphere particles don't have a "temperature" -- each one just gets
// a random direction at the requested speed.
static void assign_hard_sphere_velocities(std::vector<Particle>& particles, double speed) {
    for (size_t i = 0; i < particles.size(); i++) {
        double vx = rand01() - 0.5, vy = rand01() - 0.5, vz = rand01() - 0.5;
        double mag = std::sqrt(vx * vx + vy * vy + vz * vz);
        if (mag < 1e-9) mag = 1e-9;
        particles[i].vx = vx / mag * speed;
        particles[i].vy = vy / mag * speed;
        particles[i].vz = vz / mag * speed;
    }
}

static void assign_velocities(std::vector<Particle>& particles, const SimConfig& cfg) {
    if (cfg.model == "hard_sphere") {
        assign_hard_sphere_velocities(particles, cfg.particle_speed);
    } else {
        assign_lj_velocities(particles, cfg.temperature);
    }
}

// Fills a lattice (a grid of evenly-spaced points) starting at
// (x0, y0, z0), stopping once N particles have been placed. Spacing is
// derived from density, so a denser request genuinely packs particles
// closer together instead of just labeling them "solid".
static std::vector<Particle> build_lattice(int n, double spacing, double x0, double y0, double z0,
                                            int max_layers_y, double jitter) {
    std::vector<Particle> particles;
    int per_side = static_cast<int>(std::ceil(std::cbrt(static_cast<double>(n))));
    int idx = 0;

    for (int j = 0; j < max_layers_y && idx < n; j++) {
        for (int i = 0; i < per_side && idx < n; i++) {
            for (int k = 0; k < per_side && idx < n; k++) {
                Particle p;
                p.x = x0 + i * spacing + (rand01() - 0.5) * jitter;
                p.y = y0 + j * spacing + (rand01() - 0.5) * jitter;
                p.z = z0 + k * spacing + (rand01() - 0.5) * jitter;
                particles.push_back(p);
                idx++;
            }
        }
    }
    return particles;
}

static std::vector<Particle> init_solid(const SimConfig& cfg, double box_length) {
    // Tight, ordered lattice -- spacing comes straight from density
    // (higher density = particles packed closer together).
    // The natural resting distance between two Lennard-Jones particles is
    // about 1.12*sigma (where attraction and repulsion balance). Starting
    // particles any closer than that puts them inside each other's steep
    // repulsive wall, which shows up as a visible "jump apart" in the
    // first instants of the run -- so density sets the spacing, but never
    // closer than that natural resting distance.
    double spacing = std::max(cfg.sigma / std::cbrt(cfg.density), 1.05 * cfg.sigma);
    int per_side = static_cast<int>(std::ceil(std::cbrt(static_cast<double>(cfg.particle_count))));
    double block_size = per_side * spacing;

    double x0, y0, z0;
    if (cfg.container_enabled) {
        // Center the block horizontally, rest it on the container floor.
        x0 = std::max(0.05 * box_length, (box_length - block_size) / 2.0);
        z0 = std::max(0.05 * box_length, (box_length - block_size) / 2.0);
        y0 = 0.05 * box_length;
    } else {
        // Periodic mode: the lattice must tile the box EXACTLY, so a
        // particle near one edge and its periodic image near the
        // opposite edge end up a full spacing apart, not crushed
        // together. Using the density-derived spacing directly can
        // leave a gap smaller than that at the wrap-around seam (it
        // only lines up perfectly when particle_count is a perfect
        // cube), so the spacing is snapped to divide the box evenly.
        spacing = box_length / per_side;
        x0 = y0 = z0 = 0.0;
    }

    std::vector<Particle> particles = build_lattice(cfg.particle_count, spacing, x0, y0, z0,
                                                      per_side, /*jitter=*/spacing * 0.02);
    assign_velocities(particles, cfg);
    return particles;
}

static std::vector<Particle> init_liquid(const SimConfig& cfg, double box_length) {
    // The natural resting distance between two Lennard-Jones particles is
    // about 1.12*sigma (where attraction and repulsion balance). Starting
    // particles any closer than that puts them inside each other's steep
    // repulsive wall, which shows up as a visible "jump apart" in the
    // first instants of the run -- so density sets the spacing, but never
    // closer than that natural resting distance.
    double spacing = std::max(cfg.sigma / std::cbrt(cfg.density), 1.05 * cfg.sigma);
    int per_side = static_cast<int>(std::ceil(std::cbrt(static_cast<double>(cfg.particle_count))));

    double x0, y0, z0;
    int max_layers;
    if (cfg.container_enabled) {
        // Confine the starting block to roughly the bottom 45% of the
        // container's height -- this, plus gravity during the run, is
        // what makes a liquid visibly "pool" instead of filling the box.
        double usable_height = box_length * 0.45;
        int layers_for_target_height = std::max(1, static_cast<int>(usable_height / spacing));
        // But never drop particles to keep that target: if there are too
        // many for the 45% band at this density, the "pool" just gets a
        // little deeper instead of losing particles -- still a liquid,
        // still settled at the bottom, just more of it.
        int layers_needed_for_all = static_cast<int>(std::ceil(
            static_cast<double>(cfg.particle_count) / (per_side * per_side)));
        max_layers = std::max(layers_for_target_height, layers_needed_for_all);
        double block_size = per_side * spacing;
        x0 = std::max(0.05 * box_length, (box_length - block_size) / 2.0);
        z0 = std::max(0.05 * box_length, (box_length - block_size) / 2.0);
        y0 = 0.05 * box_length;
    } else {
        // Periodic mode: snap the spacing so the lattice tiles the box
        // exactly (see the matching comment in init_solid) -- otherwise
        // particles wrapped across the box edge can end up far closer
        // together than the intended spacing, which blows up the force
        // calculation on the very first step.
        spacing = box_length / per_side;
        x0 = y0 = z0 = 0.0;
        max_layers = per_side;
    }

    // A bigger jitter than the solid case -- particles are close together
    // but not locked into a rigid crystal. The jitter is capped at a
    // fraction of whatever spacing ended up being used, so it can never
    // exceed the (possibly tighter, periodic) spacing above.
    std::vector<Particle> particles = build_lattice(cfg.particle_count, spacing, x0, y0, z0,
                                                      max_layers, /*jitter=*/spacing * 0.35);
    assign_velocities(particles, cfg);
    return particles;
}

static std::vector<Particle> init_gas(const SimConfig& cfg, double box_length) {
    std::vector<Particle> particles;
    double radius = box_length / 2.0; // used only if the container is a sphere
    double min_separation = cfg.sigma * 0.8;

    // Gas particles are spread randomly through the ENTIRE available
    // volume (the whole cuboid, or the whole sphere) -- this is what
    // makes a gas visibly fill the container instead of clustering.
    while (static_cast<int>(particles.size()) < cfg.particle_count) {
        double x = rand01() * box_length;
        double y = rand01() * box_length;
        double z = rand01() * box_length;

        if (cfg.container_enabled && cfg.container_shape == "sphere") {
            double dx = x - radius, dy = y - radius, dz = z - radius;
            if (std::sqrt(dx * dx + dy * dy + dz * dz) > radius) continue; // outside the sphere, try again
        }

        // Simple rejection check so two particles don't spawn on top of each other.
        // In periodic mode, "on top of each other" includes wrapping across
        // the box edge, so the check uses the same minimum-image distance
        // the force calculation itself will use.
        bool too_close = false;
        for (size_t i = 0; i < particles.size() && !too_close; i++) {
            double dx = particles[i].x - x, dy = particles[i].y - y, dz = particles[i].z - z;
            if (!cfg.container_enabled) {
                dx -= box_length * std::round(dx / box_length);
                dy -= box_length * std::round(dy / box_length);
                dz -= box_length * std::round(dz / box_length);
            }
            if (dx * dx + dy * dy + dz * dz < min_separation * min_separation) too_close = true;
        }
        if (too_close) continue;

        Particle p;
        p.x = x; p.y = y; p.z = z;
        particles.push_back(p);
    }

    assign_velocities(particles, cfg);
    return particles;
}

std::vector<Particle> initialize_particles(const SimConfig& cfg, double box_length) {
    if (cfg.state == "solid") return init_solid(cfg, box_length);
    if (cfg.state == "gas") return init_gas(cfg, box_length);
    return init_liquid(cfg, box_length); // default / "liquid"
}
