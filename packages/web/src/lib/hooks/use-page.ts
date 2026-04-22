"use client";

import useSWR from "swr";
import { getPageById, getPageVersions } from "@/lib/api/pages";
import type { PageResponse, PageVersionResponse } from "@/lib/api/types";

export function usePage(pageId: string | null, repoId?: string | null) {
  const { data, error, isLoading, mutate } = useSWR<PageResponse>(
    pageId ? `page:${repoId ?? "global"}:${pageId}` : null,
    () => getPageById(pageId!, repoId ?? undefined),
    { revalidateOnFocus: false },
  );
  return { page: data, error, isLoading, mutate };
}

export function usePageVersions(pageId: string | null, repoId?: string | null) {
  const { data, error, isLoading } = useSWR<PageVersionResponse[]>(
    pageId ? `page:${repoId ?? "global"}:${pageId}:versions` : null,
    () => getPageVersions(pageId!, repoId ?? undefined),
    { revalidateOnFocus: false },
  );
  return { versions: data ?? [], error, isLoading };
}
