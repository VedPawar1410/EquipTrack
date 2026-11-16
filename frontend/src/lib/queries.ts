"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";

/** Shared queries: one cache key per resource, so every screen showing it stays consistent. */
export const keys = {
  equipment: (filters?: object) => ["equipment", filters ?? {}] as const,
  health: ["equipment", "health"] as const,
  summary: (id: string) => ["equipment", id, "summary"] as const,
  dashboard: ["dashboard"] as const,
};

export type EquipmentFilters = { search?: string; status?: string; department?: string; type?: string };

export function useEquipmentList(filters: EquipmentFilters = {}) {
  return useQuery({
    queryKey: keys.equipment(filters),
    queryFn: async () => unwrap(await api.GET("/api/v1/equipment", {
      params: { query: { limit: 500, ...filters } as never },
    })),
  });
}

export function useHealthMap() {
  return useQuery({
    queryKey: keys.health,
    queryFn: async () => unwrap(await api.GET("/api/v1/equipment/health")),
    select: (rows) => new Map(rows.map((r) => [r.equipment_id, r])),
  });
}

export function useEquipmentNames() {
  const { data } = useEquipmentList();
  return new Map((data ?? []).map((e) => [e.id, e.name]));
}
