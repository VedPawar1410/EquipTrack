"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Minus, Package, Plus, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { CodePill, Pill } from "@/components/domain/badges";
import { EmptyState } from "@/components/domain/empty-state";
import { EquipmentSelect } from "@/components/domain/equipment-select";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { hasRole, useMe } from "@/lib/auth";
import { currency } from "@/lib/format";
import { useEquipmentNames } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Part = Schemas["PartOut"];

export function PartsPage() {
  const { data: me } = useMe();
  const names = useEquipmentNames();
  const [adjusting, setAdjusting] = useState<{ part: Part; direction: 1 | -1 } | null>(null);
  const { data: parts, isPending } = useQuery({
    queryKey: ["parts"],
    queryFn: async () => unwrap(await api.GET("/api/v1/parts")),
  });
  const supervisor = hasRole(me?.role, "supervisor");
  const low = (parts ?? []).filter((p) => p.quantity_in_stock <= p.reorder_threshold);
  return (
    <>
      <PageHeader title="Parts" description="Spare parts stock and reorder levels across every machine."
                  actions={supervisor && <AddPartDialog />} />
      {low.length > 0 && (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
          <TriangleAlert className="size-4" /> {low.length} part{low.length === 1 ? " is" : "s are"} at or below the reorder level.
        </div>
      )}
      <Card className="gap-0 p-0">
        {isPending ? <div className="p-4"><Skeleton className="h-60" /></div> : !parts?.length ? (
          <div className="p-6"><EmptyState icon={Package} title="No spare parts recorded yet" /></div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-4">Part</TableHead><TableHead>Machine</TableHead><TableHead>In stock</TableHead>
                <TableHead>Reorder at</TableHead><TableHead>Unit cost</TableHead><TableHead>Supplier</TableHead>
                <TableHead className="pr-4 text-right">Stock</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {parts.map((p) => {
                const isLow = p.quantity_in_stock <= p.reorder_threshold;
                const fill = Math.min(100, (p.quantity_in_stock / Math.max(p.reorder_threshold * 3, 1)) * 100);
                return (
                  <TableRow key={p.id}>
                    <TableCell className="pl-4">
                      <p className="font-medium">{p.part_name}</p>
                      {p.part_number && <CodePill>{p.part_number}</CodePill>}
                    </TableCell>
                    <TableCell><Link href={`/equipment/${p.equipment_id}`} className="hover:underline">{names.get(p.equipment_id) ?? "—"}</Link></TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                          <div className={cn("h-full rounded-full", isLow ? "bg-warning" : "bg-success")} style={{ width: `${fill}%` }} />
                        </div>
                        <span className={cn("tabular-nums", isLow && "font-semibold text-warning")}>{p.quantity_in_stock}</span>
                        {isLow && <Pill tone="warning">Low stock</Pill>}
                      </div>
                    </TableCell>
                    <TableCell className="tabular-nums">{p.reorder_threshold}</TableCell>
                    <TableCell>{currency(p.unit_cost_usd)}</TableCell>
                    <TableCell>{p.supplier ?? "—"}</TableCell>
                    <TableCell className="pr-4">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="outline" disabled={p.quantity_in_stock === 0}
                                onClick={() => setAdjusting({ part: p, direction: -1 })}><Minus className="size-3.5" /> Use</Button>
                        {supervisor && (
                          <Button size="sm" variant="outline" onClick={() => setAdjusting({ part: p, direction: 1 })}><Plus className="size-3.5" /> Restock</Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
      <AdjustStockDialog value={adjusting} onClose={() => setAdjusting(null)} />
    </>
  );
}

function AdjustStockDialog({ value, onClose }: { value: { part: Part; direction: 1 | -1 } | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const adjust = useMutation({
    mutationFn: async (amount: number) =>
      unwrap(await api.PATCH("/api/v1/parts/{part_id}/quantity", {
        params: { path: { part_id: value!.part.id } }, body: { quantity_change: amount * value!.direction },
      })),
    onSuccess: (p) => {
      for (const key of [["parts"], ["equipment"], ["dashboard"]]) queryClient.invalidateQueries({ queryKey: key });
      toast.success(`${p.part_name}: ${p.quantity_in_stock} in stock`);
      onClose();
    },
    onError: (error) => toast.error(error.message),
  });
  const consuming = value?.direction === -1;
  return (
    <Dialog open={value !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>{consuming ? "Use parts" : "Restock"}</DialogTitle>
          <DialogDescription>{value?.part.part_name} · {value?.part.quantity_in_stock} in stock</DialogDescription>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); adjust.mutate(Number(new FormData(e.currentTarget).get("amount"))); }} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="amount">{consuming ? "How many did you take?" : "How many arrived?"}</Label>
            <Input id="amount" name="amount" type="number" min={1} max={consuming ? value?.part.quantity_in_stock : undefined} defaultValue={1} required autoFocus />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={adjust.isPending}>{adjust.isPending && <Loader2 className="size-4 animate-spin" />}{consuming ? "Use" : "Restock"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AddPartDialog() {
  const [open, setOpen] = useState(false);
  const [machine, setMachine] = useState("");
  const queryClient = useQueryClient();
  const add = useMutation({
    mutationFn: async (body: Schemas["PartIn"]) =>
      unwrap(await api.POST("/api/v1/equipment/{equipment_id}/parts", { params: { path: { equipment_id: machine } }, body })),
    onSuccess: (p) => { queryClient.invalidateQueries({ queryKey: ["parts"] }); queryClient.invalidateQueries({ queryKey: ["equipment"] }); toast.success(`${p.part_name} added`); setOpen(false); },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button><Plus className="size-4" /> Add part</Button></DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Add a spare part</DialogTitle><DialogDescription>Track stock for a part a machine needs.</DialogDescription></DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const text = (k: string) => String(f.get(k) ?? "").trim() || null;
            add.mutate({
              part_name: text("part_name")!, part_number: text("part_number"), quantity_in_stock: Number(text("quantity_in_stock") ?? 0),
              reorder_threshold: Number(text("reorder_threshold") ?? 2), unit_cost_usd: text("unit_cost_usd") ? Number(text("unit_cost_usd")) : null,
              supplier: text("supplier"),
            });
          }}
        >
          <div className="space-y-2 sm:col-span-2"><Label>Machine</Label><EquipmentSelect value={machine} onChange={setMachine} /></div>
          <div className="space-y-2 sm:col-span-2"><Label htmlFor="part_name">Part name</Label><Input id="part_name" name="part_name" required maxLength={100} /></div>
          <div className="space-y-2"><Label htmlFor="part_number">Part number</Label><Input id="part_number" name="part_number" maxLength={100} className="font-mono" /></div>
          <div className="space-y-2"><Label htmlFor="supplier">Supplier</Label><Input id="supplier" name="supplier" maxLength={100} /></div>
          <div className="space-y-2"><Label htmlFor="quantity_in_stock">In stock</Label><Input id="quantity_in_stock" name="quantity_in_stock" type="number" min={0} defaultValue={0} /></div>
          <div className="space-y-2"><Label htmlFor="reorder_threshold">Reorder at</Label><Input id="reorder_threshold" name="reorder_threshold" type="number" min={0} defaultValue={2} /></div>
          <div className="space-y-2"><Label htmlFor="unit_cost_usd">Unit cost (USD)</Label><Input id="unit_cost_usd" name="unit_cost_usd" type="number" min={0} step="0.01" /></div>
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={add.isPending || !machine}>Add part</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
