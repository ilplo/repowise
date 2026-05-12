import { apiGet } from "./client";
import type { ServerLogResponse } from "./types";

export async function getServerLogs(lines = 300): Promise<ServerLogResponse> {
  return apiGet<ServerLogResponse>("/api/logs/server", { lines }, { cache: "no-store" });
}
