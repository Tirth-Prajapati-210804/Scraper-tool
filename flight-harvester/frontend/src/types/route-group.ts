export interface RouteGroupFromTextCreate {
  origin: string;
  destination: string;
  nights?: number;
  days_ahead?: number;
}

export interface RouteGroupFromTextResponse {
  group: RouteGroup;
  resolved_origins: string[];
  resolved_destinations: string[];
}

export interface RouteGroup {
  id: string;
  name: string;
  destination_label: string;
  destinations: string[];
  origins: string[];
  nights: number;
  days_ahead: number;
  sheet_name_map: Record<string, string>;
  special_sheets: SpecialSheet[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpecialSheet {
  name: string;
  origin: string;
  destination_label: string;
  destinations: string[];
  columns: number;
}

export interface RouteGroupProgress {
  route_group_id: string;
  name: string;
  total_dates: number;
  dates_with_data: number;
  coverage_percent: number;
  last_scraped_at: string | null;
  per_origin: Record<string, { total: number; collected: number }>;
}
