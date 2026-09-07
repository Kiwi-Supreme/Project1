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

from backend.nlp.extractor import extract_with_notes
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


def _non_null_dict(model: BaseModel) -> dict:
    """Drops any field the caller left as None, so SimParams' own
    defaults apply instead of overwriting them with None."""
    return {k: v for k, v in model.model_dump().items() if v is not None}


@app.post("/api/extract")
def extract(request: ExtractRequest):
    """Step 1 of the natural-language path: read the sentence, return
    draft parameters plus a line-by-line note of how it was read. Nothing
    is validated yet -- that happens when the caller sends the parameters
    on to /api/validate or /api/simulate."""
    params, notes = extract_with_notes(request.text)
    return {"params": params, "notes": notes}


@app.post("/api/validate")
def validate(request: SimulateRequest):
    """Checks a set of parameters without running anything. Used by the
    Review step to show a green/red status before the user commits to
    running the simulation."""
    params, errors = validate_params(_non_null_dict(request))
    if errors:
        return JSONResponse(status_code=400, content={"valid": False, "errors": errors})
    return {"valid": True, "params": params.model_dump()}


@app.post("/api/simulate")
def simulate(request: SimulateRequest):
    """The real thing: validate, run the C++ engine, return the actual
    trajectory and energy data for the frontend to play back."""
    params, errors = validate_params(_non_null_dict(request))
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
    }


# --- serve the frontend itself ---
# Mounted LAST and at "/" so the /api/* routes above are matched first;
# html=True means a request for "/" automatically serves index.html, and
# "css/style.css" / "js/app.js" resolve exactly the way index.html links them.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
