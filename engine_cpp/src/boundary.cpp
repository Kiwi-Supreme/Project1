// boundary.cpp
//
// See boundary.h for the purpose of each function. The rule of thumb
// used everywhere here: position gets corrected first, velocity gets
// flipped second, so a particle never ends up sitting outside its
// container after this code runs.

#include "boundary.h"
#include <cmath>
#include <cstddef>
using std::size_t;

void apply_periodic_boundary(std::vector<Particle>& particles, double box_length) {
    for (size_t i = 0; i < particles.size(); i++) {
        Particle& p = particles[i];
        // If a particle drifted outside [0, box_length), wrap it back in.
        if (p.x < 0) p.x += box_length; else if (p.x >= box_length) p.x -= box_length;
        if (p.y < 0) p.y += box_length; else if (p.y >= box_length) p.y -= box_length;
        if (p.z < 0) p.z += box_length; else if (p.z >= box_length) p.z -= box_length;
    }
}

void apply_reflective_cuboid(std::vector<Particle>& particles, double box_length) {
    for (size_t i = 0; i < particles.size(); i++) {
        Particle& p = particles[i];

        // Each axis is checked independently: hitting the x-wall only
        // flips vx, not vy or vz -- that's what makes it a "bounce" and
        // not a random deflection.
        if (p.x < 0) { p.x = -p.x; p.vx = -p.vx; }
        else if (p.x > box_length) { p.x = 2 * box_length - p.x; p.vx = -p.vx; }

        if (p.y < 0) { p.y = -p.y; p.vy = -p.vy; }
        else if (p.y > box_length) { p.y = 2 * box_length - p.y; p.vy = -p.vy; }

        if (p.z < 0) { p.z = -p.z; p.vz = -p.vz; }
        else if (p.z > box_length) { p.z = 2 * box_length - p.z; p.vz = -p.vz; }
    }
}

void apply_reflective_sphere(std::vector<Particle>& particles, double radius) {
    double cx = radius, cy = radius, cz = radius; // sphere is centered in its bounding cube

    for (size_t i = 0; i < particles.size(); i++) {
        Particle& p = particles[i];

        double dx = p.x - cx, dy = p.y - cy, dz = p.z - cz;
        double dist = std::sqrt(dx * dx + dy * dy + dz * dz);

        if (dist > radius && dist > 1e-9) {
            // Unit vector pointing from the sphere's center to the particle --
            // this is the surface normal at the point where it hit the wall.
            double nx = dx / dist, ny = dy / dist, nz = dz / dist;

            // Push the particle back onto the surface.
            p.x = cx + nx * radius;
            p.y = cy + ny * radius;
            p.z = cz + nz * radius;

            // Reflect velocity across the normal: v' = v - 2*(v.n)*n
            double vDotN = p.vx * nx + p.vy * ny + p.vz * nz;
            p.vx -= 2 * vDotN * nx;
            p.vy -= 2 * vDotN * ny;
            p.vz -= 2 * vDotN * nz;
        }
    }
}
