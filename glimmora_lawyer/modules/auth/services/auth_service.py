"""Auth service: signup, login, logout."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.db import Profile, User, session_scope, write_audit
from core.logging import get_logger
from core.security import hash_password, verify_password
from modules.auth.schemas import LoginIn, SignupIn

log = get_logger("auth.service")


class AuthError(Exception):
    """Domain error surfaced to the UI."""


def signup(data: SignupIn) -> dict:
    email = data.email.lower().strip()
    with session_scope() as sess:
        if sess.query(User).filter(User.email == email).first():
            raise AuthError("An account with this email already exists.")
        user = User(email=email, password_hash=hash_password(data.password), is_demo=False)
        sess.add(user)
        sess.flush()
        write_audit(sess, user_id=user.id, action="auth.signup", target_type="user", target_id=user.id,
                    message=f"New signup: {email}")
        log.info("Signup: {}", email)
        return {"id": user.id, "email": user.email, "is_demo": user.is_demo}


def login(data: LoginIn) -> dict:
    email = data.email.lower().strip()
    with session_scope() as sess:
        user = sess.query(User).filter(User.email == email).one_or_none()
        if not user or not verify_password(data.password, user.password_hash):
            log.warning("Failed login attempt: {}", email)
            raise AuthError("Invalid email or password.")
        user.last_login_at = datetime.utcnow()
        write_audit(sess, user_id=user.id, action="auth.login", target_type="user", target_id=user.id,
                    message=f"Login: {email}")
        log.info("Login: {}", email)
        return {"id": user.id, "email": user.email, "is_demo": user.is_demo}


def login_by_email(email: str, password: str) -> dict:
    return login(LoginIn(email=email, password=password))


def logout(user_id: int) -> None:
    with session_scope() as sess:
        write_audit(sess, user_id=user_id, action="auth.logout", target_type="user", target_id=user_id,
                    message="Logout")
    log.info("Logout: user_id={}", user_id)


def user_has_profile(user_id: int) -> bool:
    with session_scope() as sess:
        return sess.query(Profile).filter(Profile.user_id == user_id).first() is not None
