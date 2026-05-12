"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, Pause, Play, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { getServerLogs } from "@/lib/api/logs";
import type { ServerLogResponse } from "@/lib/api/types";

const LOG_LINE_COUNT = 300;
const AUTO_REFRESH_MS = 3000;

export function ServerLogWindow() {
  const [open, setOpen] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logs, setLogs] = useState<ServerLogResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getServerLogs(LOG_LINE_COUNT);
      setLogs(response);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load server logs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void loadLogs();
  }, [loadLogs, open]);

  useEffect(() => {
    if (!open || !autoRefresh) return;

    const interval = window.setInterval(() => {
      void loadLogs();
    }, AUTO_REFRESH_MS);

    return () => window.clearInterval(interval);
  }, [autoRefresh, loadLogs, open]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={() => setOpen(true)}
      >
        <FileText className="h-3.5 w-3.5" />
        Logs
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-5xl gap-3 p-5">
          <DialogHeader>
            <DialogTitle>Server Logs</DialogTitle>
            <DialogDescription className="truncate font-mono text-xs">
              {logs?.path ?? ".repowise/server.log"}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap items-center justify-between gap-2 border-y border-[var(--color-border-default)] py-2">
            <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
              {autoRefresh ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
              <span>Auto-refresh</span>
              <Switch
                checked={autoRefresh}
                onCheckedChange={setAutoRefresh}
                aria-label="Toggle log auto-refresh"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={() => void loadLogs()}
              disabled={loading}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {error ? (
            <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          ) : null}

          <div
            ref={scrollRef}
            className="h-[60vh] overflow-auto rounded-md border border-[var(--color-border-default)] bg-[var(--color-bg-inset)] px-3 py-2"
          >
            {logs?.lines.length ? (
              <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-5 text-[var(--color-text-primary)]">
                {logs.lines.join("\n")}
              </pre>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-[var(--color-text-tertiary)]">
                {loading ? "Loading logs..." : "No log entries yet."}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
