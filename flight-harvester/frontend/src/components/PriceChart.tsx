import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceTrend } from "../types/price";

interface PriceChartProps {
  data: PriceTrend[];
}

function fmtDate(d: unknown): string {
  if (typeof d !== "string") return String(d ?? "");
  return new Date(d + "T00:00:00").toLocaleDateString("en-CA");
}

export function PriceChart({ data }: PriceChartProps) {
  if (!data.length) {
    return (
      <p className="py-12 text-center text-sm text-slate-400">
        No price data available
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: "#64748b" }}
          tickFormatter={(d: unknown) => {
            const s = typeof d === "string" ? d : String(d);
            return new Date(s + "T00:00:00").toLocaleDateString("en-CA", {
              month: "short",
              day: "numeric",
            });
          }}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "#64748b" }}
          tickFormatter={(v: unknown) =>
            `$${Number(v).toLocaleString()}`
          }
          width={68}
        />
        <Tooltip
          formatter={(value: unknown) => [
            `$${Number(value).toLocaleString()}`,
            "Price",
          ]}
          labelFormatter={fmtDate}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid #e2e8f0",
            fontSize: "13px",
          }}
        />
        <Line
          type="monotone"
          dataKey="price"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
