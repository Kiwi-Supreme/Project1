// api.js
//
// Every call the frontend makes to the local backend goes through this
// one small file. Keeping them here means app.js never has to know the
// details of URLs or fetch() -- it just calls extractParameters(text),
// validateParameters(params), or runSimulation(params).

const API = {
  async extractParameters(text) {
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("Could not read that description.");
    const data = await res.json();
    // params is what the parser understood; notes is its line-by-line
    // account of how it got there, which the Messages panel prints.
    return { params: data.params, notes: data.notes || [], extras: data.extras || null, questions: data.questions || [] };
  },

  async validateParameters(params) {
    const res = await fetch("/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    const data = await res.json();
    return { valid: res.ok && data.valid, errors: data.errors || [], warnings: data.warnings || [], params: data.params };
  },

  async runSimulation(params) {
    const res = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    const data = await res.json();
    if (!res.ok) {
      const message = (data.errors && data.errors.join(" ")) || data.error || "Simulation failed.";
      throw new Error(message);
    }
    return data; // { params, trajectory, energy, run_seconds, report, properties }
  },

  // virtual experiments: start one, then poll until it is done
  async startSweep(kind, components, temperature) {
    const res = await fetch("/api/sweep", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, components, temperature }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not start the experiment.");
    return data.id;
  },

  async getSweep(id) {
    const res = await fetch("/api/sweep/" + id);
    return res.json();
  },
};
