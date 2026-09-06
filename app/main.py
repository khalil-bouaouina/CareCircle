"""FastAPI app: startup, static, templates, routers (B22)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config, seed
from .db import init_db
from .routes import caregiver, elder, home, worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed.seed()  # guarded: only runs when the record is empty
    yield


app = FastAPI(title="CareCircle", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(config.REPO_ROOT / "app" / "static")), name="static")

app.include_router(home.router)
app.include_router(caregiver.router)
app.include_router(elder.router)
app.include_router(worker.router)
