import type { RouteGroupProgress } from "../types/route-group";
import { formatNumber } from "../utils/format";
import { ProgressBar } from "./ui/ProgressBar";

interface DateCoverageGridProps {
  progress: RouteGroupProgress;
}

export function DateCoverageGrid({ progress }: DateCoverageGridProps) {
  return (
    <div className="space-y-4">
      {/* Overall */}
      <div>
        <div className="mb-1 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">Overall</span>
          <span className="text-slate-500">
            {formatNumber(progress.dates_with_data)}/
            {formatNumber(progress.total_dates)} (
            {progress.coverage_percent.toFixed(1)}%)
          </span>
        </div>
        <ProgressBar
          value={progress.dates_with_data}
          max={progress.total_dates}
        />
      </div>

      {/* Per origin */}
      {Object.keys(progress.per_origin).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Per Origin
          </p>
          {Object.entries(progress.per_origin).map(([origin, data]) => {
            const pct =
              data.total > 0
                ? ((data.collected / data.total) * 100).toFixed(1)
                : "0.0";
            return (
              <div key={origin}>
                <div className="mb-0.5 flex items-center justify-between text-sm">
                  <span className="font-mono font-medium text-slate-700">
                    {origin}
                  </span>
                  <span className="text-xs text-slate-500">
                    {data.collected}/{data.total} ({pct}%)
                  </span>
                </div>
                <ProgressBar value={data.collected} max={data.total} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
