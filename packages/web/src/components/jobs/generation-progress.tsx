"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { useJob } from "@/lib/hooks/use-job";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { JobLog } from "./job-log";
import { formatTokens, formatNumber } from "@/lib/utils/format";
import type { JobProgressEvent } from "@/lib/api/types";

interface Props {
  jobId: string;
  repoName?: string;
  /** Called when the job reaches a terminal state, with the job's finished_at timestamp */
  onDone?: (finishedAt: string | null, status: "completed" | "failed") => void;
}

export function GenerationProgress({ jobId, repoName, onDone }: Props) {
  const { job, sse } = useJob(jobId);
  const [log, setLog] = useState<Array<{ text: string }>>([]);
  const [elapsed, setElapsed] = useState(0);
  const [actualCost, setActualCost] = useState<number | null>(null);
  const startRef = useRef(Date.now());
  const notifiedRef = useRef(false);

  // Elapsed timer
  useEffect(() => {
    const id = setInterval(() => setElapsed(Date.now() - startRef.current), 1000);
    return () => clearInterval(id);
  }, []);

  // Accumulate log entries and track running cost from SSE progress events
  useEffect(() => {
    if (!sse.data) return;
    const ev = sse.data as JobProgressEvent;
    if (ev.current_page) {
      setLog((prev) => [
        ...prev,
        { text: `[L${ev.current_level ?? "?"}] ${ev.current_page}` },
      ]);
    }
    if (ev.actual_cost_usd != null) {
      setActualCost(ev.actual_cost_usd);
    }
  }, [sse.data]);

  const liveProgress = sse.data as JobProgressEvent | null;
  const mode = (job?.config?.mode as string | undefined) ?? "sync";
  const isCliUpdate = mode === "cli_update";
  const isFullResync = mode === "full_resync";
  const completedPages = liveProgress?.completed_pages ?? job?.completed_pages ?? 0;
  const totalPages = liveProgress?.total_pages ?? job?.total_pages ?? 0;
  const currentLevel = liveProgress?.current_level ?? job?.current_level;
  const progressUnit = isCliUpdate ? "command" : isFullResync ? "pages" : "files";
  const runningLabel = isCliUpdate
    ? "Updating"
    : `${isFullResync ? "Re-indexing" : "Scanning"}${currentLevel != null ? ` level ${currentLevel}` : ""}`;
  const doneLabel = isCliUpdate ? "Update complete" : isFullResync ? "Re-index complete" : "Scan complete";
  const failedLabel = isCliUpdate ? "Update failed" : isFullResync ? "Re-index failed" : "Scan failed";
  const failedPages = job?.failed_pages ?? 0;
  const generatedPages =
    typeof job?.config?.pages_generated === "number"
      ? job.config.pages_generated
      : completedPages;

  // Toast on terminal state
  useEffect(() => {
    if (notifiedRef.current) return;
    if (job?.status === "completed") {
      notifiedRef.current = true;
      toast.success(`${isCliUpdate ? "Update command completed" : "Documentation updated"}${repoName ? ` — ${repoName}` : ""}`, {
        description: isCliUpdate
          ? (job.config?.command as string | undefined) ?? "repowise update"
          : isFullResync
          ? `${formatNumber(generatedPages)} pages generated`
          : `${formatNumber(job.completed_pages)} files scanned`,
      });
      onDone?.(job.finished_at ?? new Date().toISOString(), "completed");
    } else if (job?.status === "failed") {
      notifiedRef.current = true;
      toast.error(isCliUpdate ? "Update command failed" : "Generation failed", {
        description: job.error_message ?? "Unknown error",
      });
      onDone?.(job.finished_at ?? null, "failed");
    }
  }, [job?.status, job?.completed_pages, job?.config, job?.error_message, job?.finished_at, generatedPages, isCliUpdate, isFullResync, repoName, onDone]);

  const progress = job || liveProgress
    ? totalPages > 0
      ? Math.round((completedPages / totalPages) * 100)
      : 0
    : 0;

  const elapsedStr = `${Math.floor(elapsed / 60000)}m ${Math.floor((elapsed % 60000) / 1000)}s`;
  const isRunning = job?.status === "running" || job?.status === "pending";
  const isDone = job?.status === "completed";
  const isFailed = job?.status === "failed";

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        {isRunning && <Loader2 className="h-4 w-4 animate-spin text-[var(--color-accent-primary)] shrink-0" />}
        {isDone && <CheckCircle className="h-4 w-4 text-[var(--color-fresh)] shrink-0" />}
        {isFailed && <XCircle className="h-4 w-4 text-[var(--color-outdated)] shrink-0" />}

        <span className="text-sm font-medium text-[var(--color-text-primary)]">
          {isRunning && `${runningLabel}…`}
          {isDone && doneLabel}
          {isFailed && failedLabel}
        </span>

        <span className="ml-auto text-xs text-[var(--color-text-tertiary)] tabular-nums">
          {elapsedStr}
        </span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <Progress
          value={progress}
          indicatorClassName={isFailed ? "bg-[var(--color-outdated)]" : undefined}
        />
        <div className="flex justify-between text-xs text-[var(--color-text-tertiary)]">
          <span>
            {formatNumber(completedPages)} /{" "}
            {formatNumber(totalPages)} {progressUnit}
          </span>
          {failedPages > 0 && (
            <Badge variant="stale" className="text-xs py-0">
              {failedPages} failed
            </Badge>
          )}
          <span>{progress}%</span>
        </div>
      </div>

      {/* Live cost */}
      {actualCost != null && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--color-text-tertiary)]">
          <span>Cost: ${actualCost.toFixed(4)}</span>
          {isRunning && (
            <span className="inline-flex items-center gap-0.5 rounded bg-[var(--color-accent-primary)]/15 px-1 py-px text-[10px] font-medium text-[var(--color-accent-primary)]">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-accent-primary)]" />
              live
            </span>
          )}
        </div>
      )}

      {/* Summary on done */}
      {isDone && (
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded border border-[var(--color-border-default)] p-2 text-center">
            <p className="text-lg font-semibold text-[var(--color-text-primary)]">
              {formatNumber(isFullResync ? generatedPages : completedPages)}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">{progressUnit}</p>
          </div>
          <div className="rounded border border-[var(--color-border-default)] p-2 text-center">
            <p className="text-lg font-semibold text-[var(--color-text-primary)]">
              {formatTokens((job!.config?.total_input_tokens as number) ?? 0)}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">tokens in</p>
          </div>
          <div className="rounded border border-[var(--color-border-default)] p-2 text-center">
            <p className="text-lg font-semibold text-[var(--color-text-primary)]">
              {elapsedStr}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">elapsed</p>
          </div>
        </div>
      )}

      {/* Error */}
      {isFailed && job?.error_message && (
        <p className="text-sm text-[var(--color-outdated)]">{job.error_message}</p>
      )}

      {/* Live log */}
      {log.length > 0 && <JobLog entries={log} />}
    </div>
  );
}
