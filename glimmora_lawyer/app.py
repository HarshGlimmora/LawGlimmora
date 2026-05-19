"""Top-level compatibility shim.

Render (and several other hosts) default to `uvicorn app:app` when no
explicit start command is set. The real app lives at `api.main:app`,
so this module re-exports it under the `app` name.

For explicit deploys (render.yaml, Procfile, start.sh) keep using
`uvicorn api.main:app` — the import path stays unambiguous and the
shim is just a safety net.
"""
from api.main import app

__all__ = ["app"]
