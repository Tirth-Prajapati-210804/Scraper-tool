import { CheckCircle, Loader2, Square, XCircle } from "lucide-react";
import type { CollectionRun } from "../types/price";
import { formatRelativeTime } from "../utils/format";
import { Skeleton } from "./ui/Skeleton";

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return "—";
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

interface CollectionRunsTableProps {
  runs: CollectionRun[];
  isLoading: boolean;
  onStop?: () => void;
  stopping?: boolean;
}

export function CollectionRunsTable({
  runs,
  isLoading,
  onStop,
  stopping,
}: CollectionRunsTableProps) {
  if (isLoading) return <Skeleton className="h-48 rounded-xl" />;

  if (!runs.length) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        No collection runs yet.
      </p>
    );
  }

  const hasRunning = runs.some((r) => r.status === "running");

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2.5">Started</th>
            <th className="px-3 py-2.5">Duration</th>
            <th className="px-3 py-2.5">Status</th>
            <th className="px-3 py-2.5">Routes</th>
            <th className="px-3 py-2.5 text-right">Prices</th>
            {hasRunning && onStop && <th className="px-3 py-2.5" />}
          </tr>
        </thead>
        <tbody>
          {runs.map((run, i) => (
            <tr key={run.id} className={i % 2 !== 0 ? "bg-slate-50/50" : ""}>
              <td className="px-3 py-2 text-slate-600">
                {formatRelativeTime(run.started_at)}
              </td>
              <td className="px-3 py-2 text-slate-600">
                {formatDuration(run.started_at, run.finished_at)}
              </td>
              <td className="px-3 py-2">
                {run.status === "completed" ? (
                  <span className="flex items-center gap-1 text-green-600">
                    <CheckCircle className="h-3.5 w-3.5" /> done
                  </span>
                ) : run.status === "failed" ? (
                  <span className="flex items-center gap-1 text-red-500">
                    <XCircle className="h-3.5 w-3.5" /> failed
                  </span>
                ) : run.status === "stopped" ? (
                  <span className="flex items-center gap-1 text-amber-500">
                    <Square className="h-3.5 w-3.5" /> stopped
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-brand-600">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> running
                  </span>
                )}
              </td>
              <td className="px-3 py-2 text-slate-700">
                {run.routes_success}/{run.routes_total}
              </td>
              <td className="px-3 py-2 text-right text-slate-700">
                {run.dates_scraped.toLocaleString()}
              </td>
              {hasRunning && onStop && (
                <td className="px-3 py-2 text-right">
                  {run.status === "running" && (
                    <button
                      onClick={onStop}
                      disabled={stopping}
                      className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                      title="Stop this collection"
                    >
                      <Square className="h-3 w-3" />
                      {stopping ? "Stopping…" : "Stop"}
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
