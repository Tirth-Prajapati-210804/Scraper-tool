import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getProfilePrices,
  getSearchProfile,
  getSearchProfileProgress,
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

export function SearchProfileDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const { showToast } = useToast();
  const [triggering, setTriggering] = useState(false);
  const [selectedLegOrder, setSelectedLegOrder] = useState<number | "">("");

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
    queryKey: ["search-profile-prices", id, selectedLegOrder],
    queryFn: () =>
      getProfilePrices(id!, {
        leg_order: selectedLegOrder !== "" ? selectedLegOrder : undefined,
        limit: 500,
      }),
    enabled: !!id,
  });

  const profile = profileQuery.data;
  usePageTitle(profile?.name ?? "Search Profile");

  async function handleTrigger() {
    if (!id) return;
    setTriggering(true);
    try {
      await triggerGroupCollection(id);
      showToast("Collection triggered", "success");
      qc.invalidateQueries({ queryKey: ["search-profile-progress", id] });
      qc.invalidateQueries({ queryKey: ["search-profile-prices", id] });
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

        {/* Prices Table */}
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h3 className="text-sm font-semibold text-slate-700">Collected Prices</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Filter by leg:</span>
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
              {pricesQuery.data && (
                <span className="text-xs text-slate-400">
                  {pricesQuery.data.length} rows
                </span>
              )}
            </div>
          </div>
          <PriceTable
            prices={(pricesQuery.data ?? []).map(toDailyPrice)}
            isLoading={pricesQuery.isLoading}
          />
        </Card>
      </div>
    </ErrorBoundary>
  );
}
