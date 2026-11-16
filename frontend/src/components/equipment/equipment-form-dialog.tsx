"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { EQUIPMENT_TYPES } from "@/lib/enums";

type Equipment = Schemas["EquipmentOut"];

/** Create (admin) or edit (admin) a machine. The API validates everything again; this just guides input. */
export function EquipmentFormDialog({ equipment, trigger }: { equipment?: Equipment; trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState(equipment?.equipment_type ?? "");
  const router = useRouter();
  const queryClient = useQueryClient();
  const editing = Boolean(equipment);

  const save = useMutation({
    mutationFn: async (body: Schemas["EquipmentIn"]) =>
      editing
        ? unwrap(await api.PUT("/api/v1/equipment/{equipment_id}", { params: { path: { equipment_id: equipment!.id } }, body }))
        : unwrap(await api.POST("/api/v1/equipment", { body })),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ["equipment"] });
      toast.success(editing ? "Equipment updated" : `${saved.name} added`);
      setOpen(false);
      if (!editing) router.push(`/equipment/${saved.id}`);
    },
    onError: (error) => toast.error(error.message),
  });

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const text = (name: string) => (f.get(name)?.toString().trim() || null);
    save.mutate({
      name: text("name")!, serial_number: text("serial_number")!, model_number: text("model_number"),
      equipment_type: type as Schemas["EquipmentType"], location: text("location")!, department: text("department")!,
      purchased_at: text("purchased_at"), warranty_expires_at: text("warranty_expires_at"),
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit equipment" : "Add equipment"}</DialogTitle>
          <DialogDescription>{editing ? "Update this machine's master data." : "Register a new machine in the plant."}</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" name="name" defaultValue={equipment?.name} required className="sm:col-span-2" maxLength={100} />
          <Field label="Serial number" name="serial_number" defaultValue={equipment?.serial_number} required maxLength={100} />
          <Field label="Model number" name="model_number" defaultValue={equipment?.model_number ?? ""} maxLength={50} />
          <div className="space-y-2 sm:col-span-2">
            <Label>Type</Label>
            <Select value={type} onValueChange={setType} required>
              <SelectTrigger className="w-full"><SelectValue placeholder="Choose a type" /></SelectTrigger>
              <SelectContent className="max-h-72">{EQUIPMENT_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Field label="Location" name="location" defaultValue={equipment?.location} required maxLength={100} />
          <Field label="Department" name="department" defaultValue={equipment?.department} required maxLength={100} />
          <Field label="Purchased" name="purchased_at" type="date" defaultValue={equipment?.purchased_at ?? ""} />
          <Field label="Warranty expires" name="warranty_expires_at" type="date" defaultValue={equipment?.warranty_expires_at ?? ""} />
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending || !type}>
              {save.isPending && <Loader2 className="size-4 animate-spin" />}
              {editing ? "Save changes" : "Add equipment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, name, className, ...props }: { label: string; name: string; className?: string } & React.ComponentProps<"input">) {
  return (
    <div className={`space-y-2 ${className ?? ""}`}>
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} name={name} {...props} />
    </div>
  );
}
