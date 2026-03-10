import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { TrendingDown } from "lucide-react";
import { getPriceHistory } from "@/api/client";
import { cn } from "@/lib/utils";

export interface QueryStatusInfo {
  status: "pending" | "error" | "success";
  fetchStatus: "fetching" | "paused" | "idle";
  dataUpdatedAt: number;
  error: unknown;
}

interface PriceChartProps {
  productId: string;
  currency: string;
  onQueryStatus?: (info: QueryStatusInfo) => void;
}

const DAY_OPTIONS = [
  { label: "7d", value: 7 },
  { label: "30d", value: 30 },
  { label: "90d", value: 90 },
] as const;

type DayRange = (typeof DAY_OPTIONS)[number]["value"];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatPrice(value: number, currency: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(value);
}

export default function PriceChart({ productId, currency, onQueryStatus }: PriceChartProps) {
  const [dayRange, setDayRange] = useState<DayRange>(30);

  const { data: points = [], isLoading, status, fetchStatus, dataUpdatedAt, error } = useQuery({
    queryKey: ["prices", productId, dayRange],
    queryFn: () => getPriceHistory(productId, dayRange).then((r) => r.data),
  });

  useEffect(() => {
    onQueryStatus?.({ status, fetchStatus, dataUpdatedAt, error });
  }, [status, fetchStatus, dataUpdatedAt, error, onQueryStatus]);

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* Header row */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Price History</h2>
        <div className="flex gap-1 rounded-md border p-0.5">
          {DAY_OPTIONS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setDayRange(value)}
              className={cn(
                "rounded px-2.5 py-0.5 text-xs font-medium transition-colors",
                dayRange === value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      {isLoading ? (
        <div className="flex h-[240px] items-center justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : points.length === 0 ? (
        <div className="flex h-[240px] flex-col items-center justify-center gap-2 text-muted-foreground">
          <TrendingDown className="h-8 w-8 opacity-30" />
          <p className="text-sm">No price data yet</p>
          <p className="text-xs">Data will appear after the first price check</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={points} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="scraped_at"
              tickFormatter={formatDate}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v) => formatPrice(v, currency)}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
              width={72}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                borderColor: "hsl(var(--border))",
                borderRadius: "6px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [formatPrice(value, currency), "Price"]}
              labelFormatter={(label: string) =>
                new Date(label).toLocaleString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              }
            />
            <Line
              type="monotone"
              dataKey="price"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              stroke="hsl(var(--primary))"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
