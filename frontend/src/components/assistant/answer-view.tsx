"use client";

import { FileText } from "lucide-react";
import { Fragment, useState } from "react";

import { Pill } from "@/components/domain/badges";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Answer = Schemas["AIAnswer"];

/**
 * Turns the model's text into React elements: **bold**, numbered/bulleted lines, and [n] citation chips.
 * Deliberately NOT dangerouslySetInnerHTML: LLM output is untrusted text, and rendering it as HTML would
 * let a manipulated answer inject markup or scripts (XSS).
 */
function Inline({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+\])/g).filter(Boolean);
  return (
    <>
      {parts.map((part, i) => {
        const cite = part.match(/^\[(\d+)\]$/);
        if (cite) {
          const n = Number(cite[1]);
          return (
            <button key={i} type="button" onClick={() => onCite(n)}
                    className="mx-0.5 inline-flex h-4.5 min-w-4.5 items-center justify-center rounded bg-primary/10 px-1 align-[1px] text-[10px] font-semibold text-primary hover:bg-primary/20"
                    aria-label={`Show source ${n}`}>
              {n}
            </button>
          );
        }
        if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}

function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
        const bullet = line.match(/^[-*•]\s+(.*)$/);
        if (numbered) {
          return (
            <div key={i} className="flex gap-2">
              <span className="w-4 shrink-0 text-right font-medium text-muted-foreground tabular-nums">{numbered[1]}.</span>
              <span><Inline text={numbered[2]} onCite={onCite} /></span>
            </div>
          );
        }
        if (bullet) return <div key={i} className="flex gap-2"><span className="text-muted-foreground">•</span><span><Inline text={bullet[1]} onCite={onCite} /></span></div>;
        return <p key={i}><Inline text={line} onCite={onCite} /></p>;
      })}
    </div>
  );
}

const MODE_LABEL = { llm: null, extractive: "No AI model available: showing the manual excerpts", not_found: null } as const;

export function AnswerView({ answer, turnId }: { answer: Answer; turnId: number }) {
  const [highlight, setHighlight] = useState<number | null>(null);
  const cite = (n: number) => {
    setHighlight(n);
    document.getElementById(`source-${turnId}-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  return (
    <div className="space-y-3">
      {MODE_LABEL[answer.mode] && <p className="text-xs text-warning">{MODE_LABEL[answer.mode]}</p>}
      <AnswerText text={answer.answer} onCite={cite} />
      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
        {answer.confidence !== "none" && (
          <Pill tone={answer.confidence === "high" ? "success" : "warning"} className="capitalize">{answer.confidence} confidence</Pill>
        )}
        {answer.model && <span className="font-mono">{answer.model}</span>}
        <span>· {answer.latency_ms} ms</span>
      </div>
      {answer.sources.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Sources</p>
          {answer.sources.map((s) => (
            <div key={s.n} id={`source-${turnId}-${s.n}`}
                 className={cn("rounded-lg border p-2.5 text-xs transition-colors", highlight === s.n && "border-primary bg-primary/5", !s.cited && "opacity-75")}>
              <div className="flex items-center gap-2">
                <span className="flex size-4.5 items-center justify-center rounded bg-primary/10 text-[10px] font-semibold text-primary">{s.n}</span>
                <FileText className="size-3.5 text-muted-foreground" />
                <a href={`/api/backend/api/v1/documents/${s.document_id}/file`} target="_blank" rel="noreferrer" className="truncate font-medium hover:underline">{s.title}</a>
                {s.page && <span className="text-muted-foreground">p. {s.page}</span>}
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {s.matched_by.map((m) => <Pill key={m} tone="info" className="px-1.5 py-0 text-[10px]">{m}</Pill>)}
                {!s.cited && <Pill tone="neutral" className="px-1.5 py-0 text-[10px]">not cited</Pill>}
              </div>
              <p className="mt-1.5 line-clamp-3 text-muted-foreground">{s.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
