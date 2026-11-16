import { cn } from "@/lib/utils";

const TONE = {
  success: "bg-success-soft text-success ring-success/20",
  warning: "bg-warning-soft text-warning ring-warning/20",
  danger: "bg-danger-soft text-danger ring-danger/20",
  info: "bg-info-soft text-info ring-info/20",
  neutral: "bg-muted text-muted-foreground ring-border",
} as const;
type Tone = keyof typeof TONE;

export function Pill({ tone, children, className }: { tone: Tone; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONE[tone], className)}>
      {children}
    </span>
  );
}

const EQUIPMENT_TONE: Record<string, Tone> = { active: "success", "under maintenance": "warning", retired: "neutral" };
export function EquipmentStatusBadge({ status }: { status: string }) {
  return <Pill tone={EQUIPMENT_TONE[status] ?? "neutral"} className="capitalize">{status}</Pill>;
}

const SEVERITY_TONE: Record<string, Tone> = { Critical: "danger", High: "warning", Medium: "info", Low: "neutral" };
export function SeverityBadge({ severity }: { severity: string }) {
  return <Pill tone={SEVERITY_TONE[severity] ?? "neutral"}>{severity}</Pill>;
}

const ISSUE_TONE: Record<string, Tone> = { Open: "danger", "In Progress": "info", Resolved: "success", Closed: "neutral" };
export function IssueStatusBadge({ status }: { status: string }) {
  return <Pill tone={ISSUE_TONE[status] ?? "neutral"}>{status}</Pill>;
}

/** Error codes and part numbers: monospace, so E-47 and TL-ENC-04 read exactly. */
export function CodePill({ children }: { children: React.ReactNode }) {
  return <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[11px] font-medium text-foreground/80">{children}</code>;
}
