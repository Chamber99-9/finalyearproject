import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "sajilo_auth_token";

// Routes that require a logged-in user. Unauthenticated visitors are sent to
// /login (with a redirect back to where they were heading).
const PROTECTED_PREFIXES = ["/dashboard", "/applications", "/ocr", "/payments"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
  if (!isProtected) {
    return NextResponse.next();
  }

  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  if (token) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/applications/:path*",
    "/ocr/:path*",
    "/payments/:path*"
  ]
};
