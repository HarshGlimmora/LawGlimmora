# Glimmora Lawyer — Frontend

Next.js 14 (App Router) workspace UI for the Glimmora Lawyer legal-AI platform.
The backend lives in [`../glimmora_lawyer/`](../glimmora_lawyer) (Python + FastAPI).

## Run locally

Two terminals.

**Terminal 1 — backend** (from `../glimmora_lawyer`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m core.db                 # creates tables + seeds two demo lawyers
uvicorn api.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from this folder):

```bash
pnpm install   # or npm / yarn
cp .env.local.example .env.local  # already created if missing
pnpm dev
```

Open `http://localhost:3000`. Hit **Sign in as Anika** or **Sign in as Vikram** on the landing page for a one-tap demo.

## Environment

| Var | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` (dev fallback) | FastAPI base. Requests are sent with `credentials: include`. **Required for production.** |

## Deploy on Vercel

See [`VERCEL_DEPLOYMENT.md`](./VERCEL_DEPLOYMENT.md) for the full checklist. TL;DR:

1. Import the repo into Vercel and set **Root Directory = `frontend/`**.
2. Set `NEXT_PUBLIC_API_BASE_URL` to your HTTPS backend origin.
3. Ensure the backend sets the session cookie with `SameSite=None; Secure` if it lives on a different origin from the frontend.
4. Build settings are auto-detected (`npm run build`, Node 20.x). `vercel.json` adds security headers.

## Tech stack

- Next.js 14 App Router · React 18 · TypeScript (strict, `noUncheckedIndexedAccess`)
- Tailwind CSS 3 + custom design tokens (parchment palette, Fraunces + IBM Plex)
- shadcn-style primitives over Radix (Button, Input, Tabs, Select, Dialog…) in `src/components/ui/`
- React Hook Form + Zod for forms (validation mirrors backend Pydantic)
- TanStack Query v5 for server state
- Axios for HTTP (cookie-based session)
- `react-dropzone`, `lucide-react`, `date-fns`

## Architecture

```
frontend/
├── src/
│   ├── app/                     ← App Router pages
│   │   ├── layout.tsx              global shell · grain · providers
│   │   ├── page.tsx                root redirect (cookie-aware)
│   │   ├── (auth)/                 login · signup · profile-setup
│   │   └── (workspace)/            authenticated shell · sidebar
│   │       ├── dashboard/
│   │       └── cases/
│   │           ├── new/
│   │           └── [caseId]/       overview · evidence · research · simulator · copilot · report
│   ├── features/                ← page-level feature folders
│   │   ├── auth/   profile/   case/   evidence/   placeholders/
│   ├── components/
│   │   ├── ui/                    Radix-backed primitives (shadcn pattern)
│   │   ├── layout/                Brandbar, Sidebar, PageHeader, Brandmark
│   │   ├── cards/                 StatCard, CaseCard, PackageCard
│   │   ├── atoms/                 Eyebrow, Ornament, Grain
│   │   └── feedback/              Spinner, ErrorState, EmptyState
│   ├── lib/
│   │   ├── api/                   client.ts · endpoints.ts · query-keys.ts
│   │   ├── validation/            Zod schemas mirroring Pydantic
│   │   ├── query/provider.tsx     TanStack Query setup
│   │   ├── logger.ts              tagged client logger (dev-only by default)
│   │   ├── format.ts              date / bytes / time helpers
│   │   └── utils.ts               cn(), initials(), languagesToArray()
│   ├── hooks/                   useSession, useConstants
│   ├── types/api.ts             wire types — mirror Pydantic models
│   └── styles/globals.css       Tailwind + design tokens
├── tailwind.config.ts
├── tsconfig.json
├── next.config.mjs
└── package.json
```

### Design principles
1. **API layer is the only place HTTP lives** (`src/lib/api/endpoints.ts`).
2. **UI never imports Axios.** Every call is wrapped in `*Endpoints`.
3. **Every form** uses React Hook Form + Zod; Zod schemas mirror Pydantic (`src/lib/validation/`).
4. **Every page** must handle loading, error, empty, and success states.
5. **Every package** owns its own folder under `src/app/(workspace)/cases/[caseId]/<pkg>/` and `src/features/<pkg>/`.
6. **No emoji**, no purple gradients, no generic admin-dashboard look. Refined editorial aesthetic with parchment + serif accents.

## Frontend ↔ backend contract

Mapped 1:1 to the FastAPI routes in `../glimmora_lawyer/api/routers/`:

| Backend route | Frontend wrapper |
| --- | --- |
| `POST /api/auth/login` | `authEndpoints.login()` |
| `POST /api/auth/demo-login` | `authEndpoints.demoLogin("anika" \| "vikram")` |
| `GET /api/auth/me` | `authEndpoints.me()` |
| `GET /api/constants` | `constantsEndpoint()` |
| `GET / PUT /api/profile` | `profileEndpoints.get / save` |
| `GET / POST / PUT /api/cases[/:id]` | `caseEndpoints.list / get / create / update` |
| `POST /api/cases/:id/evidence/upload` (multipart) | `evidenceEndpoints.upload` |
| `GET /api/cases/:id/evidence/documents` | `evidenceEndpoints.listDocuments` |
| `POST /api/cases/:id/evidence/chat` | `chatEndpoints.ask` |
| `GET / DELETE /api/cases/:id/evidence/chat` | `chatEndpoints.history / clear` |

Session is a signed cookie issued by `../glimmora_lawyer/api/deps.py` via `itsdangerous`. The axios client sets `withCredentials: true`, so logout requires `POST /api/auth/logout`.

## Status

| Surface | State |
| --- | --- |
| Landing, login, signup, demo-login | ✅ live |
| Profile setup | ✅ live |
| Cases dashboard, create, detail | ✅ live |
| Evidence Vault — all 7 tabs | ✅ live |
| Research & Precedent Engine — all 6 tabs | ✅ live |
| Final Case Intelligence Report — wired into Evidence Vault "Final analysis" tab | ✅ live |
| Case Study Simulator | 🟡 polished placeholder (backend not built) |
| Lawyer Copilot Workspace | 🟡 polished placeholder (backend not built) |

## Conventions

- File names: `kebab-case.tsx` for components; `PascalCase` exports.
- Imports use `@/*` aliases via `tsconfig.json`.
- No JSDoc novellas. One short line when *why* is non-obvious; otherwise let the names speak.
- Strict TS, no `any` outside `Record<string, unknown>` for opaque dicts.
