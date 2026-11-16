"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap, type Schemas } from "@/lib/api/client";

export type Role = Schemas["Role"];
const RANK: Record<Role, number> = { technician: 1, supervisor: 2, admin: 3 };

/** Mirrors the API's role check, for showing or hiding UI. The API still enforces every permission. */
export function hasRole(role: Role | undefined, minimum: Role) {
  return role !== undefined && RANK[role] >= RANK[minimum];
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/me")),
    staleTime: 5 * 60_000,
  });
}

export async function signOut() {
  await fetch("/api/auth/logout", { method: "POST" });
  // A full page load on purpose: it discards every cached query from the previous session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.href = "/login";
}
