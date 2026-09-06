"""Demo role picker (F2). Not a product screen -- delete it in production."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..repositories import visits
from ..services import tokens
from ..web import templates
from . import ELDER_ID

router = APIRouter(tags=["home"])


@router.get("/")
def home(request: Request):
    latest = visits.latest_scheduled(ELDER_ID)
    return templates.TemplateResponse(request=request, name="home.html",
                                      context={"has_visit": latest is not None})


@router.get("/demo/worker-link")
def worker_link():
    """The raw token is never stored, so the stage shortcut re-issues one for
    the newest scheduled visit. Demo only."""
    latest = visits.latest_scheduled(ELDER_ID)
    if latest is None:
        raise HTTPException(404, "No scheduled visit")
    raw = tokens.issue(latest.id, latest.scheduled_start, latest.scheduled_end)
    return RedirectResponse(f"/v/{raw}", status_code=303)


@router.get("/health", tags=["meta"])
def health():
    return {"ok": True}
