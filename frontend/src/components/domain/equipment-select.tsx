"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useEquipmentList } from "@/lib/queries";

/** Pick a machine (retired machines are left out: nothing new should be logged against them). */
export function EquipmentSelect({ value, onChange, id }: { value: string; onChange: (id: string) => void; id?: string }) {
  const { data = [] } = useEquipmentList();
  const machines = data.filter((e) => e.status !== "retired").sort((a, b) => a.name.localeCompare(b.name));
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full"><SelectValue placeholder="Choose a machine" /></SelectTrigger>
      <SelectContent className="max-h-72">
        {machines.map((m) => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
