import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { CommandPalette } from "@/components/search/command-palette";
import { listRepos } from "@/lib/api/repos";
import { getWorkspace } from "@/lib/api/workspace";
import type { WorkspaceResponse } from "@/lib/api/types";
import "@/styles/globals.css";

export const metadata: Metadata = {
  applicationName: "repowise",
  title: {
    default: "repowise — Codebase documentation engine",
    template: "%s — repowise",
  },
  description:
    "Repowise turns indexed repositories into living documentation, code intelligence, dependency maps, and operational engineering dashboards.",
  keywords: [
    "codebase documentation",
    "developer tools",
    "repository intelligence",
    "architecture documentation",
    "code search",
  ],
  openGraph: {
    title: "repowise — Codebase documentation engine",
    description:
      "Living documentation, dependency maps, repository health, and engineering intelligence for indexed codebases.",
    siteName: "repowise",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "repowise — Codebase documentation engine",
    description:
      "Living documentation, dependency maps, repository health, and engineering intelligence for indexed codebases.",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Fetch repos + workspace info server-side for the sidebar.
  // Gracefully fall back to empty/null if the API is unavailable.
  let repos: Awaited<ReturnType<typeof listRepos>> = [];
  let workspace: WorkspaceResponse | null = null;
  try {
    const [reposResult, wsResult] = await Promise.allSettled([
      listRepos(),
      getWorkspace(),
    ]);
    if (reposResult.status === "fulfilled") repos = reposResult.value;
    if (wsResult.status === "fulfilled") workspace = wsResult.value;
  } catch {
    // API not available — show empty sidebar
  }

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} dark`}
      data-theme="night"
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(() => {
try {
  const mode = localStorage.getItem("repowise_theme") === "day" ? "day" : "night";
  document.documentElement.classList.toggle("dark", mode === "night");
  document.documentElement.dataset.theme = mode;
} catch {}
})();`,
          }}
        />
      </head>
      <body className="bg-[var(--color-bg-root)] text-[var(--color-text-primary)] antialiased">
        <NuqsAdapter>
        <TooltipProvider delayDuration={300}>
          <div className="flex h-screen overflow-hidden">
            <Sidebar repos={repos} workspace={workspace} />
            <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
              <MobileNav repos={repos} workspace={workspace} />
              <main className="flex-1 overflow-auto min-w-0">
                {children}
              </main>
            </div>
          </div>
          <CommandPalette repos={repos} workspace={workspace} />
        </TooltipProvider>
        </NuqsAdapter>
        <Toaster
          theme="system"
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--color-bg-elevated)",
              border: "1px solid var(--color-border-default)",
              color: "var(--color-text-primary)",
            },
          }}
        />
      </body>
    </html>
  );
}
