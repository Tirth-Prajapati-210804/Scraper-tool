import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getProfileJourney,
  getProfilePrices,
  getSearchProfile,
  getSearchProfileProgress,
  type JourneyRow,
} from "../api/search-profiles";
import { triggerGroupCollection } from "../api/collection";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PriceTable } from "../components/PriceTable";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ProgressBar } from "../components/ui/ProgressBar";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../context/ToastContext";
import type { FlightPrice } from "../types/search-profile";
import type { DailyPrice } from "../types/price";
import { formatRelativeTime } from "../utils/format";
import { usePageTitle } from "../utils/usePageTitle";

// FlightPrice is structurally compatible with DailyPrice for PriceTable display
function toDailyPrice(fp: FlightPrice): DailyPrice {
  return {
    id: fp.id,
    origin: fp.origin,
    destination: fp.destination,
    depart_date: fp.depart_date,
    airline: fp.airline,
    price: fp.price,
    currency: fp.currency,
    provider: fp.provider,
    stops: fp.stops,
    duration_minutes: fp.duration_minutes,
    scraped_at: fp.scraped_at,
  };
}

// Stops filter options
const STOPS_OPTIONS = [
  { value: "", label: "All stops" },
  { value: "0", label: "Direct only" },
  { value: "1", label: "1 stop" },
  { value: "2", label: "2+ stops" },
];

type Tab = "prices" | "journey";

export function SearchProfileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { showToast } = useToast();
  const [triggering, setTriggering] = useState(false);
  const [selectedLegOrder, setSelectedLegOrder] = useState<number | "">("");
  const [stopsFilter, setStopsFilter] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("prices");

  const profileQuery = useQuery({
    queryKey: ["search-profile", id],
    queryFn: () => getSearchProfile(id!),
    enabled: !!id,
  });

  const progressQuery = useQuery({
    queryKey: ["search-profile-progress", id],
    queryFn: () => getSearchProfileProgress(id!),
    enabled: !!id,
    refetchInterval: 60_000,
  });

  const pricesQuery = useQuery({
    queryKey: ["search-profile-prices", id, selectedLegOrder, stopsFilter],
    queryFn: () =>
      getProfilePrices(id!, {
        leg_order: selectedLegOrder !== "" ? selectedLegOrder : undefined,
        stops: stopsFilter !== "" ? Number(stopsFilter) : undefined,
        limit: 500,
      }),
    enabled: !!id && activeTab === "prices",
  });

  const journeyQuery = useQuery({
    queryKey: ["search-profile-journey", id],
    queryFn: () => getProfileJourney(id!),
    enabled: !!id && activeTab === "journey",
  });

  const profile = profileQuery.data;
  usePageTitle(profile?.name ?? "Search Profile");

  const isMultiLeg = (profile?.legs.length ?? 0) > 1;

  async function handleTrigger() {
    if (!id) return;
    setTriggering(true);
    try {
      await triggerGroupCollection(id);
      showToast("Collection triggered", "success");
      qc.invalidateQueries({ queryKey: ["search-profile-progress", id] });
      qc.invalidateQueries({ queryKey: ["search-profile-prices", id] });
      qc.invalidateQueries({ queryKey: ["search-profile-journey", id] });
    } catch {
      showToast("Failed to trigger collection", "error");
    } finally {
      setTriggering(false);
    }
  }

  if (profileQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="py-16 text-center text-slate-400">
        Profile not found.{" "}
        <Link to="/search-profiles" className="text-brand-600 hover:underline">
          Back to Search Profiles
        </Link>
      </div>
    );
  }

  const progress = progressQuery.data;

  return (
    <ErrorBoundary>
      <div className="space-y-6 p-6">
        {/* Back + Actions */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/search-profiles"
            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Search Profiles
          </Link>
          <Button variant="secondary" onClick={handleTrigger} loading={triggering}>
            <RefreshCw className="h-4 w-4" />
            Trigger Collection
          </Button>
        </div>

        {/* Profile header */}
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900">{profile.name}</h2>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    profile.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {profile.is_active ? "Active" : "Paused"}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {profile.days_ahead} days ahead · {profile.legs.length} leg
                {profile.legs.length !== 1 ? "s" : ""}
                {progress?.last_scraped_at && (
                  <> · Last collected {formatRelativeTime(progress.last_scraped_at)}</>
                )}
              </p>
            </div>
          </div>

          {/* Legs */}
          <div className="mt-4 space-y-2">
            {profile.legs.map((leg, idx) => (
              <div
                key={leg.id}
                className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="w-6 text-center text-xs font-mono font-medium text-slate-400">
                    L{idx + 1}
                  </span>
                  <span className="font-semibold text-slate-800">{leg.origin_query}</span>
                  <span className="text-slate-400">→</span>
                  <span className="font-semibold text-slate-800">{leg.destination_query}</span>
                  {leg.resolved_origins.length > 0 && (
                    <span className="text-xs text-slate-400">
                      ({leg.resolved_origins.join(", ")} → {leg.resolved_destinations.join(", ")})
                    </span>
                  )}
                </div>
                {leg.min_halt_hours !== null && idx < profile.legs.length - 1 && (
                  <p className="mt-1.5 ml-9 text-xs text-amber-600">
                    Wait at least {leg.min_halt_hours}h
                    {leg.max_halt_hours != null ? ` (max ${leg.max_halt_hours}h)` : ""} before next leg
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Collection Progress */}
        <Card className="p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Collection Progress</h3>
          {progressQuery.isLoading ? (
            <Skeleton className="h-32" />
          ) : progress ? (
            <div className="space-y-4">
              {/* Overall */}
              <div>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">Overall</span>
                  <span className="text-slate-500">
                    {progress.filled_slots}/{progress.total_slots} (
                    {progress.coverage_percent.toFixed(1)}%)
                  </span>
                </div>
                <ProgressBar value={progress.filled_slots} max={progress.total_slots} />
              </div>

              {/* Per leg */}
              {progress.legs.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Per Leg
                  </p>
                  {progress.legs.map((leg) => (
                    <div key={leg.leg_id}>
                      <div className="mb-0.5 flex items-center justify-between text-sm">
                        <span className="text-slate-700">
                          <span className="font-mono text-xs text-slate-400 mr-2">
                            L{leg.leg_order + 1}
                          </span>
                          {leg.origin_query} → {leg.destination_query}
                        </span>
                        <span className="text-xs text-slate-500">
                          {leg.filled_slots}/{leg.total_slots} (
                          {leg.coverage_percent.toFixed(1)}%)
                        </span>
                      </div>
                      <ProgressBar value={leg.filled_slots} max={leg.total_slots} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No progress data yet. Trigger a collection to start.</p>
          )}
        </Card>

        {/* Prices / Journey tabs */}
        <Card className="p-5">
          {/* Tab bar */}
          <div className="mb-4 flex items-center gap-1 border-b border-slate-200 pb-0">
            <button
              onClick={() => setActiveTab("prices")}
              className={`rounded-t-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "prices"
                  ? "border-b-2 border-brand-600 text-brand-700"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              Prices by leg
            </button>
            {isMultiLeg && (
              <button
                onClick={() => setActiveTab("journey")}
                className={`rounded-t-lg px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "journey"
                    ? "border-b-2 border-brand-600 text-brand-700"
                    : "text-slate-500 hover:text-slate-800"
                }`}
              >
                Journey total
              </button>
            )}
          </div>

          {activeTab === "prices" && (
            <>
              {/* Filters */}
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Leg:</span>
                  <select
                    value={selectedLegOrder}
                    onChange={(e) =>
                      setSelectedLegOrder(e.target.value === "" ? "" : Number(e.target.value))
                    }
                    className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    <option value="">All legs</option>
                    {profile.legs.map((leg, idx) => (
                      <option key={leg.id} value={idx}>
                        L{idx + 1}: {leg.origin_query} → {leg.destination_query}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500">Stops:</span>
                  <select
                    value={stopsFilter}
                    onChange={(e) => setStopsFilter(e.target.value)}
                    className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  >
                    {STOPS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                {pricesQuery.data && (
                  <span className="ml-auto text-xs text-slate-400">
                    {pricesQuery.data.length} rows
                  </span>
                )}
              </div>
              <PriceTable
                prices={(pricesQuery.data ?? []).map(toDailyPrice)}
                isLoading={pricesQuery.isLoading}
              />
            </>
          )}

          {activeTab === "journey" && isMultiLeg && (
            <JourneyView
              journeys={journeyQuery.data ?? []}
              isLoading={journeyQuery.isLoading}
              profile={profile}
            />
          )}
        </Card>
      </div>
    </ErrorBoundary>
  );
}

// ── Journey view ──────────────────────────────────────────────────────────────

function JourneyView({
  journeys,
  isLoading,
  profile,
}: {
  journeys: JourneyRow[];
  isLoading: boolean;
  profile: { legs: { origin_query: string; destination_query: string }[] };
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (isLoading) return <Skeleton className="h-48" />;

  if (journeys.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        No journey data yet. Prices need to be collected for all legs on overlapping dates.
      </p>
    );
  }

  const formatCurrency = (price: number, currency: string) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency }).format(price);

  return (
    <div className="space-y-2">
      <p className="mb-3 text-xs text-slate-500">
        Showing cheapest combined trip across all {profile.legs.length} legs — sorted by total price.
      </p>
      {journeys.slice(0, 100).map((row) => (
        <div
          key={row.start_date}
          className="rounded-lg border border-slate-200 bg-slate-50"
        >
          {/* Summary row */}
          <button
            onClick={() => setExpanded(expanded === row.start_date ? null : row.start_date)}
            className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-slate-100 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-4">
              <span className="text-sm font-semibold text-slate-900">
                {new Date(row.start_date).toLocaleDateString("en-US", {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                })}
              </span>
              <span className="text-xs text-slate-500">
                {row.legs.map((l) => l.origin).join(" → ")} → {row.legs[row.legs.length - 1].destination}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-base font-bold text-brand-700">
                {formatCurrency(row.total_price, row.currency)}
              </span>
              <span className="text-xs text-slate-400">
                {expanded === row.start_date ? "▲" : "▼"}
              </span>
            </div>
          </button>

          {/* Expanded leg breakdown */}
          {expanded === row.start_date && (
            <div className="border-t border-slate-200 px-4 py-3 space-y-2">
              {row.legs.map((leg) => (
                <div
                  key={leg.leg_order}
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-400">L{leg.leg_order + 1}</span>
                    <span className="font-medium text-slate-700">
                      {leg.origin} → {leg.destination}
                    </span>
                    <span className="text-slate-400">
                      {new Date(leg.depart_date).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                    {leg.airline && (
                      <span className="text-xs text-slate-400">{leg.airline}</span>
                    )}
                    {leg.stops !== null && (
                      <span className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${
                        leg.stops === 0
                          ? "bg-green-100 text-green-700"
                          : "bg-amber-100 text-amber-700"
                      }`}>
                        {leg.stops === 0 ? "Direct" : `${leg.stops} stop${leg.stops > 1 ? "s" : ""}`}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-800">
                      {formatCurrency(leg.price, leg.currency)}
                    </span>
                    {leg.deep_link && (
                      <a
                        href={leg.deep_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-600 hover:text-brand-700"
                        title="Book this flight"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
              <div className="border-t border-slate-200 pt-2 flex justify-end">
                <span className="text-sm font-bold text-brand-700">
                  Total: {formatCurrency(row.total_price, row.currency)}
                </span>
              </div>
            </div>
          )}
        </div>
      ))}
      {journeys.length > 100 && (
        <p className="text-center text-xs text-slate-400">
          Showing 100 of {journeys.length} combinations
        </p>
      )}
    </div>
  );
}
