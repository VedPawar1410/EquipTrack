"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import type { Schemas } from "@/lib/api/client";

export type Mode = "ask" | "diagnose";
export type Turn = {
  id: number; mode: Mode; question: string; equipmentId?: string;
  answer?: Schemas["AIAnswer"]; error?: string; pending: boolean;
};

type AssistantState = {
  open: boolean; setOpen: (open: boolean) => void;
  mode: Mode; setMode: (mode: Mode) => void;
  equipmentId?: string; setEquipmentId: (id?: string) => void;
  turns: Turn[]; setTurns: React.Dispatch<React.SetStateAction<Turn[]>>;
  /** Open the panel, optionally preset to a mode and machine (e.g. from a machine's page). */
  openAssistant: (preset?: { mode?: Mode; equipmentId?: string }) => void;
};

const AssistantContext = createContext<AssistantState | null>(null);

/** Lives in the app layout, so the conversation survives closing the panel and moving between pages. */
export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("ask");
  const [equipmentId, setEquipmentId] = useState<string>();
  const [turns, setTurns] = useState<Turn[]>([]);
  const openAssistant = useCallback((preset?: { mode?: Mode; equipmentId?: string }) => {
    if (preset?.mode) setMode(preset.mode);
    if (preset?.equipmentId) setEquipmentId(preset.equipmentId);
    setOpen(true);
  }, []);
  const value = useMemo(
    () => ({ open, setOpen, mode, setMode, equipmentId, setEquipmentId, turns, setTurns, openAssistant }),
    [open, mode, equipmentId, turns, openAssistant],
  );
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant() {
  const context = useContext(AssistantContext);
  if (!context) throw new Error("useAssistant must be used inside <AssistantProvider>");
  return context;
}
