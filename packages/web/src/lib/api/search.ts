import { apiGet } from "./client";
import type { SearchResultResponse } from "./types";

export async function search(
  query: string,
  opts?: { repo_id?: string; search_type?: "semantic" | "fulltext"; limit?: number },
): Promise<SearchResultResponse[]> {
  return apiGet<SearchResultResponse[]>("/api/search", {
    query,
    repo_id: opts?.repo_id,
    search_type: opts?.search_type ?? "semantic",
    limit: opts?.limit ?? 10,
  });
}
