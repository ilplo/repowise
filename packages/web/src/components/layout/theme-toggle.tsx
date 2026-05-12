"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

type ThemeMode = "day" | "night";

const STORAGE_KEY = "repowise_theme";

function readStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "night";
  return window.localStorage.getItem(STORAGE_KEY) === "day" ? "day" : "night";
}

function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle("dark", mode === "night");
  document.documentElement.dataset.theme = mode;
}

export function ThemeToggle({ iconOnly = false }: { iconOnly?: boolean }) {
  const [mode, setMode] = React.useState<ThemeMode>("night");

  React.useEffect(() => {
    const storedMode = readStoredTheme();
    setMode(storedMode);
    applyTheme(storedMode);
  }, []);

  const nextMode: ThemeMode = mode === "night" ? "day" : "night";
  const label = `Switch to ${nextMode} theme`;
  const Icon = mode === "night" ? Moon : Sun;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={() => {
            setMode(nextMode);
            window.localStorage.setItem(STORAGE_KEY, nextMode);
            applyTheme(nextMode);
          }}
          className={cn(
            "inline-flex h-8 shrink-0 items-center justify-center rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-hover)] hover:text-[var(--color-text-primary)]",
            iconOnly ? "w-8" : "w-9",
          )}
        >
          <Icon className="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent side={iconOnly ? "right" : "bottom"}>{label}</TooltipContent>
    </Tooltip>
  );
}
