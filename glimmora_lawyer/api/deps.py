"""Session cookie + current_user dependency.

We sign a small payload {uid: int} with `itsdangerous` and store it as an
HTTP-only cookie. The cookie attributes (`secure`, `samesite`) come from
config so the same code base works for local dev (lax + insecure) and
cross-origin production (none + secure, required for Render ↔ Vercel).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, Response
from itsdangerous import BadSignature, URLSafeSerializer

from api.errors import DomainError
from config.settings import SETTINGS
from core.db import Profile, User, session_scope

COOKIE_NAME = "glimmora_session"
_SERIALIZER = URLSafeSerializer(SETTINGS.session_secret, salt="glimmora.session.v1")


def issue_session(response: Response, user_id: int) -> None:
    token = _SERIALIZER.dumps({"uid": user_id})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=SETTINGS.cookie_samesite,
        secure=SETTINGS.cookie_secure,
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def _decode(token: str) -> Optional[int]:
    try:
        data = _SERIALIZER.loads(token)
        uid = int(data.get("uid"))
        return uid
    except (BadSignature, ValueError, TypeError):
        return None


def current_user_id(
    glimmora_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> int:
    if not glimmora_session:
        raise DomainError("unauthenticated", "Not signed in.", status_code=401)
    uid = _decode(glimmora_session)
    if uid is None:
        raise DomainError("unauthenticated", "Session token invalid or expired.", status_code=401)
    with session_scope() as sess:
        user = sess.query(User).filter(User.id == uid).one_or_none()
        if not user:
            raise DomainError("unauthenticated", "User no longer exists.", status_code=401)
    return uid


def optional_user_id(
    glimmora_session: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
) -> Optional[int]:
    if not glimmora_session:
        return None
    return _decode(glimmora_session)


def require_profile(uid: int = Depends(current_user_id)) -> int:
    with session_scope() as sess:
        prof = sess.query(Profile).filter(Profile.user_id == uid).one_or_none()
        if not prof:
            raise DomainError("profile_required",
                              "Complete your counsel profile first.",
                              status_code=409)
    return uid
