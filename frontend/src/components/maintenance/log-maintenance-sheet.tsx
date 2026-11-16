"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EquipmentSelect } from "@/components/domain/equipment-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { LOG_TYPES } from "@/lib/enums";

/** Any role can log work. "Performed by" defaults to the signed-in user (the API fills it in). */
export function LogMaintenanceSheet({ trigger, equipmentId }: { trigger: React.ReactNode; equipmentId?: string }) {
  const [open, setOpen] = useState(false);
  const [machine, setMachine] = useState(equipmentId ?? "");
  const [logType, setLogType] = useState("");
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: async (body: Schemas["MaintenanceIn"]) =>
      unwrap(await api.POST("/api/v1/equipment/{equipment_id}/maintenance", { params: { path: { equipment_id: machine } }, body })),
    onSuccess: () => {
      for (const key of [["maintenance"], ["equipment"], ["dashboard"]]) queryClient.invalidateQueries({ queryKey: key });
      toast.success("Maintenance logged");
      setOpen(false);
      setLogType("");
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{trigger}</SheetTrigger>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Log maintenance</SheetTitle>
          <SheetDescription>Record work done. Setting the next service date drives the upcoming and overdue lists.</SheetDescription>
        </SheetHeader>
        <form
          id="log-maintenance"
          className="grid gap-4 px-4"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            const text = (k: string) => String(f.get(k) ?? "").trim() || null;
            const num = (k: string) => (text(k) === null ? null : Number(text(k)));
            save.mutate({
              log_type: logType as Schemas["LogType"], performed_at: text("performed_at")!, description: text("description")!,
              duration_minutes: num("duration_minutes"), cost_usd: num("cost_usd"),
              next_scheduled_at: text("next_scheduled_at"), performed_by: text("performed_by"),
            });
          }}
        >
          <div className="space-y-2"><Label>Machine</Label><EquipmentSelect value={machine} onChange={setMachine} /></div>
          <div className="space-y-2">
            <Label>Type of work</Label>
            <Select value={logType} onValueChange={setLogType}>
              <SelectTrigger className="w-full"><SelectValue placeholder="Scheduled, inspection, repair…" /></SelectTrigger>
              <SelectContent className="max-h-72">{LOG_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DateAndCostFields />
          <div className="space-y-2"><Label htmlFor="description">Work done</Label><Textarea id="description" name="description" rows={3} required /></div>
          <div className="space-y-2">
            <Label htmlFor="performed_by">Performed by (optional)</Label>
            <Input id="performed_by" name="performed_by" maxLength={100} placeholder="Leave empty if it was you, or name a contractor" />
          </div>
        </form>
        <SheetFooter>
          <Button type="submit" form="log-maintenance" disabled={save.isPending || !machine || !logType}>
            {save.isPending && <Loader2 className="size-4 animate-spin" />} Save log
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

/**
 * Rendered only while the sheet is open (Radix mounts sheet content on open), so "today" is read in the
 * browser at the moment of use, never baked into the server prerender.
 */
function DateAndCostFields() {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label htmlFor="performed_at">Performed on</Label>
        <Input id="performed_at" name="performed_at" type="date" defaultValue={today} max={today} required />
      </div>
      <div className="space-y-2">
        <Label htmlFor="next_scheduled_at">Next service</Label>
        <Input id="next_scheduled_at" name="next_scheduled_at" type="date" min={today} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="duration_minutes">Duration (min)</Label>
        <Input id="duration_minutes" name="duration_minutes" type="number" min={1} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="cost_usd">Cost (USD)</Label>
        <Input id="cost_usd" name="cost_usd" type="number" min={0} step="0.01" />
      </div>
    </div>
  );
}
