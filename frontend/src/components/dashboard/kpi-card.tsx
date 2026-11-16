import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({ label, value, hint, icon: Icon, tone = "neutral", href }: {
  label: string; value: number | string; hint?: string; icon: LucideIcon;
  tone?: "neutral" | "danger" | "warning" | "success"; href?: string;
}) {
  const iconTone = { neutral: "bg-info-soft text-info", danger: "bg-danger-soft text-danger",
    warning: "bg-warning-soft text-warning", success: "bg-success-soft text-success" }[tone];
  const body = (
    <Card className="gap-0 p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <p className="text-sm text-muted-foreground">{label}</p>
        <span className={cn("flex size-8 items-center justify-center rounded-lg", iconTone)}><Icon className="size-4" /></span>
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  );
  return href ? <Link href={href} className="rounded-xl focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">{body}</Link> : body;
}
