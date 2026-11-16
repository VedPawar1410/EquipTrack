"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EquipmentSelect } from "@/components/domain/equipment-select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { SEVERITIES } from "@/lib/enums";

/** Any role can report an issue; the reporter is always the signed-in user (set by the API). */
export function ReportIssueDialog({ trigger, equipmentId }: { trigger: React.ReactNode; equipmentId?: string }) {
  const [open, setOpen] = useState(false);
  const [machine, setMachine] = useState(equipmentId ?? "");
  const [severity, setSeverity] = useState("");
  const queryClient = useQueryClient();
  const report = useMutation({
    mutationFn: async (body: Schemas["IssueIn"]) => unwrap(await api.POST("/api/v1/issues", { body })),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Issue reported");
      setOpen(false);
      setSeverity("");
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Report an issue</DialogTitle>
          <DialogDescription>Describe what you see. Add the machine&apos;s error code if it shows one: the AI assistant uses it.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            report.mutate({
              equipment_id: machine, title: String(f.get("title")).trim(), severity: severity as Schemas["Severity"],
              error_code: String(f.get("error_code") ?? "").trim() || null,
              description: String(f.get("description") ?? "").trim() || null,
            });
          }}
        >
          <div className="space-y-2 sm:col-span-2"><Label>Machine</Label><EquipmentSelect value={machine} onChange={setMachine} /></div>
          <div className="space-y-2 sm:col-span-2"><Label htmlFor="title">Title</Label><Input id="title" name="title" required maxLength={200} placeholder="e.g. Spindle vibration above 3000 RPM" /></div>
          <div className="space-y-2">
            <Label>Severity</Label>
            <Select value={severity} onValueChange={setSeverity}>
              <SelectTrigger className="w-full"><SelectValue placeholder="How bad is it?" /></SelectTrigger>
              <SelectContent>{SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2"><Label htmlFor="error_code">Error code (optional)</Label><Input id="error_code" name="error_code" maxLength={50} placeholder="E-47" className="font-mono" /></div>
          <div className="space-y-2 sm:col-span-2"><Label htmlFor="description">Details (optional)</Label><Textarea id="description" name="description" rows={3} /></div>
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={report.isPending || !machine || !severity}>
              {report.isPending && <Loader2 className="size-4 animate-spin" />} Report issue
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
