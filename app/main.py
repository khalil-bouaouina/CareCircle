from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import config, seed
from .db import init_db
from .repositories import accounts, statements, visits
from .routes import auth as auth_routes, caregiver, elder, worker
from .services import auth
from .web import templates


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if config.SEED_ON_STARTUP:
        seed.seed()
    yield


app = FastAPI(title="CareCircle", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(config.REPO_ROOT / "app" / "static")), name="static")

app.include_router(auth_routes.router)
app.include_router(caregiver.router)
app.include_router(elder.router)
app.include_router(worker.router)


@app.get("/", include_in_schema=False)
def home(request: Request):
    cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
    payload = auth.decode_session_token(cookie) if cookie else None
    user = accounts.get_user_by_id(payload["user_id"]) if payload and "user_id" in payload else None
    user_elders = accounts.list_elders_for_user(user.id) if user else []

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "worker_link": None,
            "user": user,
            "user_elders": user_elders,
            "role": payload.get("role") if payload else None,
        },
    )


@app.get("/health", tags=["meta"])
def health():
    return {"ok": True}


@app.post("/reset", tags=["meta"])
def reset():
    """Wipe and reseed. Demo only. Resetting the database is deleting a file."""
    from fastapi import HTTPException

    if not config.ENABLE_DEMO_RESET:
        raise HTTPException(403, "Reset is disabled in production")
    seed.seed(reset=True)
    return {"ok": True, "statements": statements.count_active(1), "visits": visits.count_visits(1)}
