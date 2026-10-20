"""
app.py

The local web server that ties everything together. It exposes three
small endpoints for the frontend to call:

    POST /api/extract   -- turn a sentence into draft parameters
    POST /api/validate   -- check whether a set of parameters is runnable
    POST /api/simulate   -- validate, run the C++ engine, return real results

...and serves the frontend's static files, so opening one local address
in a browser is the entire app. Everything here runs on this machine --
no request ever leaves it.

Run with:  uvicorn backend.app:app --reload
"""

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import sweeps
from backend.agent.orchestrator import interpret
from backend.engine.plan import make_plan
from backend.knowledge.checks import domain_check
from backend.validation.schema import validate_params
from backend.engine.runner import run_simulation, EngineRunError

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

app = FastAPI(title="MD Simulation Prototype")


class ExtractRequest(BaseModel):
    text: str


class SimulateRequest(BaseModel):
    # Every field is optional here on purpose: the frontend sends whatever
    # the user has set (from the manual form, from extraction, or a mix),
    # and validate_params() below fills in the rest from defaults.
    model: str | None = None
    state: str | None = None
    container_enabled: bool | None = None
    container_shape: str | None = None
    particle_count: int | None = None
    container_size: float | None = None
    density: float | None = None
    temperature: float | None = None
    particle_speed: float | None = None
    timestep: float | None = None
    total_time: float | None = None
    epsilon: float | None = None
    sigma: float | None = None
    cutoff: float | None = None
    seed: int | None = None
    # chemistry carried over from the description (see agent/orchestrator.py):
    components: list[dict] | None = None
    reactive: bool | None = None


def _non_null_dict(model: BaseModel) -> dict:
    """Drops any field the caller left as None, so SimParams' own
    defaults apply instead of overwriting them with None."""
    return {k: v for k, v in model.model_dump().items() if v is not None}


@app.post("/api/extract")
def extract(request: ExtractRequest):
    """Step 1 of the natural-language path: read the sentence, identify the
    substances, look their properties up in the chemical knowledge base and
    return draft parameters, a line-by-line account of how it was read, the
    chemistry (`extras`) the interface sends back with later requests, and any
    `questions` the user must answer first. Nothing is run yet."""
    result = interpret(request.text)
    return {"params": result["params"], "notes": result["notes"], "extras": result["extras"],
            "questions": result["questions"]}


def _check(request: SimulateRequest):
    """Range checks, then domain checks against the chemical knowledge base.
    Returns (params, plan, errors, warnings)."""
    params, errors = validate_params(_non_null_dict(request))
    if errors:
        return None, None, errors, []
    plan = make_plan(params)
    errors, warnings = domain_check(plan)
    return params, plan, errors, warnings


@app.post("/api/validate")
def validate(request: SimulateRequest):
    """Checks a set of parameters without running anything. Used by the
    Review step to show a green/red status before the user commits to
    running the simulation."""
    params, plan, errors, warnings = _check(request)
    if errors:
        return JSONResponse(status_code=400, content={"valid": False, "errors": errors, "warnings": warnings})
    return {"valid": True, "params": params.model_dump(), "warnings": warnings}


@app.post("/api/simulate")
def simulate(request: SimulateRequest):
    """The real thing: validate, run the molecular-dynamics engine, return the
    actual trajectory and energy data for the frontend to play back, plus the
    measured quantities and the scientific explanation (`report`)."""
    params, plan, errors, warnings = _check(request)
    if errors:
        return JSONResponse(status_code=400, content={"valid": False, "errors": errors})

    try:
        result = run_simulation(params)
    except EngineRunError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return {
        "params": params.model_dump(),
        "trajectory": result["trajectory"],
        "energy": result["energy"],
        "run_seconds": result["run_seconds"],
        "report": result["report"],
        "properties": result["properties"],
        "graphs": result.get("graphs", {}),
    }


class SweepRequest(BaseModel):
    kind: str
    components: list[dict] | None = None
    temperature: float = 1.0          # reduced temperature T* of the current setup


@app.post("/api/sweep")
def sweep_start(request: SweepRequest):
    """Start a 'virtual experiment' (several simulations varying one quantity) in the background."""
    try:
        jid = sweeps.start(request.kind, request.components, request.temperature)
    except sweeps.SweepError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return {"id": jid}


@app.get("/api/sweep/{jid}")
def sweep_status(jid: str):
    job = sweeps.get(jid)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "unknown experiment id"})
    return {k: job[k] for k in ("id", "kind", "status", "done", "total", "graphs", "error", "substance")}


# --- serve the frontend itself ---
# Mounted LAST and at "/" so the /api/* routes above are matched first;
# html=True means a request for "/" automatically serves index.html, and
# "css/style.css" / "js/app.js" resolve exactly the way index.html links them.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
