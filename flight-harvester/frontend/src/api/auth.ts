import type { TokenResponse, User } from "../types/auth";
import { api } from "./client";

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  const res = await api.post<TokenResponse>("/api/v1/auth/login", params, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await api.get<User>("/api/v1/auth/me");
  return res.data;
}
