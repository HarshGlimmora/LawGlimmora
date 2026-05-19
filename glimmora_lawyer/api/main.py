"""FastAPI entrypoint.

Local dev:
    uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

Render (production) — uses the env-supplied port and binds to all
interfaces. See render.yaml or Procfile at the repo root:
    uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from api.errors import DomainError, domain_error_handler, validation_error_handler
from api.routers import auth, cases, chat, constants, evidence, profile, report, research
from config.settings import SETTINGS, production_safety_checks
from core.db import init_db, seed_demo_users
from core.logging import configure_logging, get_logger

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Refuse to boot in production with insecure defaults (dev secret,
    # empty CORS, samesite=none without secure). Render surfaces the
    # resulting RuntimeError in the deploy logs.
    production_safety_checks()
    init_db()
    seed_demo_users()
    log.info(
        "API ready (env={} origins={} cookie={}/secure={})",
        SETTINGS.app_env,
        SETTINGS.allowed_origins or "[]",
        SETTINGS.cookie_samesite,
        SETTINGS.cookie_secure,
    )
    yield


app = FastAPI(
    title=f"{SETTINGS.app_name} API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS must be explicit (allow_credentials=True forbids "*"). The allowed
# origins list comes from ALLOWED_ORIGINS (CSV). Set it on Render to the
# Vercel production URL plus any preview domains you care about.
app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "env": SETTINGS.app_env, "app": SETTINGS.app_name}


@app.get("/api/health/llm")
def health_llm(probe: bool = False) -> dict:
    """LLM availability snapshot.

    By default returns the cached state (cheap, no network). When called
    with `?probe=true`, attempts a tiny generate_content call to refresh
    the breaker state — useful right after rotating credentials to
    confirm Vertex is happy again. The probe also trips the breaker on
    failure, so a single probe call replaces the discovery-via-first-
    research-query flow.
    """
    from modules.evidence_vault.services.ai_extractor import (
        gemini_model, get_gemini_client, llm_status, looks_like_auth_error,
        mark_vertex_failed,
    )
    info = llm_status()
    if probe:
        client, kind = get_gemini_client()
        info["client_kind"] = kind
        if client is None:
            info["probe"] = {"ok": False,
                             "reason": info.get("auth_failed_reason")
                                       or "no_client"}
        else:
            try:
                from google.genai import types  # type: ignore
                resp = client.models.generate_content(
                    model=gemini_model(),
                    contents=["Reply with the single word OK."],
                    config=types.GenerateContentConfig(temperature=0.0),
                )
                info["probe"] = {
                    "ok": True,
                    "model": gemini_model(),
                    "echo": (getattr(resp, "text", "") or "").strip()[:40],
                }
            except Exception as exc:
                if looks_like_auth_error(exc):
                    mark_vertex_failed(str(exc))
                info["probe"] = {"ok": False, "reason": str(exc)[:300]}
        # Re-snapshot so auth_failed / auth_failed_reason reflect any
        # state change the probe just caused.
        info.update(llm_status())
    return info


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(cases.router)
app.include_router(constants.router)
app.include_router(evidence.router)
app.include_router(chat.router)
app.include_router(report.router)
app.include_router(research.router)
