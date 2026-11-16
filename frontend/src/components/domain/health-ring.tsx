import { cn } from "@/lib/utils";

export function bandOf(score: number) {
  return score >= 80 ? "good" : score >= 50 ? "fair" : "poor";
}

const BAND_COLOR = { good: "text-success", fair: "text-warning", poor: "text-danger" } as const;

/** A circular 0-100 gauge, coloured by health band (good >= 80, fair >= 50, poor below). */
export function HealthRing({ score, size = 48, stroke = 5, showLabel = false }: {
  score: number; size?: number; stroke?: number; showLabel?: boolean;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const band = bandOf(score);
  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}
         role="img" aria-label={`Health ${score} out of 100, ${band}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-muted" />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} strokeLinecap="round"
                className={cn("stroke-current transition-[stroke-dashoffset] duration-700", BAND_COLOR[band])}
                strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)} />
      </svg>
      <span className={cn("absolute font-semibold tabular-nums", size >= 96 ? "text-2xl" : "text-xs")}>{score}</span>
      {showLabel && <span className="sr-only">{band}</span>}
    </div>
  );
}

export function HealthBar({ score }: { score: number }) {
  const band = bandOf(score);
  const fill = { good: "bg-success", fair: "bg-warning", poor: "bg-danger" }[band];
  return (
    <div className="flex items-center gap-2" aria-label={`Health ${score} out of 100`}>
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full", fill)} style={{ width: `${score}%` }} />
      </div>
      <span className="w-7 text-xs tabular-nums text-muted-foreground">{score}</span>
    </div>
  );
}
