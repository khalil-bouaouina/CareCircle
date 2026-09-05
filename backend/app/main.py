from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas, seed
from .config import settings
from .db import SessionLocal, get_db, init_db
from .models import ObservationCode, PreferenceStatement, Visit
from .routers import caregiver, elder, worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed.seed_if_empty(db)
    yield


app = FastAPI(title="Eldercare", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(caregiver.router)
app.include_router(elder.router)
app.include_router(worker.router)


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}


@app.get("/observation-codes", response_model=list[schemas.ObservationCodeOut], tags=["meta"])
def observation_codes(db: Session = Depends(get_db)):
    return list(db.scalars(select(ObservationCode).order_by(ObservationCode.category, ObservationCode.code)))


@app.post("/reset", response_model=schemas.ResetResult, tags=["meta"])
def reset(db: Session = Depends(get_db)):
    """Wipe and reseed. Demo only."""
    seed.reset(db)
    return schemas.ResetResult(
        ok=True,
        statements=db.scalar(select(func.count()).select_from(PreferenceStatement)) or 0,
        visits=db.scalar(select(func.count()).select_from(Visit)) or 0,
    )
