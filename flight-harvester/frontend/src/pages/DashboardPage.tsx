import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Database,
  Globe,
  MapPin,
  Play,
  Plus,
  Square,
} from "lucide-react";
import { useState } from "react";
import { getCollectionStatus, stopCollection, triggerCollection } from "../api/collection";
import { listRouteGroups } from "../api/route-groups";
import { fetchHealth, fetchOverviewStats } from "../api/stats";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ProviderStatus } from "../components/ProviderStatus";
import { RouteGroupCard } from "../components/RouteGroupCard";
import { RouteGroupForm } from "../components/RouteGroupForm";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../context/ToastContext";
import { formatRelativeTime, formatNumber } from "../utils/format";
import { usePageTitle } from "../utils/usePageTitle";

export function DashboardPage() {
  usePageTitle("Dashboard");
  const { showToast } = useToast();
  const qc = useQueryClient();
  const [triggering, setTriggering] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

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

  const statusQuery = useQuery({
    queryKey: ["collection-status"],
    queryFn: getCollectionStatus,
    refetchInterval: (data) => (data?.is_collecting ? 3_000 : 15_000),
  });

  const stopMut = useMutation({
    mutationFn: stopCollection,
    onSuccess: () => {
      showToast("Stop signal sent", "success");
      qc.invalidateQueries({ queryKey: ["collection-status"] });
    },
    onError: () => showToast("Failed to stop collection", "error"),
  });

  const stats = statsQuery.data;
  const groups = groupsQuery.data ?? [];
  const health = healthQuery.data;
  const isCollecting = statusQuery.data?.is_collecting ?? false;

  async function handleTriggerAll() {
    setTriggering(true);
    try {
      const res = await triggerCollection();
      if (res.status === "already_running") {
        showToast("Collection is already running", "info" as never);
      } else {
        showToast("Collection triggered", "success");
        qc.invalidateQueries({ queryKey: ["collection-status"] });
      }
    } catch {
      showToast("Failed to trigger collection", "error");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Overview</h2>
            {stats?.last_collection_at && (
              <p className="text-sm text-slate-500">
                Last collection: {formatRelativeTime(stats.last_collection_at)}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="h-4 w-4" />
              New group
            </Button>
            {isCollecting ? (
              <Button
                variant="secondary"
                onClick={() => stopMut.mutate()}
                loading={stopMut.isPending}
                className="border-red-200 text-red-600 hover:bg-red-50"
              >
                <Square className="h-4 w-4" />
                Stop collection
              </Button>
            ) : (
              <Button
                variant="secondary"
                onClick={handleTriggerAll}
                loading={triggering}
              >
                <Play className="h-4 w-4" />
                Trigger collection
              </Button>
            )}
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
                value={stats ? formatNumber(stats.total_prices_collected) : "0"}
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
              <p className="text-sm font-medium">No route groups configured.</p>
              <p className="mt-1 text-xs">
                Create one to start collecting flight prices.
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

      <RouteGroupForm
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        initial={null}
      />
    </ErrorBoundary>
  );
}
