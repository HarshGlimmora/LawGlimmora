import { NextResponse, type NextRequest } from "next/server";

/**
 * Route gate. Runs at the edge before every matched request and bounces
 * unauthenticated users away from the workspace, signed-in users away
 * from the auth surface, and resolves the root path to either /dashboard
 * or /login based on session presence.
 *
 * The cookie is set by the FastAPI backend via Set-Cookie. For the
 * middleware to see it on Vercel, the cookie must be visible to the
 * browser on this origin — i.e. the backend is either:
 *   - reverse-proxied through Vercel (same origin), or
 *   - served on a subdomain with `Domain=.example.com; SameSite=None; Secure`.
 *
 * If neither is configured, the workspace layout's server-side cookie
 * read also falls back to the same check, and the per-page TanStack
 * Query call to /api/auth/me catches the gap on the client. This
 * middleware is the "fast path"; the layouts are the safety net.
 */
const COOKIE = "glimmora_session";

// Routes that REQUIRE a signed-in user.
const PROTECTED_PREFIXES = ["/dashboard", "/cases", "/profile-setup"];

// Routes that REQUIRE an anonymous user (signed-in users get bounced home).
const ANON_ONLY_PREFIXES = ["/login", "/signup"];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has(COOKIE);

  if (pathname === "/") {
    const target = hasSession ? "/dashboard" : "/login";
    return NextResponse.redirect(new URL(target, req.url));
  }

  if (!hasSession && PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))) {
    const url = new URL("/login", req.url);
    return NextResponse.redirect(url);
  }

  if (hasSession && ANON_ONLY_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     *  - _next/static and _next/image (build assets)
     *  - favicon.ico, robots.txt, sitemap.xml
     *  - any file with an extension (.png, .svg, .js, ...)
     */
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\..*).*)",
  ],
};
