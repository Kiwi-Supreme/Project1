// plots.js
//
// A small general-purpose chart used by the Analysis and Experiments tabs. It draws
// exactly what the backend describes (backend/analysis/graphs.py, backend/sweeps.py):
// lines, points with error bars, histogram bars, reference lines, and nothing else.
// Same dark surface, fonts and colours as the Energy chart.

const PLOT_COLORS = ["#3987e5", "#d95926", "#199e70", "#d6a72b", "#a77bd6", "#4fc3d9"];

class PlotChart {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.graph = null;
    this.message = "";
    this.hover = null;
    this.width = 1;
    this.height = 1;
    canvas.addEventListener("pointermove", (e) => {
      if (!this.graph) return;
      const rect = canvas.getBoundingClientRect();
      this.hover = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      this.draw();
    });
    canvas.addEventListener("pointerleave", () => { this.hover = null; this.draw(); });
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

  setGraph(graph, message) {
    this.graph = graph || null;
    this.message = message || "";
    this.hover = null;
    this.draw();
  }

  static fmt(v) {
    if (v === 0) return "0";
    const a = Math.abs(v);
    if (a >= 1e5 || a < 1e-3) return v.toExponential(1);
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toPrecision(2);
  }

  static ticks(lo, hi, n) {
    const span = hi - lo || 1;
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const norm = raw / mag;
    const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-9; t += step) out.push(+t.toPrecision(12));
    return out;
  }

  draw() {
    const ctx = this.ctx, W = this.width, H = this.height;
    ctx.fillStyle = "#141414";
    ctx.fillRect(0, 0, W, H);
    ctx.textAlign = "left";
    if (!this.graph) {
      ctx.fillStyle = "#7d7d7d";
      ctx.font = "12px ui-monospace, Consolas, monospace";
      ctx.fillText(this.message || "No data.", 16, 26);
      return;
    }
    const g = this.graph;
    const pad = { left: 70, right: 18, top: 30, bottom: 44 };
    const plotW = W - pad.left - pad.right, plotH = H - pad.top - pad.bottom;
    if (plotW < 60 || plotH < 40) return;
    const ylog = !!g.ylog;
    const ty = (v) => (ylog ? Math.log10(Math.max(v, 1e-300)) : v);

    // ---- bounds
    let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
    for (const s of g.series) {
      s.x.forEach((x, i) => {
        const y = s.y[i];
        if (!isFinite(x) || !isFinite(y) || (ylog && y <= 0)) return;
        const e = s.yerr ? s.yerr[i] || 0 : 0;
        xMin = Math.min(xMin, x); xMax = Math.max(xMax, x);
        yMin = Math.min(yMin, ty(y - (ylog ? 0 : e))); yMax = Math.max(yMax, ty(y + (ylog ? 0 : e)));
      });
      if (s.kind === "bars") yMin = Math.min(yMin, 0);
    }
    (g.vlines || []).forEach((v) => { xMin = Math.min(xMin, v.x); xMax = Math.max(xMax, v.x); });
    (g.hlines || []).forEach((h) => { yMin = Math.min(yMin, ty(h.y)); yMax = Math.max(yMax, ty(h.y)); });
    if (!isFinite(xMin)) { ctx.fillStyle = "#7d7d7d"; ctx.fillText("Nothing to plot.", 16, 26); return; }
    if (xMax === xMin) { xMax += 1; xMin -= 1; }
    const xm = (xMax - xMin) * 0.04;                    // keep end points off the border
    xMin -= xm; xMax += xm;
    if (yMax === yMin) { yMax += 1; yMin -= 1; }
    const ym = (yMax - yMin) * 0.08;
    yMax += ym; if (yMin !== 0) yMin -= ym;

    const px = (x) => pad.left + ((x - xMin) / (xMax - xMin)) * plotW;
    const py = (y) => pad.top + ((yMax - ty(y)) / (yMax - yMin)) * plotH;

    // ---- grid + axes
    ctx.font = "10.5px ui-monospace, Consolas, monospace";
    ctx.strokeStyle = "#2b2b2b"; ctx.lineWidth = 1;
    ctx.fillStyle = "#7d7d7d";
    ctx.textAlign = "right";
    for (const t of PlotChart.ticks(yMin, yMax, 5)) {
      const y = Math.round(pad.top + ((yMax - t) / (yMax - yMin)) * plotH) + 0.5;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
      ctx.fillText(ylog ? "1e" + t.toFixed(0) : PlotChart.fmt(t), pad.left - 7, y + 3.5);
    }
    ctx.textAlign = "center";
    for (const t of PlotChart.ticks(xMin, xMax, 6)) {
      const x = Math.round(px(t)) + 0.5;
      ctx.strokeStyle = "#232323";
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();
      ctx.fillStyle = "#7d7d7d";
      ctx.fillText(PlotChart.fmt(t), x, H - pad.bottom + 15);
    }
    ctx.fillStyle = "#b9b9b9";
    ctx.font = "11px ui-monospace, Consolas, monospace";
    ctx.fillText(g.x_label, pad.left + plotW / 2, H - 8);
    ctx.save();
    ctx.translate(14, pad.top + plotH / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText(g.y_label, 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
    ctx.fillStyle = "#d2d2d2";
    ctx.font = "12px ui-monospace, Consolas, monospace";
    ctx.fillText(g.title, pad.left, 17);

    ctx.save();
    ctx.beginPath(); ctx.rect(pad.left, pad.top, plotW, plotH); ctx.clip();

    // ---- reference lines
    ctx.font = "10.5px ui-monospace, Consolas, monospace";
    (g.hlines || []).forEach((h, i) => {
      const y = py(h.y);
      ctx.strokeStyle = "#6a6a6a"; ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#9a9a9a"; ctx.textAlign = "right";
      ctx.fillText(h.label, W - pad.right - 6, y - 4 - (i % 2) * 0);
    });
    ctx.textAlign = "left";
    (g.vlines || []).forEach((v, i) => {
      const x = px(v.x);
      ctx.strokeStyle = "#8a7a3a"; ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#c9b45a";
      const label = v.label, w = ctx.measureText(label).width;
      const lx = x + 5 + w > W - pad.right ? x - w - 5 : x + 5;
      ctx.fillText(label, lx, pad.top + plotH - 8 - i * 13);
    });

    // ---- series
    g.series.forEach((s, si) => {
      const color = PLOT_COLORS[si % PLOT_COLORS.length];
      if (s.kind === "bars") {
        let w = Infinity;
        for (let i = 1; i < s.x.length; i++) w = Math.min(w, Math.abs(s.x[i] - s.x[i - 1]));
        const bw = Math.max(1, (isFinite(w) ? w : 1) / (xMax - xMin) * plotW * 0.9);
        ctx.fillStyle = color + "99";
        s.x.forEach((x, i) => {
          const y0 = py(0 || (ylog ? 1e-300 : 0)), y1 = py(s.y[i]);
          ctx.fillRect(px(x) - bw / 2, Math.min(y0, y1), bw, Math.abs(y0 - y1));
        });
        return;
      }
      ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 2; ctx.lineJoin = "round";
      if (s.kind === "line") {
        ctx.setLineDash(s.dash ? [6, 4] : []);
        ctx.beginPath();
        let started = false;
        s.x.forEach((x, i) => {
          if (!isFinite(s.y[i]) || (ylog && s.y[i] <= 0)) return;
          if (!started) { ctx.moveTo(px(x), py(s.y[i])); started = true; } else ctx.lineTo(px(x), py(s.y[i]));
        });
        ctx.stroke();
        ctx.setLineDash([]);
      } else {
        s.x.forEach((x, i) => {
          const y = s.y[i];
          if (!isFinite(y) || (ylog && y <= 0)) return;
          if (s.yerr && s.yerr[i]) {
            ctx.lineWidth = 1.2;
            ctx.beginPath(); ctx.moveTo(px(x), py(y - s.yerr[i])); ctx.lineTo(px(x), py(y + s.yerr[i])); ctx.stroke();
          }
          ctx.beginPath(); ctx.arc(px(x), py(y), 3.6, 0, Math.PI * 2); ctx.fill();
          ctx.strokeStyle = "#141414"; ctx.lineWidth = 1; ctx.stroke(); ctx.strokeStyle = color;
        });
      }
    });
    ctx.restore();

    // ---- legend (named series only)
    ctx.font = "10.5px ui-monospace, Consolas, monospace";
    let ly = pad.top + 8;
    const named = g.series.map((s, i) => ({ s, i })).filter((o) => o.s.label);
    const lw = Math.max(0, ...named.map((o) => ctx.measureText(o.s.label).width)) + 26;
    const lx = W - pad.right - lw - 4;
    named.forEach(({ s, i }) => {
      ctx.fillStyle = "rgba(20,20,20,0.85)"; ctx.fillRect(lx - 4, ly - 9, lw + 6, 15);
      ctx.fillStyle = PLOT_COLORS[i % PLOT_COLORS.length];
      if (s.kind === "line") ctx.fillRect(lx, ly - 1, 14, 2.5); else ctx.fillRect(lx + 2, ly - 4, 8, 8);
      ctx.fillStyle = "#b9b9b9"; ctx.textAlign = "left";
      ctx.fillText(s.label, lx + 20, ly + 3);
      ly += 16;
    });

    // ---- hover readout: nearest x of the first line/point series
    if (this.hover && this.hover.x > pad.left && this.hover.x < W - pad.right) {
      const xv = xMin + ((this.hover.x - pad.left) / plotW) * (xMax - xMin);
      const rows = [];
      g.series.forEach((s, si) => {
        if (s.kind === "bars" || !s.label) return;
        let best = -1, bd = Infinity;
        s.x.forEach((x, i) => { const d = Math.abs(x - xv); if (d < bd) { bd = d; best = i; } });
        if (best >= 0) rows.push({ c: PLOT_COLORS[si % PLOT_COLORS.length], x: s.x[best], y: s.y[best] });
      });
      if (rows.length) {
        const x = Math.round(px(rows[0].x)) + 0.5;
        ctx.strokeStyle = "#5a5a5a"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, pad.top + plotH); ctx.stroke();
        const text = [`x = ${PlotChart.fmt(rows[0].x)}`, ...rows.map((r) => `y = ${PlotChart.fmt(r.y)}`)];
        const bw = 118, bh = text.length * 14 + 8;
        const bx = Math.min(x + 10, W - pad.right - bw - 4), by = pad.top + plotH - bh - 6;
        ctx.fillStyle = "rgba(24,24,24,0.94)"; ctx.fillRect(bx, by, bw, bh);
        ctx.strokeStyle = "#3d3d3d"; ctx.strokeRect(bx + 0.5, by + 0.5, bw, bh);
        ctx.fillStyle = "#d2d2d2"; ctx.textAlign = "left";
        text.forEach((t, k) => {
          if (k > 0) { ctx.fillStyle = rows[k - 1].c; ctx.fillRect(bx + 6, by + 8 + k * 14 - 8, 5, 5); ctx.fillStyle = "#d2d2d2"; }
          ctx.fillText(t, bx + (k > 0 ? 15 : 7), by + 14 + k * 14);
        });
      }
    }
  }
}
