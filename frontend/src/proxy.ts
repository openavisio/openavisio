import { NextResponse } from "next/server";
import { auth } from "@/auth";

export default auth(async function middleware(req) {
  const { pathname } = req.nextUrl;
  const isSetupPath = pathname === "/setup";
  const isPublicPath = ["/login", "/register", "/recover", "/setup", "/api", "/patients/invite", "/share"].some((p) =>
    pathname.startsWith(p)
  );

  const setupCookie = req.cookies.get("setup_complete");
  let setupConfirmed = !!setupCookie;

  if (!setupCookie && !isSetupPath && !isPublicPath) {
    try {
      const apiUrl = process.env.API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/organization/status`, {
        cache: "no-store",
      });
      if (res.ok) {
        const { initialized } = await res.json();
        if (!initialized) {
          return NextResponse.redirect(new URL("/setup", req.url));
        }
        setupConfirmed = true;
      }
    } catch {
      // Backend unreachable — allow through, page will handle it
    }
  }

  const sessionError = (req.auth as any)?.error;
  if (!isPublicPath && (!req.auth || sessionError === "RefreshTokenExpired")) {
    const loginUrl = new URL("/login", req.url);
    if (sessionError === "RefreshTokenExpired") {
      loginUrl.searchParams.set("error", "SessionExpired");
    } else {
      loginUrl.searchParams.set("callbackUrl", pathname + req.nextUrl.search);
    }
    return NextResponse.redirect(loginUrl);
  }

  const response = NextResponse.next();
  if (setupConfirmed && !setupCookie) {
    response.cookies.set("setup_complete", "1", {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 365,
    });
  }
  return response;
});

// NextAuth's own routes are excluded, not just waved through as a public path.
// auth() runs on every matched request and appends the re-encoded session as a
// Set-Cookie; on /api/auth/callback/credentials that raced the fresh ticket the
// sign-in itself was setting, so a login after an expired session landed on
// whichever cookie won and had to be repeated.
export const config = {
  matcher: ["/((?!_next|api/auth|.*\\..*).*)"],
};
