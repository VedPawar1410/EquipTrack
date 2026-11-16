import { NextResponse, type NextRequest } from "next/server";

const TOKEN_COOKIE = "et_token";

/**
 * Optimistic route guard: no session cookie -> send to /login. This only decides which page to show;
 * the real authorization happens in the API on every request (an expired or forged token gets a 401).
 */
export function proxy(request: NextRequest) {
  const loggedIn = request.cookies.has(TOKEN_COOKIE);
  const { pathname, search } = request.nextUrl;
  if (pathname === "/login") {
    return loggedIn ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  }
  if (!loggedIn) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Everything except API routes, Next internals and static files.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};
