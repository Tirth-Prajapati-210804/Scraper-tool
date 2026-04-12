import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Globe,
  MapPin,
  Play,
} from "lucide-react";
import { useState } from "react";
import { triggerCollection } from "../api/collection";
import { listRouteGroups } from "../api/route-groups";
import { fetchHealth, fetchOverviewStats } from "../api/stats";
import { ProviderStatus } from "../components/ProviderStatus";
import { RouteGroupCard } from "../components/RouteGroupCard";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { formatRelativeTime, formatNumber } from "../utils/format";

export function DashboardPage() {
  const [triggering, setTriggering] = useState(false);

  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: fetchOverviewStats,
    refetchInterval: 60_000,
  });

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const stats = statsQuery.data;
  const groups = groupsQuery.data ?? [];
  const health = healthQuery.data;

  async function handleTriggerAll() {
    setTriggering(true);
    try {
      await triggerCollection();
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Overview</h2>
          {stats?.last_collection_at && (
            <p className="text-sm text-slate-500">
              Last collection:{" "}
              {formatRelativeTime(stats.last_collection_at)}
            </p>
          )}
        </div>
        <Button
          variant="secondary"
          onClick={handleTriggerAll}
          loading={triggering}
        >
          <Play className="h-4 w-4" />
          Trigger collection
        </Button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {statsQuery.isLoading ? (
          <>
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </>
        ) : (
          <>
            <StatCard
              label="Route Groups"
              value={stats?.active_route_groups ?? 0}
              icon={Globe}
            />
            <StatCard
              label="Prices Collected"
              value={
                stats ? formatNumber(stats.total_prices_collected) : "0"
              }
              icon={Database}
            />
            <StatCard
              label="Origins"
              value={stats?.total_origins ?? 0}
              icon={MapPin}
            />
            <StatCard
              label="Last Run"
              value={
                stats?.last_collection_at
                  ? formatRelativeTime(stats.last_collection_at)
                  : "Never"
              }
              icon={Activity}
            />
          </>
        )}
      </div>

      {/* Route Group Cards */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Route Groups
        </h2>
        {groupsQuery.isLoading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[...Array(2)].map((_, i) => (
              <Skeleton key={i} className="h-52 rounded-xl" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-10 text-center text-slate-400">
            <p className="text-sm">No route groups found.</p>
            <p className="mt-1 text-xs">
              Run the seed script to add groups.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {groups.map((group) => (
              <RouteGroupCard key={group.id} group={group} />
            ))}
          </div>
        )}
      </div>

      {/* Provider Status */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Provider Status
        </h2>
        {healthQuery.isLoading ? (
          <Skeleton className="h-16 rounded-xl" />
        ) : (
          <ProviderStatus health={health} />
        )}
      </div>
    </div>
  );
}
