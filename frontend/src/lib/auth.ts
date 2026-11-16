"use client";

import { useQuery } from "@tanstack/react-query";

import { useHydrated } from "@/hooks/use-hydrated";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export type Role = Schemas["Role"];
const RANK: Record<Role, number> = { technician: 1, supervisor: 2, admin: 3 };

/** Mirrors the API's role check, for showing or hiding UI. The API still enforces every permission. */
export function hasRole(role: Role | undefined, minimum: Role) {
  return role !== undefined && RANK[role] >= RANK[minimum];
}

/**
 * The signed-in user. Until hydration finishes it reports "pending", exactly like the server render
 * (which never knows who is signed in). Without this, a part of the page that hydrates after the user
 * has loaded would render role-dependent UI the server HTML lacks: a hydration mismatch.
 */
export function useMe() {
  const hydrated = useHydrated();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/me")),
    staleTime: 5 * 60_000,
  });
  return { data: hydrated ? query.data : undefined, isPending: !hydrated || query.isPending };
}

export async function signOut() {
  await fetch("/api/auth/logout", { method: "POST" });
  // A full page load on purpose: it discards every cached query from the previous session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}
