"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { CodePill, SeverityBadge } from "@/components/domain/badges";
import { PageHeader } from "@/components/layout/page-header";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { hasRole, useMe } from "@/lib/auth";
import { SEVERITIES } from "@/lib/enums";
import { relativeTime } from "@/lib/format";
import { BOARD_COLUMNS, TRANSITIONS } from "@/lib/issues";
import { useEquipmentList } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { ReportIssueDialog } from "./report-issue-dialog";

type Issue = Schemas["IssueOut"];
const ALL = "all";
const COLUMN_ACCENT: Record<string, string> = {
  Open: "bg-danger", "In Progress": "bg-info", Resolved: "bg-success", Closed: "bg-muted-foreground/40",
};
const CLOSED_SHOWN = 8;

export function IssuesBoard() {
  const { data: me } = useMe();
  const [severity, setSeverity] = useState(ALL);
  const [machine, setMachine] = useState(ALL);
  const [assigning, setAssigning] = useState<Issue | null>(null);
  const queryClient = useQueryClient();
  const { data: equipment = [] } = useEquipmentList();
  const names = new Map(equipment.map((e) => [e.id, e.name]));
  const { data: issues, isPending } = useQuery({
    queryKey: ["issues", "board"],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues", { params: { query: { limit: 500 } } })),
  });

  const move = useMutation({
    mutationFn: async ({ issue, status }: { issue: Issue; status: Schemas["IssueStatus"] }) =>
      unwrap(await api.PATCH("/api/v1/issues/{issue_id}/status", { params: { path: { issue_id: issue.id } }, body: { status } })),
    onSuccess: (issue) => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`“${issue.title}” is now ${issue.status}`);
    },
    onError: (error) => toast.error(error.message),
  });

  const visible = (issues ?? []).filter(
    (i) => (severity === ALL || i.severity === severity) && (machine === ALL || i.equipment_id === machine),
  );
  return (
    <>
      <PageHeader
        title="Issues"
        description="Report, claim, resolve and close equipment issues."
        actions={<ReportIssueDialog trigger={<Button><Plus className="size-4" /> Report issue</Button>} />}
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger className="w-44" aria-label="Filter by severity"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All severities</SelectItem>
            {SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={machine} onValueChange={setMachine}>
          <SelectTrigger className="w-60" aria-label="Filter by machine"><SelectValue /></SelectTrigger>
          <SelectContent className="max-h-72">
            <SelectItem value={ALL}>All machines</SelectItem>
            {equipment.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {isPending ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{BOARD_COLUMNS.map((c) => <Skeleton key={c} className="h-96" />)}</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {BOARD_COLUMNS.map((column) => {
            const all = visible.filter((i) => i.status === column);
            const cards = column === "Closed" ? all.slice(0, CLOSED_SHOWN) : all;
            return (
              <section key={column} aria-label={`${column} issues`} className="flex flex-col rounded-xl bg-muted/50 p-3">
                <header className="mb-3 flex items-center gap-2 px-1">
                  <span className={cn("size-2 rounded-full", COLUMN_ACCENT[column])} />
                  <h2 className="text-sm font-semibold">{column}</h2>
                  <span className="ml-auto rounded-full bg-background px-2 text-xs tabular-nums text-muted-foreground">{all.length}</span>
                </header>
                <div className="space-y-2">
                  {cards.length === 0 && <p className="px-1 py-6 text-center text-sm text-muted-foreground">No issues</p>}
                  {cards.map((issue) => (
                    <IssueCard key={issue.id} issue={issue} machine={names.get(issue.equipment_id)} role={me?.role}
                               busy={move.isPending && move.variables?.issue.id === issue.id}
                               onMove={(status) => move.mutate({ issue, status })} onAssign={() => setAssigning(issue)} />
                  ))}
                  {column === "Closed" && all.length > CLOSED_SHOWN && (
                    <p className="px-1 text-xs text-muted-foreground">+{all.length - CLOSED_SHOWN} older closed issues</p>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
      <AssignDialog issue={assigning} onClose={() => setAssigning(null)} />
    </>
  );
}

function IssueCard({ issue, machine, role, busy, onMove, onAssign }: {
  issue: Issue; machine?: string; role?: Schemas["Role"]; busy: boolean;
  onMove: (status: Schemas["IssueStatus"]) => void; onAssign: () => void;
}) {
  const actions = TRANSITIONS.filter((t) => t.from === issue.status && hasRole(role, t.minRole));
  const supervisorOnly = TRANSITIONS.some((t) => t.from === issue.status && !hasRole(role, t.minRole));
  const canAssign = hasRole(role, "supervisor") && (issue.status === "Open" || issue.status === "In Progress");
  return (
    <Card className={cn("gap-2 p-3 shadow-xs transition-shadow hover:shadow-md", busy && "opacity-60")}>
      <div className="flex flex-wrap items-center gap-1.5">
        <SeverityBadge severity={issue.severity} />
        {issue.error_code && <CodePill>{issue.error_code}</CodePill>}
      </div>
      <p className="text-sm leading-snug font-medium">{issue.title}</p>
      <Link href={`/equipment/${issue.equipment_id}`} className="text-xs text-muted-foreground hover:underline">{machine ?? "—"}</Link>
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {issue.assigned_to ? (
            <Avatar className="size-6"><AvatarFallback className="bg-primary/10 text-[10px] font-semibold text-primary">{issue.assigned_to.slice(0, 2).toUpperCase()}</AvatarFallback></Avatar>
          ) : <span>Unassigned</span>}
          <span>· {relativeTime(issue.created_at)}</span>
        </div>
      </div>
      {(actions.length > 0 || canAssign) && (
        <div className="flex flex-wrap gap-1.5 border-t pt-2">
          {actions.map((a) => (
            <Button key={a.to} size="sm" variant={a.label === "Reopen" ? "outline" : "secondary"} disabled={busy} onClick={() => onMove(a.to)}>
              {a.label}
            </Button>
          ))}
          {canAssign && <Button size="sm" variant="ghost" onClick={onAssign}><UserPlus className="size-3.5" /> Assign</Button>}
        </div>
      )}
      {issue.status === "Resolved" && supervisorOnly && (
        <p className="text-[11px] text-muted-foreground">Closing or reopening needs a supervisor.</p>
      )}
    </Card>
  );
}

function AssignDialog({ issue, onClose }: { issue: Issue | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const assign = useMutation({
    mutationFn: async (username: string) =>
      unwrap(await api.PATCH("/api/v1/issues/{issue_id}/assign", { params: { path: { issue_id: issue!.id } }, body: { assigned_to: username } })),
    onSuccess: (i) => { queryClient.invalidateQueries({ queryKey: ["issues"] }); toast.success(`Assigned to ${i.assigned_to}`); onClose(); },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog open={issue !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Assign issue</DialogTitle>
          <DialogDescription>{issue?.title}</DialogDescription>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); assign.mutate(String(new FormData(e.currentTarget).get("username")).trim()); }} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Technician&apos;s username</Label>
            <Input id="username" name="username" required defaultValue={issue?.assigned_to ?? ""} autoFocus />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={assign.isPending}>Assign</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

