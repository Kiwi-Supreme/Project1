// trajectoryPlayer.js
//
// Takes the REAL trajectory the C++ engine produced (trajectory.json,
// already fetched and parsed by app.js) and plays it back through a
// Scene3D. Every position and every speed drawn on screen came straight
// out of the simulation -- nothing here generates motion.
//
// It also works out two things the viewer needs but the engine doesn't
// write out, both computed from the real positions:
//   - which pairs of particles are close enough to draw a bond between;
//   - the mean number of neighbours per particle, which is the single
//     clearest number for telling the three states apart (a solid sits
//     around twelve, a liquid a little lower, a gas near zero).

class TrajectoryPlayer {
  constructor(scene) {
    this.scene = scene;
    this.frames = [];
    this.frameIndex = 0;
    this.playing = true;
    this.speed = 1;              // playback rate, set from the View panel
    this.bondCutoffSigma = 1.35; // in sigma, set from the Display panel
    this._accumulator = 0;

    this.boxLength = 1;
    this.sigma = 1;
    this.speedMax = 1;
    this.stats = { neighbours: 0, meanSpeed: 0 };

    // Bonds are recomputed whenever the displayed frame or the cut-off
    // changes, and cached in between so a paused view costs nothing.
    this._bondCacheKey = null;
    this._bondCache = [];
  }

  // trajectory is the parsed trajectory.json object from the backend:
  // { box_length, sigma, container_enabled, container_shape, frames: [...] }
  // where each frame is [[x, y, z, speed], ...].
  load(trajectory) {
    this.boxLength = trajectory.box_length;
    this.sigma = trajectory.sigma || 1;

    // The engine works in [0, box_length] coordinates. The renderer works
    // in a fixed [-1, 1] cube. Positions are converted once, up front, so
    // playback is just array indexing. The speed is carried through
    // unchanged -- it is a real physical value, not a screen coordinate.
    this.frames = trajectory.frames.map((frame) =>
      frame.map(([x, y, z, speed]) => [
        (x / this.boxLength) * 2 - 1,
        (y / this.boxLength) * 2 - 1,
        (z / this.boxLength) * 2 - 1,
        speed || 0,
      ])
    );

    this.speedMax = this._computeSpeedScale();

    // A particle's radius is 0.5 sigma. The renderer's cube spans
    // box_length, so one simulation unit is 2 / box_length on screen.
    const particleRadius = (0.5 * this.sigma / this.boxLength) * 2;
    this.scene.setScale(particleRadius, this.speedMax);
    this.scene.setContainer(trajectory.container_enabled ? trajectory.container_shape : null);

    this.frameIndex = 0;
    this._accumulator = 0;
    this._bondCacheKey = null;
    this._showCurrentFrame();
  }

  // The top of the colour ramp. The single fastest particle in a run can
  // be far above the rest, and using it would push everything else into
  // the dark end of the ramp -- so a high percentile is used instead.
  _computeSpeedScale() {
    const sampled = [];
    const stride = Math.max(1, Math.floor(this.frames.length / 12));
    for (let f = 0; f < this.frames.length; f += stride) {
      for (const p of this.frames[f]) sampled.push(p[3]);
    }
    if (sampled.length === 0) return 1;
    sampled.sort((a, b) => a - b);
    const value = sampled[Math.floor(sampled.length * 0.98)];
    return value > 1e-6 ? value : 1;
  }

  frameCount() { return this.frames.length; }

  setBondCutoff(sigmaMultiples) {
    this.bondCutoffSigma = sigmaMultiples;
    this._bondCacheKey = null;
    this._showCurrentFrame();
  }

  setFrame(index) {
    if (this.frames.length === 0) return;
    this.frameIndex = Math.max(0, Math.min(this.frames.length - 1, index));
    this._accumulator = 0;
    this._showCurrentFrame();
  }

  restart() {
    this.frameIndex = 0;
    this._accumulator = 0;
    this._showCurrentFrame();
  }

  // Called once per animation tick (~60/sec). Advances through the real
  // frames at a rate controlled by this.speed.
  tick() {
    if (this.playing && this.frames.length > 0) {
      this._accumulator += this.speed * 0.5; // frames advanced per tick
      let moved = false;
      while (this._accumulator >= 1) {
        this.frameIndex = (this.frameIndex + 1) % this.frames.length;
        this._accumulator -= 1;
        moved = true;
      }
      if (moved) this._showCurrentFrame();
    }
  }

  _showCurrentFrame() {
    if (this.frames.length === 0) {
      this.scene.setFrame([], []);
      return;
    }
    const points = this.frames[this.frameIndex];
    const bonds = this._bondsFor(this.frameIndex, points);
    this.scene.setFrame(points, bonds);

    let speedSum = 0;
    for (const p of points) speedSum += p[3];
    this.stats = {
      neighbours: points.length ? (2 * bonds.length) / points.length : 0,
      meanSpeed: points.length ? speedSum / points.length : 0,
    };
  }

  _bondsFor(index, points) {
    const key = `${index}:${this.bondCutoffSigma}`;
    if (this._bondCacheKey === key) return this._bondCache;
    this._bondCache = this._computeBonds(points);
    this._bondCacheKey = key;
    return this._bondCache;
  }

  // Finds every pair of particles closer together than the cut-off.
  //
  // Checking all N*(N-1)/2 pairs every frame would be 125,000 distance
  // tests at the 500-particle limit, on every redraw. Instead the space
  // is chopped into cubic cells exactly one cut-off wide: two particles
  // can only be within the cut-off if they are in the same cell or in one
  // of the 26 cells touching it, so only those need to be checked.
  _computeBonds(points) {
    const cutoff = (this.bondCutoffSigma * this.sigma / this.boxLength) * 2;
    const cutoffSquared = cutoff * cutoff;
    const bonds = [];
    const MAX_BONDS = 20000; // a safety limit, never reached in practice

    // Bucket every particle by which cell it falls into.
    const cells = new Map();
    const cellIndex = (v) => Math.floor((v + 1) / cutoff);
    for (let i = 0; i < points.length; i++) {
      const key = `${cellIndex(points[i][0])},${cellIndex(points[i][1])},${cellIndex(points[i][2])}`;
      const bucket = cells.get(key);
      if (bucket) bucket.push(i); else cells.set(key, [i]);
    }

    for (let i = 0; i < points.length; i++) {
      const cx = cellIndex(points[i][0]);
      const cy = cellIndex(points[i][1]);
      const cz = cellIndex(points[i][2]);

      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          for (let dz = -1; dz <= 1; dz++) {
            const bucket = cells.get(`${cx + dx},${cy + dy},${cz + dz}`);
            if (!bucket) continue;
            for (const j of bucket) {
              if (j <= i) continue; // count each pair once
              const ax = points[i][0] - points[j][0];
              const ay = points[i][1] - points[j][1];
              const az = points[i][2] - points[j][2];
              if (ax * ax + ay * ay + az * az < cutoffSquared) {
                bonds.push([i, j]);
                if (bonds.length >= MAX_BONDS) return bonds;
              }
            }
          }
        }
      }
    }
    return bonds;
  }
}
