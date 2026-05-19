"""Uniform error envelope: {error: {code, message, details?}}."""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class DomainError(Exception):
    """Service-layer exception mapped to a 4xx response."""

    def __init__(self, code: str, message: str, status_code: int = 400,
                 details: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _envelope(code: str, message: str, details: Any | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.details),
    )


def validation_error_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_envelope("validation_error", "Invalid request body.",
                          [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                           for e in exc.errors()]),
    )
