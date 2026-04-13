import type { CollectionRun, ScrapeLogEntry } from "../types/price";
import { api } from "./client";

export async function triggerCollection(): Promise<void> {
  await api.post("/api/v1/collection/trigger");
}

export async function triggerGroupCollection(groupId: string): Promise<void> {
  await api.post(`/api/v1/collection/trigger-group/${groupId}`);
}

export async function fetchCollectionRuns(limit = 20): Promise<CollectionRun[]> {
  const res = await api.get<CollectionRun[]>("/api/v1/collection/runs", {
    params: { limit },
  });
  return res.data;
}

export async function fetchScrapeLogs(params: {
  route_group_id?: string;
  origin?: string;
  limit?: number;
}): Promise<ScrapeLogEntry[]> {
  const res = await api.get<ScrapeLogEntry[]>("/api/v1/collection/logs", {
    params,
  });
  return res.data;
}
