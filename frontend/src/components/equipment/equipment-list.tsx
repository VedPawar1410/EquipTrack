"use client";

import { Factory, Plus, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EquipmentStatusBadge } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { HealthBar } from "@/components/domain/health-ring";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { hasRole, useMe } from "@/lib/auth";
import { EQUIPMENT_STATUSES, EQUIPMENT_TYPES } from "@/lib/enums";
import { formatDate } from "@/lib/format";
import { useEquipmentList, useHealthMap } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { EquipmentFormDialog } from "./equipment-form-dialog";

const ALL = "all";

export function EquipmentList() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { data: me } = useMe();
  const filters = {
    search: params.get("search") ?? undefined, status: params.get("status") ?? undefined,
    department: params.get("department") ?? undefined, type: params.get("type") ?? undefined,
  };
  const { data: equipment, isPending } = useEquipmentList(filters);
  const { data: all = [] } = useEquipmentList();
  const { data: health } = useHealthMap();
  const departments = [...new Set(all.map((e) => e.department))].sort();

  // Filters live in the URL, so a filtered view can be bookmarked or shared (and the top-bar search lands here).
  function setFilter(name: string, value?: string) {
    const next = new URLSearchParams(params);
    if (value && value !== ALL) next.set(name, value); else next.delete(name);
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`);
  }
  const [search, setSearch] = useState(filters.search ?? "");
  useEffect(() => {
    const id = setTimeout(() => { if (search !== (filters.search ?? "")) setFilter("search", search.trim()); }, 300);
    return () => clearTimeout(id);
  }); // debounce: re-armed on every render, fires 300 ms after typing stops

  const today = new Date().toISOString().slice(0, 10);
  return (
    <>
      <PageHeader
        title="Equipment"
        description="Every machine in the plant, its status and health."
        actions={hasRole(me?.role, "admin") && (
          <EquipmentFormDialog trigger={<Button><Plus className="size-4" /> Add equipment</Button>} />
        )}
      />
      <Card className="gap-0 overflow-hidden p-0">
        <div className="flex flex-wrap items-center gap-2 border-b p-3">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name…" className="pl-9" aria-label="Search equipment by name" />
          </div>
          <FilterSelect label="Status" value={filters.status} options={EQUIPMENT_STATUSES} onChange={(v) => setFilter("status", v)} />
          <FilterSelect label="Department" value={filters.department} options={departments} onChange={(v) => setFilter("department", v)} />
          <FilterSelect label="Type" value={filters.type} options={EQUIPMENT_TYPES} onChange={(v) => setFilter("type", v)} />
        </div>
        {isPending ? (
          <div className="space-y-2 p-4">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !equipment?.length ? (
          <div className="p-6"><EmptyState icon={Factory} title="No equipment matches" description="Try clearing a filter or searching for something else." /></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Name</TableHead><TableHead>Type</TableHead><TableHead>Location</TableHead>
                <TableHead>Department</TableHead><TableHead>Status</TableHead><TableHead>Health</TableHead><TableHead className="pr-4">Warranty</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {equipment.map((e) => {
                const score = health?.get(e.id)?.score;
                const expired = e.warranty_expires_at && e.warranty_expires_at < today;
                return (
                  <TableRow key={e.id} className="cursor-pointer" onClick={() => router.push(`/equipment/${e.id}`)}>
                    <TableCell className="pl-4">
                      <Link href={`/equipment/${e.id}`} className="font-medium hover:underline" onClick={(ev) => ev.stopPropagation()}>{e.name}</Link>
                      <p className="font-mono text-xs text-muted-foreground">{e.serial_number}</p>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{e.equipment_type}</TableCell>
                    <TableCell>{e.location}</TableCell>
                    <TableCell>{e.department}</TableCell>
                    <TableCell><EquipmentStatusBadge status={e.status} /></TableCell>
                    <TableCell>{score !== undefined ? <HealthBar score={score} /> : <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell className={cn("pr-4", expired ? "text-danger" : "text-muted-foreground")}>
                      {formatDate(e.warranty_expires_at)}{expired && " · expired"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
        {equipment && equipment.length > 0 && (
          <p className="border-t px-4 py-2.5 text-xs text-muted-foreground">{equipment.length} machine{equipment.length === 1 ? "" : "s"}</p>
        )}
      </Card>
    </>
  );
}

function FilterSelect({ label, value, options, onChange }: { label: string; value?: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <Select value={value ?? ALL} onValueChange={onChange}>
      <SelectTrigger className="w-44 capitalize" aria-label={`Filter by ${label.toLowerCase()}`}><SelectValue /></SelectTrigger>
      <SelectContent className="max-h-72">
        <SelectItem value={ALL}>All {label.toLowerCase()}{label.endsWith("s") ? "es" : "s"}</SelectItem>
        {options.map((o) => <SelectItem key={o} value={o} className="capitalize">{o}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
