import type { ScrapeLogEntry } from "../types/price";
import { formatRelativeTime } from "../utils/format";
import { Skeleton } from "./ui/Skeleton";

function StatusIcon({ status }: { status: ScrapeLogEntry["status"] }) {
  if (status === "success")
    return <span className="font-medium text-green-600">✓</span>;
  if (status === "no_results")
    return <span className="font-medium text-amber-500">○</span>;
  return <span className="font-medium text-red-500">✗</span>;
}

function DurationCell({ ms }: { ms: number | null }) {
  if (ms == null) return <span className="text-slate-400">—</span>;
  const color =
    ms < 1000
      ? "text-green-600"
      : ms < 5000
        ? "text-amber-600"
        : "text-red-500";
  return <span className={color}>{ms.toLocaleString()}</span>;
}

interface ScrapeLogsTableProps {
  logs: ScrapeLogEntry[];
  isLoading: boolean;
}

export function ScrapeLogsTable({ logs, isLoading }: ScrapeLogsTableProps) {
  if (isLoading) return <Skeleton className="h-64 rounded-xl" />;

  if (!logs.length) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        No scrape logs found.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2.5">Time</th>
            <th className="px-3 py-2.5">Route</th>
            <th className="px-3 py-2.5">Provider</th>
            <th className="px-3 py-2.5">Status</th>
            <th className="px-3 py-2.5 text-right">Price</th>
            <th className="px-3 py-2.5 text-right">Ms</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, i) => (
            <tr
              key={log.id}
              className={i % 2 !== 0 ? "bg-slate-50/50" : ""}
              title={log.error_message ?? undefined}
            >
              <td className="px-3 py-2 text-slate-500">
                {formatRelativeTime(log.created_at)}
              </td>
              <td className="px-3 py-2 font-mono text-xs text-slate-700">
                {log.origin}→{log.destination}
              </td>
              <td className="px-3 py-2 capitalize text-slate-600">
                {log.provider}
              </td>
              <td className="px-3 py-2">
                <StatusIcon status={log.status} />
              </td>
              <td className="px-3 py-2 text-right text-slate-700">
                {log.cheapest_price != null
                  ? `$${Math.round(log.cheapest_price).toLocaleString()}`
                  : "—"}
              </td>
              <td className="px-3 py-2 text-right">
                <DurationCell ms={log.duration_ms} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
