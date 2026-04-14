export interface SearchLegCreate {
  origin_query: string;       // "India", "AMD", "Ahmedabad", "TYO, SHA"
  destination_query: string;
  min_halt_hours?: number | null;  // NULL = final leg
  max_halt_hours?: number | null;
}

export interface SearchProfileCreate {
  name: string;
  days_ahead: number;
  is_active: boolean;
  legs: SearchLegCreate[];
}

export interface SearchLeg {
  id: string;
  profile_id: string;
  leg_order: number;
  origin_query: string;
  destination_query: string;
  resolved_origins: string[];
  resolved_destinations: string[];
  min_halt_hours: number | null;
  max_halt_hours: number | null;
}

export interface SearchProfile {
  id: string;
  name: string;
  is_active: boolean;
  days_ahead: number;
  legs: SearchLeg[];
  created_at: string;
  updated_at: string;
}

export interface FlightPrice {
  id: string;
  leg_id: string;
  profile_id: string;
  origin: string;
  destination: string;
  depart_date: string;
  airline: string;
  price: number;
  currency: string;
  provider: string;
  deep_link: string | null;
  stops: number | null;
  duration_minutes: number | null;
  scraped_at: string;
}

export interface ProfileProgressLeg {
  leg_id: string;
  leg_order: number;
  origin_query: string;
  destination_query: string;
  total_slots: number;
  filled_slots: number;
  coverage_percent: number;
}

export interface SearchProfileProgress {
  profile_id: string;
  name: string;
  total_slots: number;
  filled_slots: number;
  coverage_percent: number;
  last_scraped_at: string | null;
  legs: ProfileProgressLeg[];
}
