"""Runtime settings loaded from environment + .env.

This module is the single source of truth for every path, host, port,
credential, and feature flag the backend reads. Anything that needs to
behave differently on Render vs. local goes through `SETTINGS` rather
than being hard-coded.

Two roots:
  * DATA_ROOT  — persistent disk for app.db (SQLite case), logs, seed files
  * CASES_ROOT — persistent disk for per-case evidence + research files

On Render, attach a disk and set both to /var/data (or DATA_ROOT=/var/data
+ CASES_ROOT=/var/data/cases). Locally they default under the repo so the
dev experience is unchanged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Repo root for the Python backend — used only as a fallback anchor for
# relative paths when DATA_ROOT / CASES_ROOT are not set explicitly.
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_DEV_SECRET = "dev-only-secret-change-me"


# ---------- helpers ----------

def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _resolve(p: str, *, anchor: Path = ROOT) -> Path:
    """Return an absolute Path. Relative inputs are anchored to `anchor`."""
    path = Path(p).expanduser()
    return path if path.is_absolute() else anchor / path


def _csv_list(name: str, default: str = "") -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _is_dev(app_env: str) -> bool:
    return (app_env or "").strip().lower() in {"development", "dev", "local"}


# ---------- dataclass ----------

@dataclass(frozen=True)
class Settings:
    # Identity
    app_name: str
    app_env: str            # "development" | "production" | "staging" | "test"

    # Database
    database_url: str

    # Logging
    log_level: str
    log_file: Optional[Path]   # None disables the file sink (Render captures stdout)

    # Demo accounts
    seed_demo_users: bool
    demo_user_1_email: str
    demo_user_1_password: str
    demo_user_2_email: str
    demo_user_2_password: str

    # Filesystem roots
    root_dir: Path             # repo root (where settings.py lives)
    data_root: Path            # holds app.db (SQLite case), logs, seeds
    cases_root: Path           # holds per-case evidence + research files
    uploads_dir: Path          # `<data_root>/uploads`  (reserved)
    outputs_dir: Path          # `<data_root>/outputs`  (reserved)
    seeds_dir: Path            # `<data_root>/seeds`    (reserved)
    logs_dir: Path             # `<data_root>/logs`

    # HTTP / auth
    session_secret: str
    allowed_origins: List[str]
    cookie_secure: bool
    cookie_samesite: str       # "lax" | "none" | "strict"

    # Derived
    @property
    def is_dev(self) -> bool:
        return _is_dev(self.app_env)

    @property
    def is_prod(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}


def _build_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip()
    dev = _is_dev(app_env)

    # Filesystem roots. Defaults keep dev unchanged; Render points both at
    # the persistent disk via env.
    data_root = _resolve(os.getenv("DATA_ROOT", "data"))
    cases_root = _resolve(os.getenv("CASES_ROOT", "cases"))

    # Log file sink: in dev, write to <data_root>/logs/app.log. In prod, omit
    # the file sink entirely so we rely on Render's captured stdout/stderr —
    # unless LOG_FILE is explicitly set.
    log_file_env = os.getenv("LOG_FILE")
    if log_file_env:
        log_file: Optional[Path] = _resolve(log_file_env, anchor=data_root)
    elif dev:
        log_file = data_root / "logs" / "app.log"
    else:
        log_file = None

    # Cookie attributes. Cross-site cookies (Vercel ↔ Render) require
    # samesite=none + secure=True. Local dev sticks with lax + insecure.
    samesite_default = "lax" if dev else "none"
    secure_default = "false" if dev else "true"
    cookie_samesite = (os.getenv("COOKIE_SAMESITE") or samesite_default).lower()
    cookie_secure = _bool("COOKIE_SECURE", default=(secure_default == "true"))

    # CORS allow-list. Local dev defaults to the Next.js dev URLs; prod must
    # explicitly enumerate origins (Vercel preview + production domains).
    allowed_origins = _csv_list(
        "ALLOWED_ORIGINS",
        default="http://localhost:3000,http://127.0.0.1:3000" if dev else "",
    )

    return Settings(
        app_name=os.getenv("APP_NAME", "Glimmora Lawyer"),
        app_env=app_env,
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/app.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=log_file,
        seed_demo_users=_bool("SEED_DEMO_USERS", default=dev),
        demo_user_1_email=os.getenv("DEMO_USER_1_EMAIL", "anika.rao@demo.glimmora.law"),
        demo_user_1_password=os.getenv("DEMO_USER_1_PASSWORD", "demo-anika-2026"),
        demo_user_2_email=os.getenv("DEMO_USER_2_EMAIL", "vikram.shastri@demo.glimmora.law"),
        demo_user_2_password=os.getenv("DEMO_USER_2_PASSWORD", "demo-vikram-2026"),
        root_dir=ROOT,
        data_root=data_root,
        cases_root=cases_root,
        uploads_dir=data_root / "uploads",
        outputs_dir=data_root / "outputs",
        seeds_dir=data_root / "seeds",
        logs_dir=data_root / "logs",
        session_secret=os.getenv("GLIMMORA_SECRET_KEY", _DEV_SECRET),
        allowed_origins=allowed_origins,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
    )


SETTINGS = _build_settings()


def resolved_database_url() -> str:
    """Normalise the URL so SQLAlchemy 2.x picks up the right driver and
    so relative SQLite paths land inside DATA_ROOT (which is the persistent
    disk on Render). Handles three shapes:

      * `postgres://...`                  → `postgresql+psycopg://...`   (Render's default scheme is rejected by SQLAlchemy 2)
      * `postgresql://...`  (no driver)   → `postgresql+psycopg://...`   (pick a concrete driver)
      * `sqlite:///relative/path`         → `sqlite:////<data_root>/relative/path`
    """
    url = SETTINGS.database_url

    # Postgres scheme normalisation.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        scheme, _, rest = url.partition("://")
        if "+" not in scheme:
            url = "postgresql+psycopg://" + rest

    # Relative SQLite path → anchor to DATA_ROOT.
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url.replace("sqlite:///", "", 1)
        target = _resolve(rel, anchor=SETTINGS.data_root)
        return f"sqlite:///{target.as_posix()}"

    return url


def production_safety_checks() -> None:
    """Refuse to boot in production with insecure defaults.

    Hard aborts on:
      * `GLIMMORA_SECRET_KEY` left at the dev default
      * `ALLOWED_ORIGINS` empty (would block every CORS preflight)
      * `COOKIE_SAMESITE=none` paired with `COOKIE_SECURE=false`
        (the browser drops the cookie silently — fails authn in production)

    Render will surface the resulting `RuntimeError` in the deploy logs and
    auto-restart the service, making the misconfiguration immediately visible.
    """
    if not SETTINGS.is_prod:
        return
    problems: List[str] = []
    if SETTINGS.session_secret == _DEV_SECRET:
        problems.append("GLIMMORA_SECRET_KEY is still the dev default")
    if not SETTINGS.allowed_origins:
        problems.append("ALLOWED_ORIGINS is empty — every CORS request will fail")
    if SETTINGS.cookie_samesite == "none" and not SETTINGS.cookie_secure:
        problems.append("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
    if problems:
        bullets = "\n  - ".join(problems)
        raise RuntimeError(
            "Refusing to start in production with insecure configuration:\n  - "
            + bullets
        )
