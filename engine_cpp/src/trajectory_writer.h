// trajectory_writer.h
//
// Writes the two files the frontend actually reads:
//   - trajectory.json: particle (x, y, z) positions -- plus each
//     particle's speed |v| -- at intervals through the run, so the browser
//     can play them back as a 3D animation and colour particles by how
//     fast they are actually moving.
//   - energy.csv: potential/kinetic/total energy at each recorded step,
//     so the browser can plot the energy-conservation chart.
//
// The JSON is written by hand (not through a library) because the shape
// of the file is entirely under our control -- it's simple enough that a
// small, purpose-built writer is clearer than pulling in a JSON library
// just to produce it.

#ifndef TRAJECTORY_WRITER_H
#define TRAJECTORY_WRITER_H

#include <fstream>
#include <string>
#include <vector>
#include "particle.h"
#include "config.h"

class TrajectoryWriter {
public:
    // Opens trajectory.json and energy.csv inside output_dir, and writes
    // the metadata header (model, state, container info, box size) that
    // the frontend needs before it can make sense of the frames.
    TrajectoryWriter(const std::string& output_dir, const SimConfig& cfg, double box_length);

    // Appends one frame to trajectory.json: each particle's position and
    // its current speed, as [x, y, z, |v|].
    void write_frame(const std::vector<Particle>& particles);

    // Appends one row of energy values to energy.csv.
    void write_energy(int step, double time, double potential, double kinetic);

    // Closes both files properly (finishes the JSON array/object).
    void close();

private:
    std::ofstream trajectory_file_;
    std::ofstream energy_file_;
    bool first_frame_;
};

#endif
