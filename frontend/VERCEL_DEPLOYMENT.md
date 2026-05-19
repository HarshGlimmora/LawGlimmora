# Glimmora Lawyer — Vercel deployment guide

This frontend is a Next.js 14 (App Router) workspace that talks to a
FastAPI backend over a single env var. It is designed to deploy on
Vercel with zero post-install work beyond setting that one variable.

---

## 1 · One-time Vercel project setup

1. From your Vercel dashboard, **Add New → Project**.
2. Import this repo. When asked for the **Root Directory**, set it to
   `frontend/`.
3. Vercel will auto-detect Next.js. Leave the build settings as-is:
   - **Framework Preset**: Next.js
   - **Build Command**: `npm run build` (also in `vercel.json`)
   - **Output Directory**: `.next`
   - **Install Command**: `npm install`
   - **Development Command**: `next dev` (only used by `vercel dev`)
4. Set **Node.js Version** to 20.x.

## 2 · Environment variables (required)

Set these for **Production**, **Preview**, **Development**:

| Key                          | Value                                | Notes |
|------------------------------|--------------------------------------|-------|
| `NEXT_PUBLIC_API_BASE_URL`   | `https://api.glimmora.example`       | HTTPS in prod; no trailing slash. |

> Anything starting with `NEXT_PUBLIC_` is baked into the client bundle
> at build time. **Never** put secrets here.

If the variable is missing, the app falls back to `http://localhost:8000`
and prints a console warning. That fallback exists so local dev does not
require a `.env.local`; in production you will see the warning and your
API calls will fail with a network error until you set the variable.

## 3 · Cookie / CORS contract with the backend

The session cookie `glimmora_session` is set by the FastAPI backend.
For the browser to forward it on every Vercel-served request:

- **If the backend is on a different origin** (e.g. `app.example.com`
  → `api.example.com`), the backend must set the cookie with:
  ```
  Set-Cookie: glimmora_session=…; Path=/; HttpOnly; Secure; SameSite=None
  ```
  and respond to CORS preflights with:
  ```
  Access-Control-Allow-Origin: https://app.example.com
  Access-Control-Allow-Credentials: true
  ```
  The frontend axios client already sends `withCredentials: true`.
- **If the backend is reverse-proxied through Vercel** (recommended for
  single-origin deployments), use a Vercel rewrite to route `/api/*` to
  the backend. Cookies will be first-party — no CORS or SameSite gymnastics.

A rewrite-based setup looks like this in `vercel.json`:
```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://api.example.com/api/:path*" }
  ]
}
```
…in which case `NEXT_PUBLIC_API_BASE_URL` can be left empty / set to the
empty string or to your own domain.

## 4 · Compliance checklist

- [x] All runtime configuration comes from env vars
- [x] No hardcoded backend domains in source
- [x] No filesystem reads/writes anywhere in the client
- [x] No `window` / `document` access at module top level
- [x] All client-only components marked `"use client"`
- [x] Server components only use server-safe APIs (`cookies()`, `redirect()`)
- [x] `not-found.tsx`, `error.tsx`, `global-error.tsx` all present
- [x] Per-segment loading states (`(workspace)/loading.tsx`, root `loading.tsx`)
- [x] Edge middleware (`src/middleware.ts`) handles redirects before render
- [x] `next/font` loads Google Fonts at build time (no runtime CSS @import)
- [x] Strict TypeScript (`noUncheckedIndexedAccess: true`) passes
- [x] Production build (`npm run build`) succeeds with `NEXT_PUBLIC_API_BASE_URL` set
- [x] Security headers configured in `vercel.json`
- [x] `.vercelignore` excludes Playwright artefacts and local secrets

## 5 · Smoke test after first deploy

1. Hit the Vercel URL. You should be redirected to `/login`.
2. Open browser devtools → Network. Click **Sign in as Anika**. The
   `POST /api/auth/demo-login` call must:
   - Resolve against your `NEXT_PUBLIC_API_BASE_URL`
   - Receive a `Set-Cookie: glimmora_session=…` response header
   - Land you on `/dashboard`
3. Browse to `/cases/1/research`. Every tab must render without console
   errors. If the corpus is empty, the **Corpus** tab will show the
   "No precedents in this case yet" empty state — not a crash.
4. Trigger an export from the **Sessions** tab. The href must point at
   your prod backend, not localhost.

## 6 · Failure modes & how to spot them

| Symptom                                           | Likely cause                                                   |
|--------------------------------------------------|----------------------------------------------------------------|
| Every API call → `Network Error` in devtools     | `NEXT_PUBLIC_API_BASE_URL` not set, or backend CORS misconfig  |
| Login succeeds but `/dashboard` bounces to `/login` | Cookie not being forwarded — check `SameSite=None; Secure`     |
| `Unauthorized` after refresh                      | Cookie domain mismatch, or backend session storage reset       |
| Export links 404                                  | Backend path changed; check `researchEndpoints.sessionExportUrl` |
| Page shows `Workspace error` boundary            | A render-time exception — open devtools console for the trace id |

## 7 · What this app does NOT do on Vercel

- No filesystem persistence — all state lives in the backend
- No server actions, no API routes — every backend call is client-side
- No background jobs / cron — the backend owns long-running work
- No SSR data fetching — every page is `"use client"` and loads via TanStack Query

That means a Vercel cold start touches no backend code and an outage of
the backend produces well-behaved loading/error states everywhere, not
crashes.
