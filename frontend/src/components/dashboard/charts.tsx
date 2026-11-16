"use client";

import { Bar, BarChart, Cell, Pie, PieChart, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";

const STATUS_COLORS: Record<string, string> = {
  active: "var(--chart-2)", "under maintenance": "var(--chart-3)", retired: "var(--chart-5)",
};
const SEVERITY_COLORS: Record<string, string> = {
  Critical: "var(--chart-4)", High: "var(--chart-3)", Medium: "var(--chart-1)", Low: "var(--chart-5)",
};

export function StatusDonut({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data).map(([status, count]) => ({ status, count, fill: STATUS_COLORS[status] }));
  const config = Object.fromEntries(rows.map((r) => [r.status, { label: r.status, color: r.fill }])) satisfies ChartConfig;
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  return (
    <div className="flex items-center gap-6">
      <ChartContainer config={config} className="aspect-square h-40">
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent nameKey="status" hideLabel />} />
          <Pie data={rows} dataKey="count" nameKey="status" innerRadius={48} outerRadius={70} strokeWidth={2} paddingAngle={2}>
            {rows.map((r) => <Cell key={r.status} fill={r.fill} />)}
          </Pie>
        </PieChart>
      </ChartContainer>
      <ul className="space-y-2 text-sm">
        {rows.map((r) => (
          <li key={r.status} className="flex items-center gap-2">
            <span className="size-2.5 rounded-full" style={{ background: r.fill }} />
            <span className="capitalize text-muted-foreground">{r.status}</span>
            <span className="ml-auto pl-4 font-medium tabular-nums">{r.count}</span>
          </li>
        ))}
        <li className="border-t pt-2 text-xs text-muted-foreground">{total} machines</li>
      </ul>
    </div>
  );
}

export function SeverityBars({ data }: { data: Record<string, number> }) {
  const rows = ["Critical", "High", "Medium", "Low"].map((severity) => ({ severity, count: data[severity] ?? 0 }));
  const config = { count: { label: "Open issues" } } satisfies ChartConfig;
  return (
    <ChartContainer config={config} className="h-44 w-full">
      <BarChart data={rows} margin={{ left: -20, right: 8 }}>
        <XAxis dataKey="severity" tickLine={false} axisLine={false} fontSize={12} />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} />
        <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
        <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={44}>
          {rows.map((r) => <Cell key={r.severity} fill={SEVERITY_COLORS[r.severity]} />)}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
