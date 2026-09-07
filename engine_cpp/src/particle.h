// particle.h
//
// A "Particle" is just a point with a position, a velocity, and the force
// currently acting on it. Every particle in the simulation uses this same
// struct, whether it's part of a Lennard-Jones fluid or a hard-sphere gas.
//
// Positions/velocities/forces are stored as plain doubles (x, y, z) instead
// of a vector class on purpose -- it keeps the force and integration code
// easy to read line by line, which matters more here than saving a few
// lines with operator overloading.

#ifndef PARTICLE_H
#define PARTICLE_H

struct Particle {
    double x, y, z;     // position (simulation units, inside the container)
    double vx, vy, vz;  // velocity
    double fx, fy, fz;  // force currently acting on the particle

    Particle() : x(0), y(0), z(0), vx(0), vy(0), vz(0), fx(0), fy(0), fz(0) {}
};

#endif
