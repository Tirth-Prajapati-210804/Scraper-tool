import { api } from "./client";

export async function triggerCollection(): Promise<void> {
  await api.post("/api/v1/collection/trigger");
}

export async function triggerGroupCollection(groupId: string): Promise<void> {
  await api.post(`/api/v1/collection/trigger-group/${groupId}`);
}
