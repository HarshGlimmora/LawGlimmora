"""Auth routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from api.deps import (
    clear_session_cookie, current_user_id, issue_session, optional_user_id,
)
from api.errors import DomainError
from config.settings import SETTINGS
from core.db import Profile, User, session_scope, write_audit
from modules.auth.schemas import LoginIn, SignupIn
from modules.auth.services.auth_service import (
    AuthError, login, login_by_email, logout, signup, user_has_profile,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class DemoLoginIn(BaseModel):
    slug: str  # "anika" | "vikram"


class SessionUser(BaseModel):
    id: int
    email: str
    is_demo: bool
    has_profile: bool


def _hydrate(uid: int, email: str, is_demo: bool) -> SessionUser:
    return SessionUser(id=uid, email=email, is_demo=is_demo,
                       has_profile=user_has_profile(uid))


@router.post("/signup", response_model=SessionUser)
def post_signup(data: SignupIn, response: Response) -> SessionUser:
    try:
        result = signup(data)
    except AuthError as e:
        raise DomainError("auth_failed", str(e), status_code=400)
    issue_session(response, result["id"])
    return _hydrate(result["id"], result["email"], result["is_demo"])


@router.post("/login", response_model=SessionUser)
def post_login(data: LoginIn, response: Response) -> SessionUser:
    try:
        result = login(data)
    except AuthError as e:
        raise DomainError("auth_failed", str(e), status_code=401)
    issue_session(response, result["id"])
    return _hydrate(result["id"], result["email"], result["is_demo"])


@router.post("/demo-login", response_model=SessionUser)
def post_demo_login(data: DemoLoginIn, response: Response) -> SessionUser:
    demo_map = {
        "anika": (SETTINGS.demo_user_1_email, SETTINGS.demo_user_1_password),
        "vikram": (SETTINGS.demo_user_2_email, SETTINGS.demo_user_2_password),
    }
    if data.slug not in demo_map:
        raise DomainError("unknown_demo", f"No demo account: {data.slug!r}.", status_code=404)
    email, pwd = demo_map[data.slug]
    try:
        result = login_by_email(email, pwd)
    except AuthError as e:
        raise DomainError(
            "demo_unavailable",
            f"Demo login failed: {e}. Did the seed run?",
            status_code=503,
        )
    issue_session(response, result["id"])
    return _hydrate(result["id"], result["email"], result["is_demo"])


@router.post("/logout")
def post_logout(response: Response, uid: int | None = Depends(optional_user_id)) -> dict:
    if uid is not None:
        logout(uid)
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=SessionUser)
def get_me(uid: int = Depends(current_user_id)) -> SessionUser:
    with session_scope() as sess:
        user = sess.query(User).filter(User.id == uid).one()
        return _hydrate(user.id, user.email, user.is_demo)
