"use client";

import { ArrowUp, Bot, Loader2, Sparkles, Stethoscope, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap } from "@/lib/api/client";
import { useEquipmentList } from "@/lib/queries";
import { cn } from "@/lib/utils";

import { useAssistant, type Mode, type Turn } from "./assistant-context";
import { AnswerView } from "./answer-view";

const ANY = "any";
const PROMPTS: Record<Mode, string[]> = {
  ask: ["What does E-47 mean on the lathe?", "How often should the slideways be lubricated?", "What is the lockout procedure?"],
  diagnose: ["Grinding noise at high spindle speed", "Warning light on the panel and parts running hot"],
};

export function AssistantPanel() {
  const { mode, setMode, equipmentId, setEquipmentId, turns, setTurns } = useAssistant();
  const { data: equipment = [] } = useEquipmentList();
  const names = new Map(equipment.map((e) => [e.id, e.name]));
  const endRef = useRef<HTMLDivElement>(null);
  const pending = turns.some((t) => t.pending);
  const needsMachine = mode === "diagnose" && !equipmentId;

  // Block body on purpose: an effect may only return a cleanup function, and scrollIntoView's
  // return value is not one.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function send(question: string) {
    const text = question.trim();
    if (text.length < 3 || pending || needsMachine) return;
    const id = Date.now();
    const turn: Turn = { id, mode, question: text, equipmentId, pending: true };
    setTurns((all) => [...all, turn]);
    try {
      const answer = mode === "diagnose"
        ? unwrap(await api.POST("/api/v1/ai/diagnose/{equipment_id}", { params: { path: { equipment_id: equipmentId! } }, body: { symptom: text } }))
        : unwrap(await api.POST("/api/v1/ai/ask", { body: { question: text, equipment_id: equipmentId ?? null } }));
      setTurns((all) => all.map((t) => (t.id === id ? { ...t, answer, pending: false } : t)));
    } catch (error) {
      setTurns((all) => all.map((t) => (t.id === id ? { ...t, error: (error as Error).message, pending: false } : t)));
    }
  }

  return (
    <div className="flex h-full flex-col">
      <SheetHeader className="border-b pb-3">
        <SheetTitle className="flex items-center gap-2"><Sparkles className="size-4 text-primary" /> AI assistant</SheetTitle>
        <SheetDescription>Answers come only from your uploaded manuals, with numbered sources.</SheetDescription>
        <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-muted p-1" role="tablist" aria-label="Assistant mode">
          {(["ask", "diagnose"] as Mode[]).map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} onClick={() => setMode(m)}
                    className={cn("flex items-center justify-center gap-1.5 rounded-md py-1.5 text-sm font-medium capitalize transition-colors",
                      mode === m ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground")}>
              {m === "ask" ? <Bot className="size-3.5" /> : <Stethoscope className="size-3.5" />} {m}
            </button>
          ))}
        </div>
        <Select value={equipmentId ?? ANY} onValueChange={(v) => setEquipmentId(v === ANY ? undefined : v)}>
          <SelectTrigger className="w-full" aria-label="Machine"><SelectValue /></SelectTrigger>
          <SelectContent className="max-h-72">
            {mode === "ask" && <SelectItem value={ANY}>Any machine (all manuals)</SelectItem>}
            {mode === "diagnose" && !equipmentId && <SelectItem value={ANY} disabled>Choose the machine to diagnose</SelectItem>}
            {equipment.filter((e) => e.status !== "retired").map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
          </SelectContent>
        </Select>
        {mode === "diagnose" && (
          <p className="text-xs text-muted-foreground">Diagnose also uses the machine&apos;s health score, recent maintenance and open issues.</p>
        )}
      </SheetHeader>

      <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="space-y-3 pt-6 text-center">
            <Sparkles className="mx-auto size-8 text-primary/60" />
            <p className="text-sm text-muted-foreground">{mode === "ask" ? "Ask about an error code, a procedure or a spec." : "Describe the symptom you see."}</p>
            <div className="flex flex-col items-center gap-2">
              {PROMPTS[mode].map((p) => (
                <button key={p} onClick={() => send(p)} disabled={needsMachine}
                        className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:border-primary/50 hover:text-foreground disabled:opacity-50">{p}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="space-y-2">
            <div className="ml-8 rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
              {t.question}
              <p className="mt-0.5 text-[10px] opacity-80">{t.mode === "diagnose" ? "Diagnose" : "Ask"}{t.equipmentId ? ` · ${names.get(t.equipmentId) ?? "machine"}` : ""}</p>
            </div>
            <div className="mr-2 rounded-2xl rounded-tl-sm border bg-card p-3">
              {t.pending && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Searching the manuals…</p>}
              {t.error && <p className="text-sm text-danger">{t.error}</p>}
              {t.answer && <AnswerView answer={t.answer} turnId={t.id} />}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <form className="border-t p-3" onSubmit={(e) => { e.preventDefault(); const f = e.currentTarget; send(new FormData(f).get("q") as string); f.reset(); }}>
        <div className="relative">
          <Textarea name="q" rows={2} placeholder={mode === "ask" ? "Ask a question…" : "Describe the symptom…"} className="resize-none pr-11"
                    disabled={needsMachine} maxLength={1000}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
          <Button type="submit" size="icon" className="absolute right-2 bottom-2 size-7" disabled={pending || needsMachine} aria-label="Send">
            <ArrowUp className="size-4" />
          </Button>
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>Enter to send · Shift+Enter for a new line</span>
          {turns.length > 0 && (
            <button type="button" onClick={() => setTurns([])} className="flex items-center gap-1 hover:text-foreground"><Trash2 className="size-3" /> Clear</button>
          )}
        </div>
      </form>
    </div>
  );
}
