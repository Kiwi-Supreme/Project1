// scene3d.js
//
// A small, hand-written 3D renderer for the viewport. It draws the real
// particle positions it is handed frame by frame (see trajectoryPlayer.js)
// inside the container, with a camera that can be rotated and zoomed.
//
// This is plain <canvas> 2D drawing with the 3D maths (rotation,
// perspective projection) done by hand, not a 3D library -- the whole
// scene is a few hundred particles, a wireframe container and some bond
// lines, which doesn't need WebGL to run smoothly, and it keeps this file
// readable top to bottom.
//
// Everything it draws is measured, not decorative:
//   - a ball is drawn at the particle's TRUE radius (0.5 sigma), so how
//     tightly packed a state is can be seen directly;
//   - its colour is the particle's real speed from the engine, on a
//     single-hue dark-to-light ramp (slow = dark blue, fast = near white);
//   - a bond is drawn between any two particles genuinely closer than the
//     cut-off distance.
// Those three together are what make a solid, a liquid and a gas look
// different from each other rather than looking like the same cloud of
// dots in different places.

// A single-hue ramp, dark to light. One hue (blue) rising steadily in
// lightness is what a "how much of this quantity" scale should be -- a
// rainbow would invent boundaries in the data that aren't there.
const SPEED_RAMP = [
  [0.00, [22, 69, 127]],
  [0.35, [42, 114, 196]],
  [0.70, [111, 169, 232]],
  [1.00, [207, 230, 255]],
];

function speedColor(t) {
  const x = Math.max(0, Math.min(1, t));
  for (let i = 1; i < SPEED_RAMP.length; i++) {
    if (x <= SPEED_RAMP[i][0]) {
      const [t0, c0] = SPEED_RAMP[i - 1];
      const [t1, c1] = SPEED_RAMP[i];
      const f = (x - t0) / (t1 - t0);
      return `rgb(${Math.round(c0[0] + (c1[0] - c0[0]) * f)},` +
             `${Math.round(c0[1] + (c1[1] - c0[1]) * f)},` +
             `${Math.round(c0[2] + (c1[2] - c0[2]) * f)})`;
    }
  }
  return "rgb(207,230,255)";
}

class Scene3D {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.width = 1;
    this.height = 1;

    // Camera: yaw/pitch = rotation around the scene, dist = zoom.
    this.view = { yaw: 0.55, pitch: 0.32, dist: 5.5 };
    this.target = { yaw: 0.55, pitch: 0.32, dist: 5.5 };
    this.autoRotate = false;

    // What to draw. containerShape is "cuboid", "sphere", or null (no
    // container -- periodic mode). points is an array of
    // [x, y, z, speed]; x/y/z are in the renderer's own -1..1 cube,
    // speed is the particle's real speed from the engine.
    this.containerShape = null;
    this.points = [];
    this.bonds = [];

    // Scale information supplied by whoever loaded the trajectory.
    this.particleRadius = 0.05;  // one particle radius, in -1..1 units
    this.speedMax = 1;           // speed that maps to the top of the ramp

    this.show = {
      balls: true, bonds: true, speed: true,
      container: true, grid: true, axes: true, depth: false,
    };
    this.ballScale = 0.55;

    this._wireInput();
    this.resize();
  }

  // The canvas fills whatever space the layout gives it, so its drawing
  // buffer has to be re-matched to its on-screen size (and to the
  // display's pixel density) whenever that changes.
  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = Math.max(1, Math.round(rect.width));
    this.height = Math.max(1, Math.round(rect.height));
    this.canvas.width = Math.round(this.width * dpr);
    this.canvas.height = Math.round(this.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  setContainer(shape) { this.containerShape = shape; }

  // points: [[x, y, z, speed], ...]   bonds: [[i, j], ...]
  setFrame(points, bonds) {
    this.points = points || [];
    this.bonds = bonds || [];
  }

  setScale(particleRadius, speedMax) {
    this.particleRadius = particleRadius;
    this.speedMax = speedMax > 0 ? speedMax : 1;
  }

  resetView() {
    this.target.yaw = 0.55;
    this.target.pitch = 0.32;
    this.target.dist = 5.5;
  }

  _wireInput() {
    const canvas = this.canvas;
    let dragging = false, lastX = 0, lastY = 0;

    canvas.addEventListener("pointerdown", (e) => {
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX, dy = e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      this.target.yaw += dx * 0.008;
      this.target.pitch = Math.max(-1.3, Math.min(1.3, this.target.pitch + dy * 0.008));
      if (this.onViewChange) this.onViewChange();
    });
    window.addEventListener("pointerup", () => { dragging = false; });

    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      this.target.dist = Math.max(2, Math.min(14, this.target.dist + e.deltaY * 0.0025 * this.target.dist));
      if (this.onViewChange) this.onViewChange();
    }, { passive: false });
  }

  // --- 3D maths: rotate a point around the scene, then project it onto the canvas ---
  _rotate(p) {
    const { yaw, pitch } = this.view;
    const cy = Math.cos(yaw), sy = Math.sin(yaw);
    const x1 = p[0] * cy - p[2] * sy;
    const z1 = p[0] * sy + p[2] * cy;
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const y2 = p[1] * cp - z1 * sp;
    const z2 = p[1] * sp + z1 * cp;
    return [x1, y2, z2];
  }

  _project(p) {
    // Perspective divide: the further a point is from the camera, the
    // smaller it is drawn. The focal length is tied to the viewport size
    // so the scene fills the same fraction of the panel whatever its
    // shape; the zoom slider moves the camera (dist) rather than changing
    // the lens, which is what keeps the perspective looking consistent.
    const camZ = p[2] + this.view.dist;
    // 1.5x the short side, paired with a default camera distance of 5.5,
    // frames the whole container with a margin and keeps the perspective
    // gentle -- a closer camera exaggerates the near corners badly.
    const f = Math.min(this.width, this.height) * 1.5;
    const scale = f / Math.max(camZ, 0.15);
    return { x: this.width / 2 + p[0] * scale, y: this.height / 2 - p[1] * scale, scale, depth: camZ };
  }

  _projectPoint(p) { return this._project(this._rotate(p)); }

  // Renders one frame using whatever setFrame()/setContainer() were last given.
  draw() {
    if (this.autoRotate) this.target.yaw += 0.006;

    // camera eases toward the drag/slider target -- makes rotation smooth
    this.view.yaw += (this.target.yaw - this.view.yaw) * 0.15;
    this.view.pitch += (this.target.pitch - this.view.pitch) * 0.15;
    this.view.dist += (this.target.dist - this.view.dist) * 0.15;

    const ctx = this.ctx;
    ctx.fillStyle = "#141414";
    ctx.fillRect(0, 0, this.width, this.height);

    if (this.show.grid) this._drawFloorGrid();
    if (this.show.container && this.containerShape === "cuboid") this._drawCuboid();
    if (this.show.container && this.containerShape === "sphere") this._drawSphere();

    // Project every particle once, then reuse those screen positions for
    // both the bonds and the balls.
    const projected = this.points.map((p) => this._projectPoint(p));
    if (this.show.bonds) this._drawBonds(projected);
    if (this.show.balls) this._drawBalls(projected);
    if (this.show.axes) this._drawAxes();
  }

  _drawFloorGrid() {
    const ctx = this.ctx;
    ctx.strokeStyle = "#2b2b2b";
    ctx.lineWidth = 1;
    for (let g = -1; g <= 1.001; g += 0.5) {
      const a = this._projectPoint([g, -1, -1]);
      const b = this._projectPoint([g, -1, 1]);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      const c = this._projectPoint([-1, -1, g]);
      const d = this._projectPoint([1, -1, g]);
      ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(d.x, d.y); ctx.stroke();
    }
  }

  _drawCuboid() {
    const ctx = this.ctx;
    const corners = [];
    for (const bx of [-1, 1]) for (const by of [-1, 1]) for (const bz of [-1, 1]) corners.push([bx, by, bz]);
    const edges = [[0,1],[0,2],[0,4],[1,3],[1,5],[2,3],[2,6],[3,7],[4,5],[4,6],[5,7],[6,7]];
    const projected = corners.map((c) => this._projectPoint(c));
    ctx.strokeStyle = "#5f5f5f";
    ctx.lineWidth = 1;
    edges.forEach(([a, b]) => {
      ctx.beginPath(); ctx.moveTo(projected[a].x, projected[a].y); ctx.lineTo(projected[b].x, projected[b].y); ctx.stroke();
    });
  }

  _drawSphere() {
    const ctx = this.ctx;
    ctx.strokeStyle = "#4f4f4f";
    ctx.lineWidth = 1;
    const rings = 5, segments = 28;
    for (let r = 0; r < rings; r++) {
      const phi = (Math.PI * (r + 1)) / (rings + 1) - Math.PI / 2;
      const ringRadius = Math.cos(phi);
      const y = Math.sin(phi);
      let prev = null;
      for (let s = 0; s <= segments; s++) {
        const theta = (2 * Math.PI * s) / segments;
        const p = this._projectPoint([ringRadius * Math.cos(theta), y, ringRadius * Math.sin(theta)]);
        if (prev) { ctx.beginPath(); ctx.moveTo(prev.x, prev.y); ctx.lineTo(p.x, p.y); ctx.stroke(); }
        prev = p;
      }
    }
    for (let m = 0; m < 6; m++) {
      const theta = (Math.PI * m) / 6;
      let prev = null;
      for (let s = 0; s <= segments; s++) {
        const phi = (Math.PI * s) / segments - Math.PI / 2;
        const p = this._projectPoint([Math.cos(phi) * Math.cos(theta), Math.sin(phi), Math.cos(phi) * Math.sin(theta)]);
        if (prev) { ctx.beginPath(); ctx.moveTo(prev.x, prev.y); ctx.lineTo(p.x, p.y); ctx.stroke(); }
        prev = p;
      }
    }
  }

  _drawBonds(projected) {
    const ctx = this.ctx;
    ctx.strokeStyle = "#8c8c8c";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let b = 0; b < this.bonds.length; b++) {
      const a = projected[this.bonds[b][0]];
      const c = projected[this.bonds[b][1]];
      if (!a || !c) continue;
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(c.x, c.y);
    }
    ctx.stroke();
  }

  _drawBalls(projected) {
    const ctx = this.ctx;

    // Painter's algorithm: draw far particles first so near ones sit on
    // top of them. The index is carried along so each drawn ball keeps
    // its own speed.
    const order = projected.map((proj, i) => i);
    order.sort((a, b) => projected[b].depth - projected[a].depth);

    for (let k = 0; k < order.length; k++) {
      const i = order[k];
      const proj = projected[i];
      const speed = this.points[i][3] || 0;

      const r = Math.max(1.0, this.particleRadius * proj.scale * this.ballScale);
      const fill = this.show.speed
        ? speedColor(speed / this.speedMax)
        : "#d4d4d4";

      ctx.globalAlpha = this.show.depth
        ? Math.max(0.3, Math.min(1, 1.6 - proj.depth / (this.view.dist * 1.8)))
        : 1;
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.arc(proj.x, proj.y, r, 0, Math.PI * 2);
      ctx.fill();

      // A thin dark rim keeps neighbouring balls readable as separate
      // objects when they are packed tightly (a solid or a dense liquid).
      if (r > 2.2) {
        ctx.globalAlpha = 1;
        ctx.strokeStyle = "#141414";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  // A small orientation marker in the corner, the way a molecular viewer
  // shows which way the axes point. x = red, y = green, z = blue.
  _drawAxes() {
    const ctx = this.ctx;
    const ox = 32, oy = this.height - 32, len = 20;
    const axes = [[[1, 0, 0], "#e05a4a"], [[0, 1, 0], "#4fb36a"], [[0, 0, 1], "#4a86e0"]];

    axes.forEach(([axis, color]) => {
      const r = this._rotate(axis);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(ox, oy);
      ctx.lineTo(ox + r[0] * len, oy - r[1] * len);
      ctx.stroke();
    });
  }
}
