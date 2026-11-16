import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

/** Response/request types generated from the FastAPI OpenAPI schema (npm run gen:api). */
export type Schemas = components["schemas"];

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// An expired or revoked token: clear the cookie, then go to /login (clearing first avoids a redirect loop,
// because the route guard sends anyone *with* a cookie away from /login).
const signOutOnUnauthorized: Middleware = {
  async onResponse({ response }) {
    if (response.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      await fetch("/api/auth/logout", { method: "POST" });
      // A full page load on purpose: it discards every cached query from the previous session.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
  },
};

/** Typed client: paths, params and bodies are checked against the API contract at compile time. */
export const api = createClient<paths>({ baseUrl: "/api/backend" });
api.use(signOutOnUnauthorized);

/** Turn an openapi-fetch result into data, or throw an ApiError carrying FastAPI's {"detail": ...}. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : "Request failed";
    throw new ApiError(result.response.status, message);
  }
  return result.data;
}
