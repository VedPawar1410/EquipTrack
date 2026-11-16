"use client";

import { Sparkles } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { useAssistant } from "./assistant-context";
import { AssistantPanel } from "./assistant-panel";

/** The floating button (bottom right, every page) and the side panel it opens. Shortcut: Cmd/Ctrl + J. */
export function AssistantLauncher() {
  const { open, setOpen, openAssistant } = useAssistant();
  const pathname = usePathname();
  // On a machine's page, start with that machine selected.
  const machineOnPage = pathname.match(/^\/equipment\/([0-9a-f-]{36})/)?.[1];

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        if (open) setOpen(false); else openAssistant({ equipmentId: machineOnPage });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen, openAssistant, machineOnPage]);

  return (
    <>
      {!open && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button size="icon" onClick={() => openAssistant({ equipmentId: machineOnPage })} aria-label="Open AI assistant"
                    className="fixed right-5 bottom-5 z-40 size-13 rounded-full shadow-lg shadow-primary/30 transition-transform hover:scale-105">
              <Sparkles className="size-5.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="left">AI assistant (⌘J)</TooltipContent>
        </Tooltip>
      )}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className="flex flex-col gap-0 p-0 data-[side=right]:w-full sm:data-[side=right]:max-w-md">
          <AssistantPanel />
        </SheetContent>
      </Sheet>
    </>
  );
}
