import { cookies } from "next/headers";

import { API_URL, TOKEN_COOKIE } from "@/lib/server-config";

/**
 * Forwards browser calls to the FastAPI backend, attaching the JWT from the httpOnly cookie.
 *
 * Security: the destination is always API_URL + "/api/v1/...". The caller chooses only the path
 * under /api/v1, never the host, so the token can't be sent anywhere else. Only the headers the
 * API needs are forwarded (never the browser's cookies).
 */
async function forward(request: Request, ctx: RouteContext<"/api/backend/[...path]">) {
  const { path } = await ctx.params;
  if (path[0] !== "api" || path[1] !== "v1" || path.some((p) => p === ".." || p === ".")) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const search = new URL(request.url).search;
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  const headers = new Headers({ Accept: "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType); // keeps the multipart boundary for uploads
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const upstream = await fetch(`${API_URL}/${path.map(encodeURIComponent).join("/")}${search}`, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
    cache: "no-store",
  }).catch(() => null);
  if (!upstream) {
    return Response.json({ detail: "The EquipTrack API is unreachable" }, { status: 502 });
  }
  const passthrough = new Headers();
  for (const name of ["content-type", "content-disposition"]) {
    const value = upstream.headers.get(name);
    if (value) passthrough.set(name, value);
  }
  return new Response(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: passthrough });
}

export { forward as DELETE, forward as GET, forward as PATCH, forward as POST, forward as PUT };
