import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AdminDailyUsage } from "@/api/client";
import { useCurrency } from "@/lib/currency";
import type { DashboardMetric } from "./DashboardFilters";

type UsageTrendChartProps = {
  data: AdminDailyUsage[];
  metric: DashboardMetric;
};

function metricLabel(metric: DashboardMetric): string {
  if (metric === "cost") return "Chi phí nhà cung cấp";
  if (metric === "calls") return "Số lượt gọi";
  return "Số tiền đã trừ";
}

function readMetric(row: AdminDailyUsage, metric: DashboardMetric): number {
  if (metric === "cost") return row.cost_fen ?? 0;
  if (metric === "calls") return row.calls;
  return row.charge_fen;
}

type MoneyFormatter = (fen: number) => string;

// 按指标格式化数值（金额走当前展示货币）
function formatMetric(value: number, metric: DashboardMetric, format: MoneyFormatter): string {
  if (metric === "calls") return value.toLocaleString("vi-VN");
  return format(value);
}

function shortDate(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : iso;
}

// YYYY-MM-DD → DD/MM/YYYY（提示框用）
function fullDate(iso: string): string {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : iso;
}

/** 用量趋势面积图 */
export function UsageTrendChart({ data, metric }: UsageTrendChartProps) {
  const { format } = useCurrency();
  const chartData = data.map((row) => ({
    date: row.date,
    label: shortDate(row.date),
    value: readMetric(row, metric),
  }));

  if (chartData.length === 0) {
    return <div className="admin-chart-empty">Chưa có dữ liệu xu hướng</div>;
  }

  return (
    <div className="admin-chart-wrap">
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="usageTrendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--admin-accent)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="var(--admin-accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--admin-border)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--admin-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            minTickGap={16}
          />
          <YAxis
            tick={{ fill: "var(--admin-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={metric === "calls" ? 36 : 52}
            tickFormatter={(v) => (metric === "calls" ? String(v) : format(Number(v)))}
          />
          <Tooltip
            contentStyle={{
              background: "var(--admin-card)",
              border: "1px solid var(--admin-border)",
              borderRadius: "10px",
              fontSize: "12px",
            }}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as { date?: string } | undefined;
              return row?.date ? fullDate(row.date) : "";
            }}
            formatter={(value) => [formatMetric(Number(value ?? 0), metric, format), metricLabel(metric)]}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--admin-forest)"
            strokeWidth={2}
            fill="url(#usageTrendFill)"
            dot={false}
            activeDot={{ r: 4, fill: "var(--admin-forest)" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
