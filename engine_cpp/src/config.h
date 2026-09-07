// config.h
//
// Everything the engine needs for one simulation run, read from a small
// "key=value" text file. We use a plain text format instead of JSON on
// purpose: the engine only ever needs to READ its own config (never write
// or parse arbitrary JSON), so a hand-written line parser keeps this file
// free of any external library.

#ifndef CONFIG_H
#define CONFIG_H

#include <string>

struct SimConfig {
    // --- what to simulate ---
    std::string model;            // "lennard_jones" or "hard_sphere"
    std::string state;            // "solid", "liquid", or "gas"
    bool container_enabled;       // false = periodic box (particles wrap)
    std::string container_shape;  // "cuboid" or "sphere" (only used if container_enabled)

    // --- size and count ---
    int particle_count;
    double container_size;        // cuboid edge length, or sphere diameter
    double density;                // used to size the box when container is off (periodic)

    // --- energy / speed ---
    double temperature;            // Lennard-Jones: sets initial particle speed
    double particle_speed;         // Hard-Sphere: sets initial particle speed directly

    // --- time ---
    double timestep;
    double total_time;

    // --- Lennard-Jones potential parameters (reduced units) ---
    double epsilon;
    double sigma;
    double cutoff;

    // --- output ---
    std::string output_dir;
    int dump_every;                 // save a trajectory frame every N steps

    // --- reproducibility ---
    // 0 means "seed from the clock", so repeated demo runs look different.
    // Any other value makes the run repeat exactly, which is what the
    // automated tests rely on.
    unsigned int seed;

    SimConfig();
};

// Reads a "key=value" file (one setting per line, "#" starts a comment)
// and fills in a SimConfig, using sensible defaults for anything missing.
SimConfig load_config(const std::string& path);

#endif
