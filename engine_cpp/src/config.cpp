// config.cpp
//
// See config.h for what each setting means. This file only does one
// thing: turn a text file of "key=value" lines into a filled-in
// SimConfig, falling back to defaults for anything the file doesn't set.

#include "config.h"
#include <fstream>
#include <sstream>
#include <map>
#include <algorithm>
#include <cctype>
#include <cstdlib>

// Reasonable defaults so the engine can still run on an incomplete
// config file (useful for quick manual testing).
SimConfig::SimConfig()
    : model("lennard_jones"),
      state("liquid"),
      container_enabled(true),
      container_shape("cuboid"),
      particle_count(200),
      container_size(10.0),
      density(0.8),
      temperature(1.0),
      particle_speed(1.2),
      timestep(0.001),
      total_time(5.0),
      epsilon(1.0),
      sigma(1.0),
      cutoff(2.5),
      output_dir("."),
      dump_every(20),
      seed(0) {}

// Removes leading/trailing whitespace from a string.
static std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

SimConfig load_config(const std::string& path) {
    SimConfig cfg; // start from defaults

    std::ifstream file(path.c_str());
    if (!file.is_open()) {
        // No config file found -- just run with defaults rather than crash.
        return cfg;
    }

    // Read every "key=value" line into a lookup table first, so we can
    // fill in the SimConfig fields in whatever order is convenient.
    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(file, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#') continue; // skip blanks/comments

        size_t eq = line.find('=');
        if (eq == std::string::npos) continue; // not a "key=value" line

        std::string key = trim(line.substr(0, eq));
        std::string value = trim(line.substr(eq + 1));
        values[key] = value;
    }

    // Helper lambdas to pull a value out of the table if it's present.
    auto has = [&](const std::string& k) { return values.find(k) != values.end(); };

    if (has("model")) cfg.model = values["model"];
    if (has("state")) cfg.state = values["state"];
    if (has("container_enabled")) cfg.container_enabled = (values["container_enabled"] == "true" || values["container_enabled"] == "1");
    if (has("container_shape")) cfg.container_shape = values["container_shape"];
    if (has("particle_count")) cfg.particle_count = std::atoi(values["particle_count"].c_str());
    if (has("container_size")) cfg.container_size = std::atof(values["container_size"].c_str());
    if (has("density")) cfg.density = std::atof(values["density"].c_str());
    if (has("temperature")) cfg.temperature = std::atof(values["temperature"].c_str());
    if (has("particle_speed")) cfg.particle_speed = std::atof(values["particle_speed"].c_str());
    if (has("timestep")) cfg.timestep = std::atof(values["timestep"].c_str());
    if (has("total_time")) cfg.total_time = std::atof(values["total_time"].c_str());
    if (has("epsilon")) cfg.epsilon = std::atof(values["epsilon"].c_str());
    if (has("sigma")) cfg.sigma = std::atof(values["sigma"].c_str());
    if (has("cutoff")) cfg.cutoff = std::atof(values["cutoff"].c_str());
    if (has("output_dir")) cfg.output_dir = values["output_dir"];
    if (has("dump_every")) cfg.dump_every = std::atoi(values["dump_every"].c_str());
    if (has("seed")) cfg.seed = static_cast<unsigned int>(std::atol(values["seed"].c_str()));

    return cfg;
}
