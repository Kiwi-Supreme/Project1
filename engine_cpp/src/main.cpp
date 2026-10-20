// main.cpp
//
// This is the whole simulation, wired together. The flow is exactly:
//
//   load settings -> place particles -> repeat { compute interactions,
//   move particles, keep them inside the container, occasionally save
//   a snapshot } -> close the output files.
//
// Run it as:  md_engine path/to/config.txt
// (if no path is given, it looks for "config.txt" in the current folder)
//
// It writes trajectory.json and energy.csv into the configured output
// directory -- those two files are everything the frontend needs.

#include <iostream>
#include <cstdlib>
#include <ctime>

#include "config.h"
#include "particle.h"
#include "initialize.h"
#include "forces.h"
#include "boundary.h"
#include "integrator.h"
#include "trajectory_writer.h"

int main(int argc, char** argv) {
    std::string config_path = (argc > 1) ? argv[1] : "config.txt";
    SimConfig cfg = load_config(config_path);

    // A seed of 0 (the default) means "vary every run", which is what a
    // live demo wants. A fixed seed makes the whole run repeatable, which
    // is what the automated tests need to assert anything about the result.
    std::srand(cfg.seed != 0 ? cfg.seed : static_cast<unsigned int>(std::time(nullptr)));

    // --- set up the simulation space and the starting particles ---
    double box_length = compute_box_length(cfg);
    std::vector<Particle> particles = initialize_particles(cfg, box_length);
    bool periodic = !cfg.container_enabled;
    double particle_radius = 0.5 * cfg.sigma;

    // --- figure out how many steps to run and how often to save a frame ---
    int total_steps = static_cast<int>(cfg.total_time / cfg.timestep);
    if (total_steps < 1) total_steps = 1;
    cfg.dump_every = std::max(1, total_steps / 250); // aim for ~250 saved frames

    TrajectoryWriter writer(cfg.output_dir, cfg, box_length);

    bool is_lj = (cfg.model != "hard_sphere");

    // --- compute the force at the very start, before the loop begins ---
    double potential_energy = 0.0;
    if (is_lj) {
        potential_energy = compute_lj_forces(particles, cfg, box_length, periodic);
    } else {
        for (size_t i = 0; i < particles.size(); i++) particles[i].fx = particles[i].fy = particles[i].fz = 0.0;
    }

    // --- the main simulation loop ---
    // Each iteration starts holding the TRUE state at time = step*dt
    // (positions, velocities, and the force already computed for that
    // position) -- so a snapshot is saved first, THEN the state is
    // advanced to step+1. Saving before advancing (rather than after)
    // means frame 0 is always the real, untouched starting configuration.
    for (int step = 0; step <= total_steps; step++) {
        // 1. Every so often, save the CURRENT (not-yet-advanced) state
        //    for the 3D viewer and the energy chart.
        if (step % cfg.dump_every == 0) {
            double kinetic_energy = 0.0;
            for (size_t i = 0; i < particles.size(); i++) {
                const Particle& p = particles[i];
                kinetic_energy += 0.5 * (p.vx * p.vx + p.vy * p.vy + p.vz * p.vz);
            }
            kinetic_energy /= particles.size();
            double pe_per_particle = is_lj ? (potential_energy / particles.size()) : 0.0;

            writer.write_frame(particles);
            writer.write_energy(step, step * cfg.timestep, pe_per_particle, kinetic_energy);
        }

        // 2. Move every particle half a step using the current force, then a full position step.
        begin_step(particles, cfg.timestep);

        // 3. Keep particles inside the simulation space (wrap or bounce).
        if (periodic) {
            apply_periodic_boundary(particles, box_length);
        } else if (cfg.container_shape == "sphere") {
            apply_reflective_sphere(particles, box_length / 2.0);
        } else {
            apply_reflective_cuboid(particles, box_length);
        }

        // 4. Recompute the force at the new positions (Lennard-Jones only --
        //    Hard-Sphere has no continuous force, just collisions).
        if (is_lj) {
            potential_energy = compute_lj_forces(particles, cfg, box_length, periodic);
        } else {
            resolve_hard_sphere_collisions(particles, particle_radius);
        }
    
        // 5. Finish the velocity update using the new force.
        finish_step(particles, cfg.timestep);

    }

    writer.close();

    std::cout << "Simulation finished: " << total_steps << " steps, "
              << particles.size() << " particles, model=" << cfg.model
              << ", state=" << cfg.state << std::endl;
    return 0;
}
