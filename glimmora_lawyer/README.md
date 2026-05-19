# Glimmora Lawyer — Backend

FastAPI shim over the modular service layer. The UI lives in [`../frontend/`](../frontend) (Next.js).

## Run locally

```bash
cd glimmora_lawyer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # tweak the values you care about
python -m core.db                      # ensures tables + seeds demo users (dev only)
uvicorn api.main:app --reload --port 8000
```

API at `http://localhost:8000` · OpenAPI docs at `http://localhost:8000/docs` · Health at `http://localhost:8000/api/health`.

## Run in production (Render)

The repo root ships a `render.yaml` blueprint that provisions:

- the web service (this app) with `uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2`
- a managed Postgres database (`DATABASE_URL` injected automatically)
- a 5 GB persistent disk mounted at `/var/data` for evidence/research files

Manual steps after first deploy (env vars marked `sync: false` in the blueprint):

1. **`GLIMMORA_SECRET_KEY`** — `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. **`ALLOWED_ORIGINS`** — comma-separated Vercel URLs, no trailing slash, e.g. `https://glimmora.vercel.app,https://staging.glimmora.app`
3. **Gemini auth** — either `USE_VERTEX_AI=true` + base64 SA JSON in `GCP_PROJECT`, **or** `GEMINI_API_KEY` from AI Studio. The regex fallback runs deterministically if neither is set.

Health check at `https://<service>.onrender.com/api/health` should respond `{"ok": true, "env": "production", ...}`.

Alternative startup commands (no blueprint):

- `Procfile`: `web: cd glimmora_lawyer && uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2`
- `start.sh` wrapper: `cd glimmora_lawyer && ./start.sh`

## Demo accounts (dev only)

Seeded by `python -m core.db`. The frontend exposes one-click sign-in buttons. Production keeps `SEED_DEMO_USERS=false`.

- **Anika Rao** — commercial litigation, Bombay HC, pre-loaded case.
- **Vikram Shastri** — constitutional & writ matters, Bombay HC, pre-loaded case.

## Layout

```
glimmora_lawyer/
  api/                  FastAPI shim — main + deps + errors + routers/*
  config/               settings (env-driven) + UI constants
  core/                 db (SQLAlchemy), security (bcrypt), logging (loguru)
  modules/
    auth/  profile/  case/                       schemas + services
    evidence_vault/                              schemas + services + utils
    research_engine/                             schemas + services + utils
  tests/research_engine/                         pytest suite (unit-level)
  .env.example                                   committed template
  start.sh                                       prod startup wrapper
  requirements.txt
```

`modules/*/services/*` is the source of truth. `api/routers/*` is a thin translation layer that wraps each service unchanged.

## Configuration surface

Every env var the backend reads is documented in [`.env.example`](.env.example). The big ones:

| Var | Default | Render setting |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `DATA_ROOT` | `./data` | `/var/data` |
| `CASES_ROOT` | `./cases` | `/var/data/cases` |
| `DATABASE_URL` | `sqlite:///app.db` (anchored to `DATA_ROOT`) | Postgres URL injected by Render |
| `ALLOWED_ORIGINS` | `localhost:3000` | your Vercel origins (CSV) |
| `COOKIE_SECURE` / `COOKIE_SAMESITE` | `false` / `lax` | `true` / `none` |
| `GLIMMORA_SECRET_KEY` | dev-only sentinel | regenerated per deploy |
| `SEED_DEMO_USERS` | `true` in dev | `false` |
| `GEMINI_MODEL_*` | per-stage flash/pro split | override per stage if needed |

## Rules

- API never touches the DB directly — routers call services.
- Every service mutation writes an audit row + a structured log line.
- Every read filters by `user_id`. Per-case files live under `<CASES_ROOT>/<case_id>/`.
- Pydantic models from `modules/**/schemas` are the wire format — the frontend mirrors them in `frontend/src/types/`.
- In production, the app refuses to boot with insecure defaults (dev secret, empty CORS, `samesite=none` without `secure`).
