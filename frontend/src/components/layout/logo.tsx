import { Cog } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
        <Cog className="size-4.5" strokeWidth={2.25} />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">EquipTrack</span>
    </div>
  );
}
