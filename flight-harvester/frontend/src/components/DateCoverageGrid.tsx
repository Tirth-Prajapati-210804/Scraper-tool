import { useMemo } from "react";
import type { RouteGroupProgress } from "../types/route-group";
import { formatNumber } from "../utils/format";

interface DateCoverageGridProps {
  progress: RouteGroupProgress;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function toIso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

interface MonthGroup {
  label: string;
  days: { iso: string; hasData: boolean; isToday: boolean }[];
}

export function DateCoverageGrid({ progress }: DateCoverageGridProps) {
  const scrapedSet = useMemo(
    () => new Set(progress.scraped_dates),
    [progress.scraped_dates],
  );

  // Build the full expected date range: tomorrow → total_dates days ahead
  // We infer days_ahead from total_dates and the number of origin×dest combinations
  const originCount = Object.keys(progress.per_origin).length || 1;
  // total_dates = origins * destinations * days_ahead — we can't know destinations
  // separately, so we derive the day span from scraped_dates range or fall back
  // to a best-effort estimate
  const daySpan = useMemo(() => {
    if (progress.scraped_dates.length >= 2) {
      const sorted = [...progress.scraped_dates].sort();
      const first = new Date(sorted[0] + "T00:00:00");
      const last = new Date(sorted[sorted.length - 1] + "T00:00:00");
      const diff = Math.round((last.getTime() - first.getTime()) / 86_400_000) + 1;
      return Math.max(diff, 30);
    }
    // Fall back: total_dates / per_origin_size gives approx days_ahead
    const approx = originCount > 0 ? Math.round(progress.total_dates / originCount) : 90;
    return Math.max(approx, 30);
  }, [progress.scraped_dates, progress.total_dates, originCount]);

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  // Anchor: use earliest scraped date if available, else tomorrow
  const startDate = useMemo(() => {
    if (progress.scraped_dates.length > 0) {
      const sorted = [...progress.scraped_dates].sort();
      return new Date(sorted[0] + "T00:00:00");
    }
    return addDays(today, 1);
  }, [progress.scraped_dates, today]);

  const months = useMemo<MonthGroup[]>(() => {
    const groups: MonthGroup[] = [];
    let current = new Date(startDate);

    for (let i = 0; i < daySpan; i++) {
      const iso = toIso(current);
      const monthKey = current.toLocaleDateString("en-US", {
        month: "short",
        year: "numeric",
      });
      const isToday = iso === toIso(today);

      let group = groups.find((g) => g.label === monthKey);
      if (!group) {
        group = { label: monthKey, days: [] };
        groups.push(group);
      }
      group.days.push({ iso, hasData: scrapedSet.has(iso), isToday });
      current = addDays(current, 1);
    }
    return groups;
  }, [startDate, daySpan, scrapedSet, today]);

  return (
    <div className="space-y-5">
      {/* Summary row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-sm">
          <span className="font-medium text-slate-700">
            {formatNumber(progress.dates_with_data)}{" "}
            <span className="font-normal text-slate-500">
              / {formatNumber(progress.total_dates)} dates collected
            </span>
          </span>
          <span className="font-semibold text-brand-600">
            {progress.coverage_percent.toFixed(1)}%
          </span>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-brand-500" />
            Collected
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-slate-200" />
            Pending
          </span>
        </div>
      </div>

      {/* Calendar months */}
      <div className="space-y-4">
        {months.map((month) => (
          <div key={month.label}>
            <p className="mb-1.5 text-xs font-medium text-slate-500">{month.label}</p>
            <div className="flex flex-wrap gap-1">
              {month.days.map(({ iso, hasData, isToday }) => (
                <div
                  key={iso}
                  title={iso}
                  className={[
                    "h-5 w-5 rounded-sm transition-colors",
                    hasData
                      ? "bg-brand-500 hover:bg-brand-600"
                      : "bg-slate-200 hover:bg-slate-300",
                    isToday ? "ring-2 ring-amber-400 ring-offset-1" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Per-origin breakdown */}
      {Object.keys(progress.per_origin).length > 1 && (
        <div className="border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
            Per Origin
          </p>
          <div className="space-y-2">
            {Object.entries(progress.per_origin).map(([origin, data]) => {
              const pct =
                data.total > 0
                  ? Math.round((data.collected / data.total) * 100)
                  : 0;
              return (
                <div key={origin} className="flex items-center gap-3">
                  <span className="w-10 font-mono text-xs font-medium text-slate-700">
                    {origin}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-brand-500 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs text-slate-500">
                    {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
