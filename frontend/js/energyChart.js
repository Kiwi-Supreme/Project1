// energyChart.js
//
// Draws the energy-vs-time chart from the REAL energy.csv rows the C++
// engine produced (one {step, time, potential, kinetic, total} object per
// saved step). Nothing here is invented -- the axis range is fitted to
// the actual data.
//
// The chart is the project's correctness evidence, not decoration: for a
// periodic run, or for hard spheres, the total line staying flat is what
// shows the forces and the integrator are right.

const SERIES = [
  { key: "potential", label: "potential", color: "#3987e5" },
  { key: "kinetic",   label: "kinetic",   color: "#d95926" },
  { key: "total",     label: "total",     color: "#199e70" },
];

class EnergyChart {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.rows = [];
    this.hoverIndex = null;
    this.width = 1;
    this.height = 1;

    canvas.addEventListener("pointermove", (e) => {
      if (this.rows.length === 0) return;
      const rect = canvas.getBoundingClientRect();
      this.hoverIndex = this._indexAtX(e.clientX - rect.left);
      this.draw();
    });
    canvas.addEventListener("pointerleave", () => {
      this.hoverIndex = null;
      this.draw();
    });

    this.resize();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = Math.max(1, Math.round(rect.width));
    this.height = Math.max(1, Math.round(rect.height));
    this.canvas.width = Math.round(this.width * dpr);
    this.canvas.height = Math.round(this.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.draw();
  }

  setData(rows) {
    this.rows = rows || [];
    this.hoverIndex = null;
    this.draw();
  }

  _layout() {
    return { left: 62, right: 96, top: 18, bottom: 40 };
  }

  _indexAtX(px) {
    const pad = this._layout();
    const plotW = this.width - pad.left - pad.right;
    const f = (px - pad.left) / plotW;
    const i = Math.round(f * (this.rows.length - 1));
    return Math.max(0, Math.min(this.rows.length - 1, i));
  }

  draw() {
    const ctx = this.ctx, W = this.width, H = this.height;
    ctx.fillStyle = "#141414";
    ctx.fillRect(0, 0, W, H);

    if (this.rows.length < 2) {
      ctx.fillStyle = "#7d7d7d";
      ctx.font = '12px ui-monospace, Consolas, monospace';
      ctx.fillText("No run yet — press Run Simulation.", 16, 26);
      return;
    }

    const pad = this._layout();
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;
    if (plotW < 40 || plotH < 40) return;

    // Fit the y-axis to the actual values, with a little breathing room.
    let yMin = Infinity, yMax = -Infinity;
    for (const row of this.rows) {
      for (const s of SERIES) {
        if (row[s.key] < yMin) yMin = row[s.key];
        if (row[s.key] > yMax) yMax = row[s.key];
      }
    }
    const margin = Math.max(0.2, (yMax - yMin) * 0.12);
    yMin -= margin; yMax += margin;

    const yToPx = (v) => pad.top + ((yMax - v) / (yMax - yMin)) * plotH;
    const xToPx = (i) => pad.left + (i / (this.rows.length - 1)) * plotW;

    // --- recessive grid + axis labels ---
    ctx.strokeStyle = "#2b2b2b";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#7d7d7d";
    ctx.font = '10.5px ui-monospace, Consolas, monospace';
    ctx.textAlign = "right";
    for (let s = 0; s <= 4; s++) {
      const v = yMin + (s / 4) * (yMax - yMin);
      const y = Math.round(yToPx(v)) + 0.5;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
      ctx.fillText(v.toFixed(2), pad.left - 7, y + 3.5);
    }

    ctx.textAlign = "center";
    const lastTime = this.rows[this.rows.length - 1].time;
    for (let s = 0; s <= 4; s++) {
      const i = Math.round((s / 4) * (this.rows.length - 1));
      const x = Math.round(xToPx(i)) + 0.5;
      ctx.strokeStyle = "#232323";
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();
      ctx.fillStyle = "#7d7d7d";
      ctx.fillText(this.rows[i].time.toFixed(1), x, H - pad.bottom + 15);
    }

    ctx.fillStyle = "#7d7d7d";
    ctx.fillText("time (reduced units)", pad.left + plotW / 2, H - 8);
    ctx.save();
    ctx.translate(14, pad.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("energy per particle", 0, 0);
    ctx.restore();

    // --- the three series ---
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    for (const s of SERIES) {
      ctx.strokeStyle = s.color;
      ctx.beginPath();
      this.rows.forEach((row, i) => {
        const x = xToPx(i), y = yToPx(row[s.key]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    // --- direct labels at the right-hand end of each line ---
    // With three series, naming each line where it ends means identity is
    // never carried by colour alone.
    const last = this.rows[this.rows.length - 1];
    ctx.textAlign = "left";
    ctx.font = '10.5px ui-monospace, Consolas, monospace';
    const placed = [];
    for (const s of SERIES) {
      let y = yToPx(last[s.key]);
      while (placed.some((p) => Math.abs(p - y) < 12)) y += 12;
      placed.push(y);

      ctx.fillStyle = s.color;
      ctx.fillRect(W - pad.right + 6, y - 4, 7, 7);
      ctx.fillStyle = "#b9b9b9";
      ctx.fillText(s.label, W - pad.right + 18, y + 3.5);
    }

    // --- hover crosshair with the real values at that instant ---
    if (this.hoverIndex !== null) {
      const i = this.hoverIndex;
      const x = Math.round(xToPx(i)) + 0.5;
      ctx.strokeStyle = "#5a5a5a";
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();

      for (const s of SERIES) {
        ctx.fillStyle = s.color;
        ctx.beginPath(); ctx.arc(x, yToPx(this.rows[i][s.key]), 3.5, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = "#141414"; ctx.lineWidth = 1.5; ctx.stroke();
      }

      const lines = [
        `t = ${this.rows[i].time.toFixed(3)}`,
        `potential  ${this.rows[i].potential.toFixed(3)}`,
        `kinetic    ${this.rows[i].kinetic.toFixed(3)}`,
        `total      ${this.rows[i].total.toFixed(3)}`,
      ];
      const boxW = 132, boxH = lines.length * 14 + 8;
      const bx = Math.min(x + 10, W - pad.right - boxW);
      const by = pad.top + 6;
      ctx.fillStyle = "rgba(24,24,24,0.94)";
      ctx.fillRect(bx, by, boxW, boxH);
      ctx.strokeStyle = "#3d3d3d"; ctx.lineWidth = 1;
      ctx.strokeRect(bx + 0.5, by + 0.5, boxW, boxH);
      ctx.fillStyle = "#d2d2d2";
      ctx.textAlign = "left";
      lines.forEach((line, k) => ctx.fillText(line, bx + 7, by + 16 + k * 14));
    }
  }
}
