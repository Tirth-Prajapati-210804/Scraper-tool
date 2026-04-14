import type {
  FlightPrice,
  SearchProfile,
  SearchProfileCreate,
  SearchProfileProgress,
} from "../types/search-profile";
import { api } from "./client";

export async function listSearchProfiles(activeOnly = true): Promise<SearchProfile[]> {
  const res = await api.get<SearchProfile[]>("/api/v1/search-profiles/", {
    params: { active_only: activeOnly },
  });
  return res.data;
}

export async function getSearchProfile(id: string): Promise<SearchProfile> {
  const res = await api.get<SearchProfile>(`/api/v1/search-profiles/${id}`);
  return res.data;
}

export async function createSearchProfile(data: SearchProfileCreate): Promise<SearchProfile> {
  const res = await api.post<SearchProfile>("/api/v1/search-profiles/", data);
  return res.data;
}

export async function updateSearchProfile(
  id: string,
  data: Partial<Pick<SearchProfile, "name" | "days_ahead" | "is_active">>,
): Promise<SearchProfile> {
  const res = await api.put<SearchProfile>(`/api/v1/search-profiles/${id}`, data);
  return res.data;
}

export async function deleteSearchProfile(id: string): Promise<void> {
  await api.delete(`/api/v1/search-profiles/${id}`);
}

export async function getSearchProfileProgress(id: string): Promise<SearchProfileProgress> {
  const res = await api.get<SearchProfileProgress>(
    `/api/v1/search-profiles/${id}/progress`,
  );
  return res.data;
}

export async function getProfilePrices(
  id: string,
  params?: { leg_order?: number; origin?: string; destination?: string; limit?: number },
): Promise<FlightPrice[]> {
  const res = await api.get<FlightPrice[]>(`/api/v1/search-profiles/${id}/prices`, {
    params,
  });
  return res.data;
}
