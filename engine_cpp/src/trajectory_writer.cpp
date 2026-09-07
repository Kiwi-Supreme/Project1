// trajectory_writer.cpp
//
// See trajectory_writer.h. The JSON written here has this shape:
//
// {
//   "model": "lennard_jones", "state": "liquid",
//   "container_shape": "cuboid", "container_enabled": true,
//   "box_length": 10.0, "sigma": 1.0, "dt": 0.001, "dump_every": 20,
//   "frames": [
//     [[x,y,z,speed], [x,y,z,speed], ...],  <- one entry per particle,
//     [[x,y,z,speed], [x,y,z,speed], ...],     one array per frame
//     ...
//   ]
// }
//
// The fourth number is the particle's speed |v| at that instant. It is
// written here rather than recomputed in the browser because the browser
// only ever receives positions -- and the viewer colours particles by
// speed, which is what makes a slow, ordered solid look different from a
// fast, scattered gas on screen.
//
// It's written incrementally (one frame at a time) instead of building
// the whole thing in memory first, so a long run doesn't need to hold
// every frame at once.

#include "trajectory_writer.h"
#include <sstream>
#include <cmath>

TrajectoryWriter::TrajectoryWriter(const std::string& output_dir, const SimConfig& cfg, double box_length)
    : first_frame_(true) {
    trajectory_file_.open((output_dir + "/trajectory.json").c_str());
    energy_file_.open((output_dir + "/energy.csv").c_str());

    // --- trajectory.json header ---
    trajectory_file_ << "{\n";
    trajectory_file_ << "\"model\":\"" << cfg.model << "\",\n";
    trajectory_file_ << "\"state\":\"" << cfg.state << "\",\n";
    trajectory_file_ << "\"container_enabled\":" << (cfg.container_enabled ? "true" : "false") << ",\n";
    trajectory_file_ << "\"container_shape\":\"" << cfg.container_shape << "\",\n";
    trajectory_file_ << "\"box_length\":" << box_length << ",\n";
    // sigma is needed by the viewer to draw particles at their true size
    // and to decide which pairs are close enough to count as neighbours.
    trajectory_file_ << "\"sigma\":" << cfg.sigma << ",\n";
    trajectory_file_ << "\"particle_count\":" << cfg.particle_count << ",\n";
    trajectory_file_ << "\"dt\":" << cfg.timestep << ",\n";
    trajectory_file_ << "\"dump_every\":" << cfg.dump_every << ",\n";
    trajectory_file_ << "\"frames\":[\n";

    // --- energy.csv header ---
    energy_file_ << "step,time,potential,kinetic,total\n";
}

void TrajectoryWriter::write_frame(const std::vector<Particle>& particles) {
    if (!first_frame_) trajectory_file_ << ",\n";
    first_frame_ = false;

    trajectory_file_ << "[";
    for (size_t i = 0; i < particles.size(); i++) {
        const Particle& p = particles[i];
        if (i > 0) trajectory_file_ << ",";
        double speed = std::sqrt(p.vx * p.vx + p.vy * p.vy + p.vz * p.vz);
        trajectory_file_ << "[" << p.x << "," << p.y << "," << p.z << "," << speed << "]";
    }
    trajectory_file_ << "]";
}

void TrajectoryWriter::write_energy(int step, double time, double potential, double kinetic) {
    energy_file_ << step << "," << time << "," << potential << "," << kinetic << "," << (potential + kinetic) << "\n";
}

void TrajectoryWriter::close() {
    trajectory_file_ << "\n]\n}\n";
    trajectory_file_.close();
    energy_file_.close();
}
