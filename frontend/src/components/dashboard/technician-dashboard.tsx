"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CircleAlert, ClipboardList } from "lucide-react";
import Link from "next/link";

import { CodePill, IssueStatusBadge, SeverityBadge } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { formatDate, relativeTime } from "@/lib/format";
import { useEquipmentNames } from "@/lib/queries";

function IssueRow({ issue, machine }: { issue: Schemas["IssueOut"]; machine?: string }) {
  return (
    <Link href="/issues" className="flex items-center gap-3 rounded-lg p-2.5 transition-colors hover:bg-muted">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{issue.title}</p>
        <p className="truncate text-sm text-muted-foreground">{machine ?? "—"} · {relativeTime(issue.created_at)}</p>
      </div>
      {issue.error_code && <CodePill>{issue.error_code}</CodePill>}
      <SeverityBadge severity={issue.severity} />
      <IssueStatusBadge status={issue.status} />
    </Link>
  );
}

/** Technicians can't see plant analytics; their home is their own work queue. */
export function TechnicianDashboard({ username }: { username: string }) {
  const names = useEquipmentNames();
  const mine = useQuery({
    queryKey: ["issues", { assigned_to: username }],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues", { params: { query: { assigned_to: username } } })),
    select: (rows) => rows.filter((i) => i.status === "Open" || i.status === "In Progress"),
  });
  const unassigned = useQuery({
    queryKey: ["issues", { status: "Open" }],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues", { params: { query: { status: "Open" } } })),
    select: (rows) => rows.filter((i) => !i.assigned_to),
  });
  const upcoming = useQuery({
    queryKey: ["maintenance", "upcoming"],
    queryFn: async () => unwrap(await api.GET("/api/v1/maintenance/upcoming")),
  });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Assigned to me</CardTitle><CardDescription>Open and in-progress issues you own.</CardDescription></CardHeader>
        <CardContent className="space-y-1">
          {mine.isPending ? <Skeleton className="h-24" /> : mine.data?.length ? mine.data.map((i) => (
            <IssueRow key={i.id} issue={i} machine={names.get(i.equipment_id)} />
          )) : <EmptyState icon={ClipboardList} title="Nothing assigned to you" description="Claim an open issue to start on it." />}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Waiting for someone</CardTitle><CardDescription>Open issues nobody has claimed yet.</CardDescription></CardHeader>
        <CardContent className="space-y-1">
          {unassigned.isPending ? <Skeleton className="h-24" /> : unassigned.data?.length ? unassigned.data.map((i) => (
            <IssueRow key={i.id} issue={i} machine={names.get(i.equipment_id)} />
          )) : <EmptyState icon={CircleAlert} title="No unclaimed issues" />}
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader><CardTitle>Maintenance due in the next 30 days</CardTitle></CardHeader>
        <CardContent className="space-y-1">
          {upcoming.isPending ? <Skeleton className="h-24" /> : upcoming.data?.length ? upcoming.data.map((m) => (
            <Link key={m.id} href={`/equipment/${m.equipment_id}`} className="flex items-center gap-3 rounded-lg p-2.5 hover:bg-muted">
              <CalendarClock className="size-4 text-muted-foreground" />
              <span className="flex-1 font-medium">{names.get(m.equipment_id) ?? "—"}</span>
              <span className="text-sm text-muted-foreground">{formatDate(m.next_scheduled_at)}</span>
            </Link>
          )) : <EmptyState icon={CalendarClock} title="Nothing due in the next 30 days" />}
        </CardContent>
      </Card>
    </div>
  );
}
