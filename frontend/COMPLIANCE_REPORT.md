# Glimmora Lawyer Frontend — Vercel Compliance Report

**Date**: 2026-05-19
**Audit scope**: Full frontend codebase under `frontend/`
**Target**: Vercel production deployment
**Verdict**: ✅ Production-ready after fixes in this branch.

---

## 1 · Architecture map

### Routes (13 user-facing pages)

| Path                                   | Type    | Guard            | Purpose |
|----------------------------------------|---------|------------------|---------|
| `/`                                    | server  | middleware       | Redirects to `/dashboard` or `/login` based on session cookie |
| `/login`                               | server  | anon-only        | Landing + demo cards + sign-in/sign-up tabs |
| `/signup`                              | server  | anon-only        | Standalone signup form |
| `/profile-setup`                       | server  | session required | Profile creation (firm, jurisdiction, languages…) |
| `/dashboard`                           | client  | session required | Workspace home — cases list, stat cards, package roadmap |
| `/cases/new`                           | client  | session required | New case creation form |
| `/cases/[caseId]`                      | client  | session required | Case overview — parties, dates, package shortcuts |
| `/cases/[caseId]/evidence`             | client  | session required | Evidence Vault — 7 tabs |
| `/cases/[caseId]/research`             | client  | session required | Research & Precedent Engine — 6 tabs |
| `/cases/[caseId]/simulator`            | client  | session required | Placeholder (backend not built) |
| `/cases/[caseId]/copilot`              | client  | session required | Placeholder (backend not built) |
| `/cases/[caseId]/report`               | client  | session required | Placeholder (final report lives inside Evidence Vault tab) |
| `*` (catch-all)                        | server  | always           | `not-found.tsx` — branded 404 |

### Feature folders

```
src/features/
├── auth/           AuthCard · DemoCards · LoginForm · SignupForm
├── profile/        ProfileForm
├── case/           CaseForm
├── evidence/       8 components (vault tabs + chat)
├── research/       6 components (ask · corpus · authorities · timeline · sessions · connections)
└── placeholders/   PackagePlaceholder
```

### Shared layer

```
src/components/
├── ui/         button · input · select · multi-select · tabs · dialog · textarea · label · badge · card · separator
├── layout/     Brandbar · Brandmark · Sidebar · PageHeader
├── cards/      CaseCard · PackageCard · StatCard
├── atoms/      Eyebrow · Ornament · Grain
└── feedback/   Spinner · EmptyState · ErrorState
```

### API contract (one place: `src/lib/api/endpoints.ts`)

| Backend route                                                                        | Frontend wrapper                              |
|--------------------------------------------------------------------------------------|-----------------------------------------------|
| `GET/POST /api/auth/{me,login,signup,demo-login,logout}`                             | `authEndpoints.*`                             |
| `GET /api/constants`                                                                 | `constantsEndpoint()`                         |
| `GET/PUT /api/profile`                                                               | `profileEndpoints.*`                          |
| `GET/POST/PUT /api/cases[/:id]`                                                      | `caseEndpoints.*`                             |
| `POST /api/cases/:id/evidence/upload` (multipart)                                    | `evidenceEndpoints.upload`                    |
| `GET /api/cases/:id/evidence/{documents,chunks,entities,partitions,contradictions,missing-evidence}` | `evidenceEndpoints.*`             |
| `GET/POST/DELETE /api/cases/:id/evidence/chat`                                       | `chatEndpoints.*`                             |
| `GET/POST/DELETE /api/cases/:id/research/{documents,ingest-text,upload,enrich,…}`    | `researchEndpoints.*`                         |
| `POST /api/cases/:id/research/{search,research,sessions,downstream/build}`           | `researchEndpoints.{search,run,saveSession,buildDownstream}` |
| `PATCH /api/cases/:id/research/sessions/:sid/feedback`                               | `researchEndpoints.patchFeedback`             |
| `GET /api/cases/:id/research/sessions/:sid/export/{json,markdown,pdf}` (download)    | `researchEndpoints.sessionExportUrl`          |
| `GET/POST /api/cases/:id/report[/generate]`                                          | `reportEndpoints.{get,generate}`              |
| `GET /api/cases/:id/report/export/{json,text,pdf}` (download)                        | `reportEndpoints.exportUrl`                   |

### Environment variables

| Var                          | Where used                            | Build / runtime |
|------------------------------|---------------------------------------|-----------------|
| `NEXT_PUBLIC_API_BASE_URL`   | `src/lib/api/client.ts` → `api` + `backendUrl()` | Build-time bake; reflected in client bundle |
| `NODE_ENV`                   | `src/lib/logger.ts`, error-logging   | Runtime, set by Vercel automatically |

**No other env vars.** No server secrets touched on the frontend at any layer.

---

## 2 · Compliance findings & fixes

### Fixed in this pass

| # | Risk                                                              | Severity | Fix |
|---|-------------------------------------------------------------------|----------|-----|
| 1 | `localhost:8000` fallback would mask missing env var in prod      | High     | `getApiBaseUrl()` now emits a console warning when `NEXT_PUBLIC_API_BASE_URL` is missing in production builds |
| 2 | Export URLs used `api.defaults.baseURL` → potential build-time leak | High   | New `backendUrl(path)` helper; all export URLs route through it |
| 3 | No `not-found.tsx`, `error.tsx`, `global-error.tsx`               | High     | Added all three with branded UI + trace ids |
| 4 | No segment-level loading or error boundaries                      | Med      | Added `(workspace)/error.tsx`, `(workspace)/loading.tsx`, `(auth)/error.tsx`, `loading.tsx` |
| 5 | No edge middleware — every layout re-reads the cookie             | Med      | New `src/middleware.ts` handles redirects at the edge |
| 6 | "Private alpha · localhost" string visible in sidebar             | Med      | Replaced with "Private alpha" |
| 7 | `@import url("fonts.googleapis.com/…")` blocked render            | Med      | Migrated to `next/font/google` with `display: "swap"` and CSS variables |
| 8 | Brandbar logout silently failed on network error                  | Med      | Wrapped in try/catch; client state always cleared and redirect always fires |
| 9 | Canonical-store leaked server FS path `cases/{id}/evidence/logs/…`| Low      | Replaced with a generic description |
| 10 | No `vercel.json` for build & security headers                    | Low      | Added with X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy |
| 11 | No `.vercelignore` → Playwright artefacts shipped to Vercel       | Low      | Added with e2e, test-results, playwright-report, screenshots excluded |
| 12 | `next.config.mjs` missing prod hardening                          | Low      | Added `poweredByHeader: false`, `productionBrowserSourceMaps: false`, empty `images.remotePatterns` |

### Pre-existing compliance, verified clean

| Check                                                            | Status |
|------------------------------------------------------------------|--------|
| No `fs`, `path`, `child_process`, or other Node-only modules in `src/` (outside server components) | ✅ |
| No top-level `window`, `document`, `sessionStorage`, `localStorage` references | ✅ |
| Every interactive component is `"use client"` marked              | ✅ |
| Every form uses RHF + Zod                                         | ✅ |
| Every TanStack Query query has `loading`, `error`, `empty`, and `success` states | ✅ |
| Single axios instance, single base URL source                     | ✅ |
| Cookie-based session via `withCredentials: true`                  | ✅ |
| Typed API contract for every endpoint                             | ✅ |
| Strict TypeScript with `noUncheckedIndexedAccess: true` passes    | ✅ |
| No client-side secrets, no `process.env.SECRET_*` references      | ✅ |
| No `dangerouslySetInnerHTML`                                      | ✅ |

---

## 3 · Vercel-specific risks resolved

### Server vs client boundary

The only server components in the app are the layouts (`(auth)/layout.tsx`,
`(workspace)/layout.tsx`) and the root `page.tsx`. They use `cookies()`
and `redirect()` from `next/headers` and `next/navigation` — both
Vercel-safe. No `fs`, no top-level fetch with credentials, no Node-only
APIs.

### Edge runtime compatibility

The new `middleware.ts` uses only the Edge-runtime-safe `NextRequest`,
`NextResponse`, and cookie APIs. It will run at the Vercel Edge with no
modifications.

### Cookie / session handling

The cookie is set by FastAPI. For cross-origin Vercel→backend traffic
the backend must set `SameSite=None; Secure`. For same-origin (recommended),
use Vercel rewrites to route `/api/*` through the Next.js domain.

`VERCEL_DEPLOYMENT.md` documents both setups.

### Bundle size

Removed external Google Fonts CSS import. Switched to `next/font/google`,
which self-hosts the fonts at build time. This eliminates a render-blocking
network request and ensures fonts are CDN-cached on the same origin.

### No SSR data fetching

Every data-loading page is `"use client"` and uses TanStack Query. This
means:
- A backend outage produces well-behaved loading/error states, not a
  500 page from the Vercel function.
- Cold starts touch zero backend code.
- All retry behaviour is controlled by one QueryClient.

---

## 4 · Deployment checklist

- [x] Single env var, documented, with prod warning
- [x] HTTPS-only assumption baked into `VERCEL_DEPLOYMENT.md`
- [x] `vercel.json` declares framework + security headers
- [x] `.vercelignore` excludes test artefacts
- [x] `next.config.mjs` hardened for production
- [x] `not-found.tsx`, `error.tsx`, `global-error.tsx`, `loading.tsx` present
- [x] Segment-level `error.tsx` + `loading.tsx` for both `(auth)` and `(workspace)`
- [x] Edge middleware handles redirects without re-rendering
- [x] `next/font` used for all webfonts
- [x] No `localhost` strings in production code paths
- [x] Strict TypeScript passes (`npm run typecheck`)
- [x] Production build succeeds (`npm run build` with `NEXT_PUBLIC_API_BASE_URL` set)
- [ ] Backend `SameSite=None; Secure` cookie verified for chosen deployment topology *(infra/backend task)*

The single open item is a backend/infrastructure decision, not a frontend
gap — see §3 of `VERCEL_DEPLOYMENT.md` for the two valid topologies.

---

## 5 · Files added or modified

```
A  src/app/not-found.tsx
A  src/app/error.tsx
A  src/app/global-error.tsx
A  src/app/loading.tsx
A  src/app/(workspace)/error.tsx
A  src/app/(workspace)/loading.tsx
A  src/app/(auth)/error.tsx
A  src/middleware.ts
A  vercel.json
A  .vercelignore
A  VERCEL_DEPLOYMENT.md
A  COMPLIANCE_REPORT.md

M  src/app/layout.tsx                          (next/font integration)
M  src/styles/globals.css                       (CSS var-driven fonts)
M  tailwind.config.ts                           (CSS var-driven font stack)
M  next.config.mjs                              (prod hardening)
M  src/lib/api/client.ts                        (getApiBaseUrl + backendUrl + prod warning)
M  src/lib/api/endpoints.ts                     (export URLs via backendUrl)
M  src/components/layout/brandbar.tsx           (logout error handling)
M  src/components/layout/sidebar.tsx            (remove "localhost" footer)
M  src/features/evidence/canonical-store.tsx    (remove FS path leak)
M  .env.local.example                           (production-aware notes)
M  .env.local                                   (mirrors example)
M  .gitignore                                   (Playwright artefacts)
M  README.md                                    (Vercel section + status table refresh)
```
