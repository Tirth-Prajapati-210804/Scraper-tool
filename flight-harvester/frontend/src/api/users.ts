import type { UserAdmin } from "../types/auth";
import { api } from "./client";

export async function listUsers(): Promise<UserAdmin[]> {
  const res = await api.get<UserAdmin[]>("/api/v1/users/");
  return res.data;
}

export async function deactivateUser(userId: string): Promise<UserAdmin> {
  const res = await api.post<UserAdmin>(`/api/v1/users/${userId}/deactivate`);
  return res.data;
}

export async function reactivateUser(userId: string): Promise<UserAdmin> {
  const res = await api.post<UserAdmin>(`/api/v1/users/${userId}/reactivate`);
  return res.data;
}
