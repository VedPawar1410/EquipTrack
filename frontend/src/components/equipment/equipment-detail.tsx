"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Archive, ChevronDown, CircleAlert, Download, FileText, Package, Pencil, Wrench } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { CodePill, EquipmentStatusBadge, IssueStatusBadge, Pill, SeverityBadge } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { HealthRing } from "@/components/domain/health-ring";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { hasRole, useMe } from "@/lib/auth";
import { currency, formatDate, relativeTime } from "@/lib/format";
import { keys } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { EquipmentFormDialog } from "./equipment-form-dialog";

type Status = Schemas["EquipmentStatus"];
const BAND_TEXT = { good: "text-success", fair: "text-warning", poor: "text-danger" } as const;

export function EquipmentDetail({ id }: { id: string }) {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const summary = useQuery({
    queryKey: keys.summary(id),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/equipment/{equipment_id}/summary", { params: { path: { equipment_id: id } } })),
  });

  const setStatus = useMutation({
    mutationFn: async (status: Status) =>
      unwrap(await api.PATCH("/api/v1/equipment/{equipment_id}/status", {
        params: { path: { equipment_id: id } }, body: { status },
      })),
    onSuccess: (e) => {
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: keys.dashboard });
      toast.success(`Status set to ${e.status}`);
    },
    onError: (error) => toast.error(error.message),
  });

  if (summary.isError) {
    return (
      <EmptyState icon={CircleAlert} title="Equipment not found" description={summary.error.message}
                  action={<Button asChild variant="outline"><Link href="/equipment">Back to equipment</Link></Button>} />
    );
  }
  if (!summary.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16" />
        <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-64" /><Skeleton className="h-64 lg:col-span-2" /></div>
      </div>
    );
  }
  const { equipment: e, health, recent_maintenance, open_issues, parts, documents, low_stock_parts } = summary.data;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/equipment" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Equipment
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{e.name}</h1>
              <EquipmentStatusBadge status={e.status} />
            </div>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <CodePill>{e.serial_number}</CodePill> {e.equipment_type} · {e.location} · {e.department}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {hasRole(me?.role, "supervisor") && e.status !== "retired" && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" disabled={setStatus.isPending}>Change status <ChevronDown className="size-4" /></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Set status</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {(["active", "under maintenance"] as Status[]).map((s) => (
                    <DropdownMenuItem key={s} disabled={s === e.status} onClick={() => setStatus.mutate(s)} className="capitalize">
                      {s}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {hasRole(me?.role, "admin") && (
              <>
                <EquipmentFormDialog equipment={e} trigger={<Button variant="outline"><Pencil className="size-4" /> Edit</Button>} />
                {e.status !== "retired" && <RetireDialog id={e.id} name={e.name} />}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Equipment health</CardTitle></CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <HealthRing score={health.score} size={128} stroke={10} />
            <p className={cn("text-sm font-semibold capitalize", BAND_TEXT[health.band])}>{health.band}</p>
            <ul className="w-full space-y-2 text-sm">
              {health.deductions.length === 0 && (
                <li className="text-center text-muted-foreground">No deductions: everything is on track.</li>
              )}
              {health.deductions.map((d) => (
                <li key={d.reason} className="flex items-center justify-between gap-3 rounded-lg bg-muted/60 px-3 py-2">
                  <span>{d.reason}</span>
                  <span className="font-medium tabular-nums text-danger">−{d.points}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-3">
              {[
                ["Model", e.model_number ?? "—"], ["Type", e.equipment_type], ["Department", e.department],
                ["Location", e.location], ["Purchased", formatDate(e.purchased_at)],
                ["Warranty until", formatDate(e.warranty_expires_at)], ["Open issues", String(open_issues.length)],
                ["Low-stock parts", String(low_stock_parts)], ["Manuals", String(documents.length)],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="mt-0.5 font-medium">{value}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="maintenance">Maintenance</TabsTrigger>
          <TabsTrigger value="issues">Issues</TabsTrigger>
          <TabsTrigger value="parts">Parts</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Maintenance timeline</CardTitle></CardHeader>
            <CardContent><Timeline logs={recent_maintenance} /></CardContent>
          </Card>
          <div className="grid gap-4">
            <Card>
              <CardHeader><CardTitle>Open issues</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                {open_issues.length === 0 ? <p className="text-sm text-muted-foreground">No open issues.</p> : open_issues.map((i) => (
                  <div key={i.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={i.severity} />
                      {i.error_code && <CodePill>{i.error_code}</CodePill>}
                      <IssueStatusBadge status={i.status} />
                    </div>
                    <p className="mt-2 font-medium">{i.title}</p>
                    {i.description && <p className="text-sm text-muted-foreground">{i.description}</p>}
                  </div>
                ))}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Parts</CardTitle></CardHeader>
              <CardContent className="space-y-1.5 text-sm">
                {parts.length === 0 ? <p className="text-muted-foreground">No parts recorded.</p> : parts.map((p) => (
                  <div key={p.id} className="flex items-center justify-between gap-3">
                    <span>{p.part_name} {p.part_number && <CodePill>{p.part_number}</CodePill>}</span>
                    {p.quantity_in_stock <= p.reorder_threshold
                      ? <Pill tone="warning">Low stock · {p.quantity_in_stock} left</Pill>
                      : <span className="tabular-nums text-muted-foreground">{p.quantity_in_stock} in stock</span>}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="maintenance" className="mt-4"><MaintenanceTab id={id} /></TabsContent>
        <TabsContent value="issues" className="mt-4"><IssuesTab id={id} /></TabsContent>
        <TabsContent value="parts" className="mt-4"><PartsTable parts={parts} /></TabsContent>
        <TabsContent value="documents" className="mt-4"><DocumentsList documents={documents} /></TabsContent>
      </Tabs>
    </div>
  );
}

function Timeline({ logs }: { logs: Schemas["MaintenanceOut"][] }) {
  if (logs.length === 0) return <p className="text-sm text-muted-foreground">No maintenance on record.</p>;
  return (
    <ol className="relative space-y-5 border-l pl-5">
      {logs.map((log) => (
        <li key={log.id} className="relative">
          <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full bg-primary ring-4 ring-card" />
          <p className="text-sm font-medium">{log.log_type} · {log.description}</p>
          <p className="text-xs text-muted-foreground">
            {formatDate(log.performed_at)} by {log.performed_by}
            {log.next_scheduled_at && ` · next ${formatDate(log.next_scheduled_at)}`}
          </p>
        </li>
      ))}
    </ol>
  );
}

function MaintenanceTab({ id }: { id: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["equipment", id, "maintenance"],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/equipment/{equipment_id}/maintenance", { params: { path: { equipment_id: id } } })),
  });
  if (isPending) return <Skeleton className="h-40" />;
  if (!data?.length) return <EmptyState icon={Wrench} title="No maintenance logged yet" />;
  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">Date</TableHead><TableHead>Type</TableHead><TableHead>Work done</TableHead>
            <TableHead>By</TableHead><TableHead>Duration</TableHead><TableHead>Cost</TableHead>
            <TableHead className="pr-4">Next service</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((m) => (
            <TableRow key={m.id}>
              <TableCell className="pl-4">{formatDate(m.performed_at)}</TableCell>
              <TableCell>{m.log_type}</TableCell>
              <TableCell className="max-w-xs truncate">{m.description}</TableCell>
              <TableCell>{m.performed_by}</TableCell>
              <TableCell>{m.duration_minutes ? `${m.duration_minutes} min` : "—"}</TableCell>
              <TableCell>{currency(m.cost_usd)}</TableCell>
              <TableCell className="pr-4">{formatDate(m.next_scheduled_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function IssuesTab({ id }: { id: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["issues", { equipment_id: id }],
    queryFn: async () => unwrap(await api.GET("/api/v1/issues", { params: { query: { equipment_id: id } } })),
  });
  if (isPending) return <Skeleton className="h-40" />;
  if (!data?.length) return <EmptyState icon={CircleAlert} title="No issues reported for this machine" />;
  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">Issue</TableHead><TableHead>Code</TableHead><TableHead>Severity</TableHead>
            <TableHead>Status</TableHead><TableHead>Assignee</TableHead><TableHead className="pr-4 text-right">Reported</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((i) => (
            <TableRow key={i.id}>
              <TableCell className="pl-4 font-medium">{i.title}</TableCell>
              <TableCell>{i.error_code ? <CodePill>{i.error_code}</CodePill> : "—"}</TableCell>
              <TableCell><SeverityBadge severity={i.severity} /></TableCell>
              <TableCell><IssueStatusBadge status={i.status} /></TableCell>
              <TableCell>{i.assigned_to ?? <span className="text-muted-foreground">Unassigned</span>}</TableCell>
              <TableCell className="pr-4 text-right text-muted-foreground">{relativeTime(i.created_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function PartsTable({ parts }: { parts: Schemas["PartOut"][] }) {
  if (!parts.length) return <EmptyState icon={Package} title="No spare parts recorded for this machine" />;
  return (
    <Card className="p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="pl-4">Part</TableHead><TableHead>Part number</TableHead><TableHead>In stock</TableHead>
            <TableHead>Reorder at</TableHead><TableHead>Unit cost</TableHead><TableHead className="pr-4">Supplier</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {parts.map((p) => (
            <TableRow key={p.id}>
              <TableCell className="pl-4 font-medium">{p.part_name}</TableCell>
              <TableCell>{p.part_number ? <CodePill>{p.part_number}</CodePill> : "—"}</TableCell>
              <TableCell>
                <span className={cn("tabular-nums", p.quantity_in_stock <= p.reorder_threshold && "font-semibold text-warning")}>
                  {p.quantity_in_stock}
                </span>
              </TableCell>
              <TableCell className="tabular-nums">{p.reorder_threshold}</TableCell>
              <TableCell>{currency(p.unit_cost_usd)}</TableCell>
              <TableCell className="pr-4">{p.supplier ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function DocumentsList({ documents }: { documents: Schemas["DocumentOut"][] }) {
  if (!documents.length) {
    return <EmptyState icon={FileText} title="No manuals attached" description="Upload a manual on the Documents page and link it to this machine." />;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {documents.map((d) => (
        <Card key={d.id} className="flex-row items-center gap-3 p-4">
          <span className="flex size-10 items-center justify-center rounded-lg bg-info-soft text-info"><FileText className="size-5" /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium">{d.title}</p>
            <p className="text-xs text-muted-foreground">{d.doc_type}</p>
          </div>
          <Pill tone={d.is_indexed ? "success" : d.index_error ? "danger" : "warning"}>
            {d.is_indexed ? "Indexed" : d.index_error ? "Failed" : "Indexing"}
          </Pill>
          <Button asChild variant="ghost" size="icon" aria-label={`Download ${d.title}`}>
            <a href={`/api/backend${d.blob_url}`} target="_blank" rel="noreferrer"><Download className="size-4" /></a>
          </Button>
        </Card>
      ))}
    </div>
  );
}

function RetireDialog({ id, name }: { id: string; name: string }) {
  const queryClient = useQueryClient();
  const retire = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/equipment/{equipment_id}", { params: { path: { equipment_id: id } } });
      if (error || !response.ok) throw new Error("Could not retire this machine");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: keys.dashboard });
      toast.success(`${name} retired`);
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" className="text-danger"><Archive className="size-4" /> Retire</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Retire {name}?</DialogTitle>
          <DialogDescription>It stops counting toward health scores and due dates. Its full history is kept.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
          <DialogClose asChild><Button variant="destructive" onClick={() => retire.mutate()}>Retire</Button></DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
