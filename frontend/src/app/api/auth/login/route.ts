import { cookies } from "next/headers";

import { API_URL, TOKEN_COOKIE, TOKEN_MAX_AGE_SECONDS } from "@/lib/server-config";

/** Exchange username + password for the API's JWT, and keep it in an httpOnly cookie. */
export async function POST(request: Request) {
  const { username, password } = (await request.json().catch(() => ({}))) as {
    username?: string;
    password?: string;
  };
  if (!username || !password) {
    return Response.json({ detail: "Username and password are required" }, { status: 422 });
  }
  const upstream = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
    cache: "no-store",
  }).catch(() => null);
  if (!upstream) {
    return Response.json({ detail: "The EquipTrack API is unreachable" }, { status: 502 });
  }
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return Response.json({ detail: body.detail ?? "Sign-in failed" }, { status: upstream.status });
  }
  (await cookies()).set(TOKEN_COOKIE, body.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: TOKEN_MAX_AGE_SECONDS,
  });
  return Response.json({ ok: true });
}
