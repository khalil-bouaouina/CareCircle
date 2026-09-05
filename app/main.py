"""FastAPI app (B19). Startup: init_db, then seed if the record is empty."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import config, seed
from .db import init_db
from .repositories import statements, visits
from .routes import caregiver, elder, worker
from .web import templates


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if config.SEED_ON_STARTUP:
        seed.seed()
    yield


app = FastAPI(title="Eldercare", version="0.2.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(config.REPO_ROOT / "app" / "static")), name="static")

app.include_router(caregiver.router)
app.include_router(elder.router)
app.include_router(worker.router)


@app.get("/", include_in_schema=False)
def home(request: Request):
    # Tokens are deliberately unrecoverable, so this demo picker does not
    # manufacture a worker link after the visit-created screen is closed.
    return templates.TemplateResponse(request=request, name="home.html", context={"worker_link": None})


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}


@app.post("/reset", tags=["meta"])
def reset():
    """Wipe and reseed. Demo only. Resetting the database is deleting a file."""
    seed.seed(reset=True)
    return {"ok": True, "statements": statements.count_active(1), "visits": visits.count_visits(1)}
