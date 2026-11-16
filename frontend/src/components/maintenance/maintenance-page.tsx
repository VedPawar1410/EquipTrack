"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CalendarCheck, Plus, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatDate, relativeTime } from "@/lib/format";
import { useEquipmentNames } from "@/lib/queries";

import { LogMaintenanceSheet } from "./log-maintenance-sheet";

type Log = Schemas["MaintenanceOut"];

function weekLabel(iso: string) {
  const days = Math.floor((new Date(iso).getTime() - Date.now()) / 86_400_000);
  return days < 7 ? "This week" : days < 14 ? "Next week" : "In 2–4 weeks";
}

export function MaintenancePage() {
  const names = useEquipmentNames();
  const upcoming = useQuery({
    queryKey: ["maintenance", "upcoming"],
    queryFn: async () => unwrap(await api.GET("/api/v1/maintenance/upcoming")),
  });
  const overdue = useQuery({
    queryKey: ["maintenance", "overdue"],
    queryFn: async () => unwrap(await api.GET("/api/v1/maintenance/overdue")),
  });
  const groups = new Map<string, Log[]>();
  for (const log of upcoming.data ?? []) {
    const label = weekLabel(log.next_scheduled_at!);
    groups.set(label, [...(groups.get(label) ?? []), log]);
  }
  return (
    <>
      <PageHeader
        title="Maintenance"
        description="What's due, what's late, and logging the work."
        actions={<LogMaintenanceSheet trigger={<Button><Plus className="size-4" /> Log maintenance</Button>} />}
      />
      {(overdue.data?.length ?? 0) > 0 && (
        <Card className="mb-6 gap-3 border-danger/30 bg-danger-soft p-4">
          <div className="flex items-center gap-2 font-semibold text-danger"><TriangleAlert className="size-4" /> Overdue</div>
          {overdue.data!.map((log) => (
            <Link key={log.id} href={`/equipment/${log.equipment_id}`} className="flex items-center justify-between gap-4 rounded-lg bg-background/70 px-3 py-2 text-sm hover:bg-background">
              <span className="font-medium">{names.get(log.equipment_id) ?? "—"}</span>
              <span className="text-danger">due {formatDate(log.next_scheduled_at)} · {relativeTime(log.next_scheduled_at!)}</span>
            </Link>
          ))}
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Upcoming (next 30 days)</CardTitle>
          <CardDescription>Each machine&apos;s next planned service, from its most recent maintenance log.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {upcoming.isPending && <Skeleton className="h-40" />}
          {upcoming.data?.length === 0 && <EmptyState icon={CalendarCheck} title="Nothing due in the next 30 days" />}
          {[...groups].map(([label, logs]) => (
            <div key={label}>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</h3>
              <div className="divide-y rounded-lg border">
                {logs.map((log) => (
                  <Link key={log.id} href={`/equipment/${log.equipment_id}`} className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-muted/50">
                    <CalendarClock className="size-4 text-muted-foreground" />
                    <span className="flex-1 font-medium">{names.get(log.equipment_id) ?? "—"}</span>
                    <span className="hidden text-muted-foreground sm:inline">last: {log.log_type.toLowerCase()} · {log.description}</span>
                    <span className="w-28 text-right tabular-nums">{formatDate(log.next_scheduled_at)}</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
