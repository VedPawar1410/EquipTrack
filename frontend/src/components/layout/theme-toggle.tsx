"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // The server can't know the visitor's theme, so nothing rendered here may depend on it
  // (a theme-dependent label caused a hydration mismatch). The label is neutral; CSS picks the icon.
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle light/dark mode"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          <Sun className="size-4.5 dark:hidden" />
          <Moon className="hidden size-4.5 dark:block" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>Toggle light/dark mode</TooltipContent>
    </Tooltip>
  );
}
