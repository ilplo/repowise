import type { Metadata } from "next";
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  FileText,
  CheckCircle2,
  AlertCircle,
  Skull,
  Activity,
  RefreshCw,
  Clock,
  GitBranch,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";
import { listRepos, getRepoStats } from "@/lib/api/repos";
import { listJobs } from "@/lib/api/jobs";
import { getGitSummary } from "@/lib/api/git";
import { getWorkspace } from "@/lib/api/workspace";
import type { RepoStatsResponse, GitSummaryResponse, JobResponse } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { AddRepoDialog } from "@/components/repos/add-repo-dialog";
import { formatRelativeTime, formatNumber } from "@/lib/utils/format";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Monitor repository documentation freshness, indexing jobs, code graph coverage, and engineering attention areas in Repowise.",
  openGraph: {
    title: "Repowise Dashboard",
    description:
      "A repository intelligence dashboard for living documentation, code graph coverage, and engineering operations.",
  },
  twitter: {
    card: "summary",
    title: "Repowise Dashboard",
    description:
      "Monitor living documentation, code graph coverage, and repository intelligence in Repowise.",
  },
};

export const revalidate = 30;

function formatJobWork(job: JobResponse): string {
  const mode = (job.config?.mode as string | undefined) ?? "sync";
  if (mode === "cli_update") {
    return "1 command";
  }
  if (mode === "full_resync") {
    const generated =
      typeof job.config?.pages_generated === "number"
        ? job.config.pages_generated
        : job.completed_pages;
    return `${formatNumber(generated)} pages`;
  }
  return `${formatNumber(job.total_pages)} files`;
}

function jobModeLabel(job: JobResponse): string {
  const mode = (job.config?.mode as string | undefined) ?? "sync";
  if (mode === "cli_update") return "CLI update";
  if (mode === "full_resync") return "Full resync";
  return "Sync";
}

function jobRuntimeLabel(job: JobResponse): string {
  return job.model_name || job.provider_name || "Model not recorded";
}

function jobProgress(job: JobResponse): number {
  if (job.total_pages <= 0) return job.status === "completed" ? 100 : 0;
  return Math.min(100, Math.round((job.completed_pages / job.total_pages) * 100));
}

function repoCoverage(stats: RepoStatsResponse | undefined): string {
  return stats ? `${Math.round(stats.doc_coverage_pct)}%` : "Pending";
}

function repoRiskLabel(git: GitSummaryResponse | undefined): string {
  if (!git) return "Awaiting git scan";
  if (git.hotspot_count > 0) return `${formatNumber(git.hotspot_count)} hotspot${git.hotspot_count === 1 ? "" : "s"}`;
  if (git.stable_count > 0) return `${formatNumber(git.stable_count)} stable files`;
  return "No hotspots detected";
}

export default async function DashboardPage() {
  const [repos, jobs, ws] = await Promise.allSettled([
    listRepos(),
    listJobs({ limit: 10 }),
    getWorkspace(),
  ]);

  const repoList = repos.status === "fulfilled" ? repos.value : [];
  const jobList = jobs.status === "fulfilled" ? jobs.value : [];
  const workspace = ws.status === "fulfilled" ? ws.value : null;

  // Workspace mode → workspace dashboard
  if (workspace?.is_workspace) {
    redirect("/workspace");
  }

  // Single repo → go straight to its overview
  if (repoList.length === 1) {
    redirect(`/repos/${repoList[0].id}/overview`);
  }

  // Aggregate stats across all repos

  const statsResults = await Promise.allSettled(
    repoList.map((r) => getRepoStats(r.id)),
  );
  const gitResults = await Promise.allSettled(
    repoList.map((r) => getGitSummary(r.id)),
  );

  const statsMap = new Map<string, RepoStatsResponse>();
  const gitMap = new Map<string, GitSummaryResponse>();
  repoList.forEach((r, i) => {
    if (statsResults[i]?.status === "fulfilled")
      statsMap.set(r.id, (statsResults[i] as PromiseFulfilledResult<RepoStatsResponse>).value);
    if (gitResults[i]?.status === "fulfilled")
      gitMap.set(r.id, (gitResults[i] as PromiseFulfilledResult<GitSummaryResponse>).value);
  });

  // Aggregate stats across all repos
  let totalPages = 0;
  let freshPages = 0;
  let deadCode = 0;
  let totalHotspots = 0;
  for (const s of statsMap.values()) {
    totalPages += s.file_count;
    freshPages += Math.round(s.file_count * s.doc_coverage_pct / 100);
    deadCode += s.dead_export_count;
  }
  for (const g of gitMap.values()) {
    totalHotspots += g.hotspot_count;
  }
  const stalePages = totalPages - freshPages;
  const coveragePct = totalPages > 0 ? Math.round((freshPages / totalPages) * 100) : 0;
  const runningJobs = jobList.filter((job) => job.status === "running");
  const failedJobs = jobList.filter((job) => job.status === "failed");
  const completedJobs = jobList.filter((job) => job.status === "completed");

  const softwareJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "repowise",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Any",
    description:
      "Open-source codebase documentation engine for repository documentation, code graph exploration, and engineering intelligence.",
  };

  return (
    <div className="relative min-h-full overflow-hidden px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
      />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(245,149,32,0.06)_1px,transparent_1px),linear-gradient(180deg,rgba(245,149,32,0.04)_1px,transparent_1px)] bg-[size:72px_72px] opacity-40" />

      <div className="relative mx-auto max-w-[1320px] space-y-4">
        <section
          aria-labelledby="dashboard-title"
          className="glass-panel overflow-hidden rounded-2xl p-3 sm:p-4"
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[var(--glass-border)] bg-[var(--color-accent-muted)] text-[var(--color-accent-primary)]">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div>
                <h1
                  id="dashboard-title"
                  className="text-lg font-semibold text-[var(--color-text-primary)]"
                >
                  Dashboard
                </h1>
                <p className="sr-only">Repowise repository intelligence dashboard</p>
              </div>
              <Badge variant="accent">{repoList.length} repos</Badge>
              {failedJobs.length > 0 && (
                <Badge variant="outdated">{failedJobs.length} failed</Badge>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <AddRepoDialog />
              <Button variant="outline" asChild>
                <Link href="/settings">
                  <Settings className="h-4 w-4" />
                  Settings
                </Link>
              </Button>
              {repoList.length > 0 && (
                <Button variant="ghost" asChild>
                  <Link href={`/repos/${repoList[0].id}/search`}>
                    <Search className="h-4 w-4" />
                    Search
                  </Link>
                </Button>
              )}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            <CompactMetric
              icon={<FileText className="h-4 w-4" />}
              label="Pages"
              value={formatNumber(totalPages)}
            />
            <CompactMetric
              icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
              label="Fresh"
              value={totalPages > 0 ? `${coveragePct}%` : "Pending"}
            />
            <CompactMetric
              icon={<AlertCircle className="h-4 w-4 text-yellow-500" />}
              label="Stale"
              value={formatNumber(stalePages)}
            />
            <CompactMetric
              icon={<GitBranch className="h-4 w-4" />}
              label="Hotspots"
              value={formatNumber(totalHotspots)}
            />
            <CompactMetric
              icon={<Skull className="h-4 w-4 text-[var(--color-text-tertiary)]" />}
              label="Dead"
              value={deadCode > 0 ? formatNumber(deadCode) : "—"}
            />
            <CompactMetric
              icon={<Activity className="h-4 w-4" />}
              label="Jobs"
              value={runningJobs.length > 0 ? `${runningJobs.length} running` : formatNumber(jobList.length)}
            />
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
          <section aria-labelledby="repositories-title">
            <Card className="glass-card overflow-hidden">
              <CardHeader className="flex-row items-center justify-between gap-4 pb-3">
                <div>
                  <CardTitle id="repositories-title" className="text-base font-semibold">
                    Repositories
                  </CardTitle>
                </div>
                <Badge variant="accent">{repoList.length} registered</Badge>
              </CardHeader>
              <CardContent className="p-0">
                {repoList.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      title="No repositories registered"
                      description="Add a repository or run repowise init."
                      icon={<Boxes className="h-8 w-8" />}
                      className="bg-[var(--glass-bg)]"
                    />
                  </div>
                ) : (
                  <div className="grid gap-3 p-4 md:grid-cols-2">
                    {repoList.map((repo) => {
                      const stats = statsMap.get(repo.id);
                      const git = gitMap.get(repo.id);
                      return (
                        <Link
                          key={repo.id}
                          href={`/repos/${repo.id}/overview`}
                          className="group rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4 transition hover:-translate-y-0.5 hover:border-[var(--color-border-hover)] hover:bg-[var(--color-bg-elevated)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent-primary)]"
                        >
                          <div className="flex items-start gap-3">
                            <div className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-accent-muted)] text-[var(--color-accent-primary)]">
                              <BookOpen className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <h3 className="truncate text-sm font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-accent-primary)]">
                                  {repo.name}
                                </h3>
                                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-[var(--color-text-tertiary)] transition group-hover:translate-x-0.5 group-hover:text-[var(--color-accent-primary)]" />
                              </div>
                              <p className="mt-1 truncate font-mono text-xs text-[var(--color-text-tertiary)]" title={repo.local_path}>
                                {repo.local_path}
                              </p>
                            </div>
                          </div>

                          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                            <MiniMetric label="Docs" value={repoCoverage(stats)} />
                            <MiniMetric label="Files" value={stats ? formatNumber(stats.file_count) : "Pending"} />
                          </div>

                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            <Badge variant={git?.hotspot_count ? "outdated" : "outline"}>
                              {repoRiskLabel(git)}
                            </Badge>
                            {repo.head_commit && (
                              <Badge variant="outline" className="font-mono">
                                {repo.head_commit.slice(0, 7)}
                              </Badge>
                            )}
                            <span className="text-xs text-[var(--color-text-tertiary)]">
                              Updated {formatRelativeTime(repo.updated_at)}
                            </span>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </section>

          <section aria-labelledby="jobs-title">
            <Card className="glass-card overflow-hidden">
              <CardHeader className="flex-row items-center justify-between gap-4 pb-3">
                <div>
                  <CardTitle id="jobs-title" className="text-base font-semibold">
                    Jobs
                  </CardTitle>
                </div>
                {runningJobs.length > 0 ? (
                  <Badge variant="accent">{runningJobs.length} running</Badge>
                ) : (
                  <Badge variant="outline">{completedJobs.length} completed</Badge>
                )}
              </CardHeader>
              <CardContent className="p-0">
                {jobList.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      title="No jobs yet"
                      description="Run init, update, sync, or resync."
                      icon={<Activity className="h-8 w-8" />}
                      className="bg-[var(--glass-bg)]"
                    />
                  </div>
                ) : (
                  <ul className="divide-y divide-[var(--color-border-default)]">
                    {jobList.map((job) => (
                      <li key={job.id} className="px-5 py-4">
                        <div className="flex items-start gap-3">
                          <JobStatusIcon status={job.status} />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium text-[var(--color-text-primary)]">
                                {jobModeLabel(job)}
                              </span>
                              <Badge
                                variant={
                                  job.status === "completed"
                                    ? "fresh"
                                    : job.status === "failed"
                                      ? "outdated"
                                      : job.status === "running"
                                        ? "accent"
                                        : "default"
                                }
                              >
                                {job.status}
                              </Badge>
                              <span className="font-mono text-xs text-[var(--color-text-secondary)]">
                                {job.status === "running"
                                  ? `${formatNumber(job.completed_pages)}/${formatNumber(job.total_pages)}`
                                  : formatJobWork(job)}
                              </span>
                            </div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--color-bg-elevated)]">
                              <div
                                className="h-full rounded-full bg-[var(--color-accent-primary)] transition-[width]"
                                style={{ width: `${jobProgress(job)}%` }}
                              />
                            </div>
                            <p className="mt-2 truncate text-xs text-[var(--color-text-tertiary)]">
                              {jobRuntimeLabel(job)} · Updated {formatRelativeTime(job.updated_at)}
                            </p>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </section>
        </div>

      </div>
    </div>
  );
}

function CompactMetric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-tertiary)]">
          {label}
        </span>
        <span className="text-[var(--color-accent-primary)]">{icon}</span>
      </div>
      <p className="mt-1 truncate text-base font-semibold tabular-nums text-[var(--color-text-primary)]">
        {value}
      </p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border-default)] bg-[var(--color-bg-elevated)] px-3 py-2">
      <p className="text-[11px] font-medium uppercase text-[var(--color-text-tertiary)]">{label}</p>
      <p className="mt-1 font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}

function JobStatusIcon({ status }: { status: string }) {
  if (status === "running") {
    return (
      <RefreshCw className="h-4 w-4 shrink-0 animate-spin text-[var(--color-accent-primary)]" />
    );
  }
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />;
  }
  if (status === "failed") {
    return <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />;
  }
  return <Clock className="h-4 w-4 shrink-0 text-[var(--color-text-tertiary)]" />;
}
