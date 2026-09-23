import { Activity, Film, Percent, TrendingUp } from "lucide-react";
import type { AdminStats } from "@/api/client";
import { useCurrency } from "@/lib/currency";
import { dashboardRangeLabel, type DashboardFilterState } from "@/pages/dashboard/DashboardFilters";
import { DashboardKpiCard } from "@/pages/dashboard/DashboardKpiCard";
import { calcProfitFen, sumDailyUsage } from "@/pages/dashboard/dashboardMetrics";

type DashboardPeriodKpisProps = {
  stats: AdminStats | null;
  filters: DashboardFilterState;
  loading: boolean;
};

/** 第二行 KPI：随筛选时间窗变化的调用/扣费/毛利/项目规模 */
export function DashboardPeriodKpis({ stats, filters, loading }: DashboardPeriodKpisProps) {
  const { format } = useCurrency();
  const placeholder = loading ? "…" : "—";
  const rangeLabel = dashboardRangeLabel(filters.days);
  const period = sumDailyUsage(stats?.daily_usage ?? []);
  const profitFen = calcProfitFen(period.charge_fen, period.cost_fen);
  const profitPct =
    period.charge_fen > 0 ? `${((profitFen / period.charge_fen) * 100).toFixed(1)}%` : undefined;

  return (
    <div className="admin-dashboard-kpi-grid admin-dashboard-kpi-grid--secondary">
      <DashboardKpiCard
        label={`Lượt gọi ${rangeLabel.toLowerCase()}`}
        value={stats ? period.calls.toLocaleString("vi-VN") : placeholder}
        hint={stats ? `Tổng ${stats.usage_calls_total ?? 0} lượt` : "Số lượt gọi"}
        icon={Activity}
        tone="mint"
      />
      <DashboardKpiCard
        label={`Tiền đã trừ ${rangeLabel.toLowerCase()}`}
        value={stats ? format(period.charge_fen) : placeholder}
        hint={stats ? `Tháng này ${format(stats.usage_charge_month_fen ?? 0)}` : "Tiền đã trừ của người dùng"}
        icon={TrendingUp}
        tone="blue"
      />
      <DashboardKpiCard
        label={`Lợi nhuận gộp ${rangeLabel.toLowerCase()}`}
        value={stats ? format(profitFen) : placeholder}
        hint={stats ? `Chi phí ${format(period.cost_fen)}` : "Tiền đã trừ − chi phí"}
        icon={Percent}
        tone="rose"
        trend={profitPct ? `Biên lợi nhuận ${profitPct}` : undefined}
      />
      <DashboardKpiCard
        label="Dự án phim ngắn"
        value={stats ? stats.drama_project_count ?? 0 : placeholder}
        hint={stats ? `${stats.user_count} người dùng` : "Số dự án"}
        icon={Film}
        tone="slate"
      />
    </div>
  );
}
