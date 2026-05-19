"""Profile service: create / update / fetch profile."""
from __future__ import annotations

from typing import Optional

from core.db import Profile, User, session_scope, write_audit
from core.logging import get_logger
from modules.profile.schemas import ProfileIn

log = get_logger("profile.service")


class ProfileError(Exception):
    pass


def _to_dict(p: Profile) -> dict:
    return {
        "id": p.id, "user_id": p.user_id, "full_name": p.full_name,
        "display_name": p.display_name, "firm_name": p.firm_name, "role": p.role,
        "practice_area": p.practice_area, "years_of_experience": p.years_of_experience,
        "jurisdiction_focus": p.jurisdiction_focus, "city": p.city,
        "preferred_languages": p.preferred_languages,
        "bar_registration_id": p.bar_registration_id, "phone": p.phone,
        "default_workspace_theme": p.default_workspace_theme,
    }


def get_profile(user_id: int) -> Optional[dict]:
    with session_scope() as sess:
        p = sess.query(Profile).filter(Profile.user_id == user_id).one_or_none()
        return _to_dict(p) if p else None


def upsert_profile(user_id: int, data: ProfileIn) -> dict:
    languages_csv = ", ".join(data.preferred_languages)
    with session_scope() as sess:
        user = sess.query(User).filter(User.id == user_id).one_or_none()
        if not user:
            raise ProfileError("User not found.")
        if data.email.lower().strip() != user.email:
            user.email = data.email.lower().strip()

        p = sess.query(Profile).filter(Profile.user_id == user_id).one_or_none()
        is_new = p is None
        if is_new:
            p = Profile(user_id=user_id, role="lawyer")
            sess.add(p)

        p.full_name = data.full_name.strip()
        p.display_name = data.display_name.strip()
        p.firm_name = data.firm_name.strip()
        p.practice_area = data.practice_area
        p.years_of_experience = data.years_of_experience
        p.jurisdiction_focus = data.jurisdiction_focus
        p.city = data.city.strip()
        p.preferred_languages = languages_csv
        p.bar_registration_id = (data.bar_registration_id or "").strip() or None
        p.phone = (data.phone or "").strip() or None
        p.default_workspace_theme = data.default_workspace_theme

        sess.flush()
        action = "profile.create" if is_new else "profile.update"
        write_audit(sess, user_id=user_id, action=action, target_type="profile", target_id=p.id,
                    message=f"{p.full_name} ({p.firm_name})")
        log.info("{}: user_id={} profile_id={}", action, user_id, p.id)
        return _to_dict(p)
