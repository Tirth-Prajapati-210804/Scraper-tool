import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { fetchCollectionRuns, fetchScrapeLogs } from "../api/collection";
import { listRouteGroups } from "../api/route-groups";
import { CollectionRunsTable } from "../components/CollectionRunsTable";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ScrapeLogsTable } from "../components/ScrapeLogsTable";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import type { ScrapeLogEntry } from "../types/price";
import { usePageTitle } from "../utils/usePageTitle";

export function CollectionLogsPage() {
  usePageTitle("Collection Logs");
  const [filterGroupId, setFilterGroupId] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const runsQuery = useQuery({
    queryKey: ["collection-runs"],
    queryFn: () => fetchCollectionRuns(20),
    refetchInterval: 30_000,
  });

  const logsQuery = useQuery({
    queryKey: ["scrape-logs", filterGroupId],
    queryFn: () =>
      fetchScrapeLogs({
        route_group_id: filterGroupId || undefined,
        limit: 100,
      }),
    refetchInterval: 30_000,
  });

  // Client-side filter by provider and status
  const filteredLogs = useMemo<ScrapeLogEntry[]>(() => {
    let logs = logsQuery.data ?? [];
    if (filterProvider)
      logs = logs.filter((l) => l.provider === filterProvider);
    if (filterStatus)
      logs = logs.filter((l) => l.status === filterStatus);
    return logs;
  }, [logsQuery.data, filterProvider, filterStatus]);

  // Unique providers from current logs for filter dropdown
  const providers = useMemo(() => {
    const set = new Set((logsQuery.data ?? []).map((l) => l.provider));
    return [...set].sort();
  }, [logsQuery.data]);

  return (
    <ErrorBoundary>
    <div className="space-y-6">
      {/* Collection Runs */}
      <Card>
        <h3 className="mb-4 text-sm font-semibold text-slate-700">
          Collection Runs
        </h3>
        <CollectionRunsTable
          runs={runsQuery.data ?? []}
          isLoading={runsQuery.isLoading}
        />
      </Card>

      {/* Scrape Logs */}
      <Card>
        <div className="mb-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-700">
            Recent Scrape Logs (latest 100)
          </h3>
          {/* Filters */}
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[180px]">
              <Select
                label="Route Group"
                value={filterGroupId}
                onChange={(e) => setFilterGroupId(e.target.value)}
              >
                <option value="">All groups</option>
                {groupsQuery.data?.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="min-w-[130px]">
              <Select
                label="Provider"
                value={filterProvider}
                onChange={(e) => setFilterProvider(e.target.value)}
              >
                <option value="">All providers</option>
                {providers.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </Select>
            </div>

            <div className="min-w-[130px]">
              <Select
                label="Status"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="">All statuses</option>
                <option value="success">Success</option>
                <option value="error">Error</option>
                <option value="no_results">No results</option>
                <option value="rate_limited">Rate limited</option>
              </Select>
            </div>

            {filteredLogs.length !== (logsQuery.data?.length ?? 0) && (
              <span className="mt-5 text-xs text-slate-400">
                {filteredLogs.length} / {logsQuery.data?.length ?? 0} shown
              </span>
            )}
          </div>
        </div>

        <ScrapeLogsTable
          logs={filteredLogs}
          isLoading={logsQuery.isLoading}
        />
      </Card>
    </div>
    </ErrorBoundary>
  );
}
