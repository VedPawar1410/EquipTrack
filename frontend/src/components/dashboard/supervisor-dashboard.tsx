"use client";

import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CircleAlert, Factory, Package, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { CodePill, IssueStatusBadge, SeverityBadge } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { HealthRing } from "@/components/domain/health-ring";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, unwrap } from "@/lib/api/client";
import { relativeTime } from "@/lib/format";
import { keys, useEquipmentNames } from "@/lib/queries";

import { SeverityBars, StatusDonut } from "./charts";
import { KpiCard } from "./kpi-card";

export function SupervisorDashboard() {
  const { data, isPending } = useQuery({
    queryKey: keys.dashboard,
    queryFn: async () => unwrap(await api.GET("/api/v1/analytics/dashboard")),
  });
  const { data: critical = [] } = useQuery({
    queryKey: ["issues", "critical"],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues/critical")),
  });
  const names = useEquipmentNames();

  if (isPending || !data) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
        <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-80 lg:col-span-2" /><Skeleton className="h-80" /></div>
      </div>
    );
  }
  const openIssues = Object.values(data.open_issues_by_severity).reduce((a, b) => a + b, 0);
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard label="Active equipment" value={data.equipment_by_status.active ?? 0} icon={Factory} tone="success"
                 hint={`${data.equipment_by_status["under maintenance"] ?? 0} under maintenance`} href="/equipment?status=active" />
        <KpiCard label="Open issues" value={openIssues} icon={CircleAlert} tone={data.critical_open_issues ? "danger" : "neutral"}
                 hint={`${data.critical_open_issues} critical`} href="/issues" />
        <KpiCard label="Due in 30 days" value={data.machines_due_next_30_days} icon={CalendarClock} href="/maintenance" />
        <KpiCard label="Overdue" value={data.machines_overdue} icon={TriangleAlert}
                 tone={data.machines_overdue ? "danger" : "success"} hint="past their next service date" href="/maintenance" />
        <KpiCard label="Low-stock parts" value={data.low_stock_parts} icon={Package}
                 tone={data.low_stock_parts ? "warning" : "success"} hint="at or below reorder level" href="/parts" />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Needs attention</CardTitle>
            <CardDescription>Machines below a good health score, worst first, with the reasons.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {data.needs_attention.length === 0 && (
              <EmptyState icon={Factory} title="Every machine is in good health" description="Nothing scores below 80 right now." />
            )}
            {data.needs_attention.map((m) => (
              <Link key={m.equipment_id} href={`/equipment/${m.equipment_id}`}
                    className="flex items-center gap-4 rounded-lg p-2.5 transition-colors hover:bg-muted">
                <HealthRing score={m.score} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{m.name}</p>
                  <p className="truncate text-sm text-muted-foreground">
                    {m.deductions.map((d) => `${d.reason}, -${d.points}`).join(" · ")}
                  </p>
                </div>
                <span className="text-xs capitalize text-muted-foreground">{m.band}</span>
              </Link>
            ))}
          </CardContent>
        </Card>
        <div className="grid gap-4 lg:col-span-2">
          <Card>
            <CardHeader><CardTitle>Equipment by status</CardTitle></CardHeader>
            <CardContent><StatusDonut data={data.equipment_by_status} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Open issues by severity</CardTitle></CardHeader>
            <CardContent><SeverityBars data={data.open_issues_by_severity} /></CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Critical open issues</CardTitle>
          <CardDescription>Unresolved critical issues, oldest first.</CardDescription>
        </CardHeader>
        <CardContent>
          {critical.length === 0 ? (
            <EmptyState icon={CircleAlert} title="No critical issues" description="Nothing critical is waiting." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow><TableHead>Issue</TableHead><TableHead>Machine</TableHead><TableHead>Code</TableHead>
                  <TableHead>Severity</TableHead><TableHead>Status</TableHead><TableHead>Assignee</TableHead><TableHead className="text-right">Reported</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {critical.map((issue) => (
                  <TableRow key={issue.id}>
                    <TableCell className="font-medium">{issue.title}</TableCell>
                    <TableCell><Link className="hover:underline" href={`/equipment/${issue.equipment_id}`}>{names.get(issue.equipment_id) ?? "—"}</Link></TableCell>
                    <TableCell>{issue.error_code ? <CodePill>{issue.error_code}</CodePill> : "—"}</TableCell>
                    <TableCell><SeverityBadge severity={issue.severity} /></TableCell>
                    <TableCell><IssueStatusBadge status={issue.status} /></TableCell>
                    <TableCell>{issue.assigned_to ?? <span className="text-muted-foreground">Unassigned</span>}</TableCell>
                    <TableCell className="text-right text-muted-foreground">{relativeTime(issue.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
