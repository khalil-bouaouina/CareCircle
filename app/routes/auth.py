"""Authentication and account onboarding routes (B18 / Auth)."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import config
from ..repositories import accounts, people
from ..services import auth
from ..web import templates

router = APIRouter(tags=["auth"])


@router.get("/login")
def login_page(request: Request, next: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"next": next, "error": None},
    )


@router.post("/login")
def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default=""),
):
    user = auth.authenticate_user(email, password)
    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"next": next, "error": "Email ou mot de passe incorrect.", "email": email},
            status_code=400,
        )

    user_elders = accounts.list_elders_for_user(user.id)
    active_elder_id = user_elders[0][0].id if user_elders else None
    user_role = user_elders[0][1].role if user_elders else "primary_caregiver"

    token = auth.create_session_token({
        "user_id": user.id,
        "active_elder_id": active_elder_id,
        "role": user_role,
    })

    redirect_url = next if next and next.startswith("/") else ("/elder" if user_role == "elder" else "/caregiver/record")
    resp = RedirectResponse(redirect_url, status_code=303)
    resp.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,  # 30 days
    )
    return resp


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"error": None, "capacity_modes": config.CAPACITY_MODES},
    )


@router.post("/register")
def register(
    request: Request,
    account_type: str = Form(default="caregiver"),
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    elder_name: str | None = Form(default=None),
    capacity_mode: str = Form(default="assisted"),
    language: str = Form(default="fr"),
):
    try:
        if account_type == "elder":
            user, elder = auth.register_elder(
                name=name,
                email=email,
                password=password,
                capacity_mode=capacity_mode,
                language=language,
            )
            user_role = "elder"
            redirect_url = "/elder"
        else:
            if not elder_name or not elder_name.strip():
                raise ValueError("Le nom de la personne aidée est obligatoire")
            user, elder = auth.register_caregiver(
                name=name,
                email=email,
                password=password,
                elder_name=elder_name,
                capacity_mode=capacity_mode,
                language=language,
            )
            user_role = "primary_caregiver"
            redirect_url = "/caregiver/record"
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": str(exc),
                "account_type": account_type,
                "name": name,
                "email": email,
                "elder_name": elder_name,
                "capacity_modes": config.CAPACITY_MODES,
            },
            status_code=400,
        )

    token = auth.create_session_token({
        "user_id": user.id,
        "active_elder_id": elder.id if elder else None,
        "role": user_role,
    })

    resp = RedirectResponse(redirect_url, status_code=303)
    resp.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,

        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
    )
    return resp


@router.get("/logout")
@router.post("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(config.SESSION_COOKIE_NAME)
    return resp


@router.post("/switch-elder/{elder_id}")
def switch_elder(elder_id: int, request: Request):
    cookie = request.cookies.get(config.SESSION_COOKIE_NAME)
    payload = auth.decode_session_token(cookie) if cookie else None
    if not payload:
        return RedirectResponse("/login", status_code=303)

    user_id = payload.get("user_id")
    link = accounts.get_user_elder_link(user_id, elder_id) if user_id else None
    if link is None:
        raise HTTPException(403, "Vous n'avez pas accès à ce dossier")

    payload["active_elder_id"] = elder_id
    payload["role"] = link.role
    token = auth.create_session_token(payload)

    referer = request.headers.get("referer") or "/caregiver/record"
    resp = RedirectResponse(referer, status_code=303)
    resp.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 30,
    )
    return resp

