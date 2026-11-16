import { API_URL } from "@/lib/server-config";

// A cold start (the API scaled to zero) can take ~25 s; give it room to finish before we give up.
export const maxDuration = 60;

/**
 * Wake the API. The login page calls this as soon as it opens, so the container boots while the
 * visitor is still typing instead of after they press "Sign in".
 *
 * POST, not GET: a GET handler that only fetches could be prerendered at build time, which would
 * call the API during the build and freeze the answer. A POST always runs per request.
 */
export async function POST() {
  const response = await fetch(`${API_URL}/health`, {
    cache: "no-store",
    signal: AbortSignal.timeout(55_000),
  }).catch(() => null);
  return Response.json({ ready: response?.ok ?? false });
}
