import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchPriceTrend, fetchPrices } from "../api/prices";
import { listRouteGroups } from "../api/route-groups";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PriceChart } from "../components/PriceChart";
import { PriceTable } from "../components/PriceTable";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { usePageTitle } from "../utils/usePageTitle";
import { DateRangeInput } from "../components/ui/DateRangeInput";
import { Select } from "../components/ui/Select";

interface Filters {
  route_group_id: string;
  origin: string;
  date_from: string;
  date_to: string;
}

const EMPTY_FILTERS: Filters = {
  route_group_id: "",
  origin: "",
  date_from: "",
  date_to: "",
};

export function DataExplorerPage() {
  usePageTitle("Data Explorer");
  const [pending, setPending] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const selectedGroup = groupsQuery.data?.find(
    (g) => g.id === pending.route_group_id,
  );

  function handleGroupChange(id: string) {
    setPending({ ...EMPTY_FILTERS, route_group_id: id });
  }

  function handleApply() {
    setApplied({ ...pending });
  }

  // Price table query
  const pricesQuery = useQuery({
    queryKey: ["explorer-prices", applied],
    queryFn: () =>
      fetchPrices({
        route_group_id: applied.route_group_id || undefined,
        origin: applied.origin || undefined,
        date_from: applied.date_from || undefined,
        date_to: applied.date_to || undefined,
        limit: 1000,
      }),
    enabled: !!applied.route_group_id,
  });

  // Trend chart — needs origin + destination
  const appliedGroup = groupsQuery.data?.find(
    (g) => g.id === applied.route_group_id,
  );
  const trendOrigin = applied.origin || appliedGroup?.origins[0] || "";
  const trendDest = appliedGroup?.destinations[0] || "";

  const trendQuery = useQuery({
    queryKey: ["explorer-trend", applied, trendOrigin, trendDest],
    queryFn: () =>
      fetchPriceTrend({
        origin: trendOrigin,
        destination: trendDest,
        date_from: applied.date_from || undefined,
        date_to: applied.date_to || undefined,
      }),
    enabled: !!trendOrigin && !!trendDest,
  });

  return (
    <ErrorBoundary>
    <div className="space-y-6">
      {/* Filters */}
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[180px]">
            <Select
              label="Route Group"
              value={pending.route_group_id}
              onChange={(e) => handleGroupChange(e.target.value)}
            >
              <option value="">Select group…</option>
              {groupsQuery.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </Select>
          </div>

          <div className="min-w-[120px]">
            <Select
              label="Origin"
              value={pending.origin}
              onChange={(e) =>
                setPending((f) => ({ ...f, origin: e.target.value }))
              }
              disabled={!selectedGroup}
            >
              <option value="">All origins</option>
              {selectedGroup?.origins.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </div>

          <DateRangeInput
            dateFrom={pending.date_from}
            dateTo={pending.date_to}
            onDateFromChange={(v) =>
              setPending((f) => ({ ...f, date_from: v }))
            }
            onDateToChange={(v) => setPending((f) => ({ ...f, date_to: v }))}
          />

          <Button
            variant="primary"
            onClick={handleApply}
            disabled={!pending.route_group_id}
          >
            Apply
          </Button>
        </div>
      </Card>

      {/* No group selected */}
      {!applied.route_group_id && (
        <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-400">
          <p className="text-sm">
            Select a route group and click Apply to explore prices.
          </p>
        </div>
      )}

      {/* Chart */}
      {applied.route_group_id && (
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-slate-700">
            Price Trend
            {trendOrigin && trendDest && (
              <span className="ml-2 font-mono text-xs font-normal text-slate-400">
                {trendOrigin} → {trendDest}
              </span>
            )}
          </h3>
          <PriceChart data={trendQuery.data ?? []} />
        </Card>
      )}

      {/* Price Table */}
      {applied.route_group_id && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">
              Price Data
            </h3>
            {pricesQuery.data && (
              <span className="text-xs text-slate-400">
                Showing {pricesQuery.data.length} results
              </span>
            )}
          </div>
          <PriceTable
            prices={pricesQuery.data ?? []}
            isLoading={pricesQuery.isLoading}
          />
        </Card>
      )}
    </div>
    </ErrorBoundary>
  );
}
