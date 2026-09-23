import {
  Activity,
  Banknote,
  CheckCircle2,
  CircleDollarSign,
  Clapperboard,
  Film,
  Layers,
  Percent,
  TrendingDown,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { AdminStats } from "@/api/client";
import type { DashboardInsightItem } from "@/pages/dashboard/DashboardInsightGrid";
import {
  calcProfitFen,
  sumDailyUsage,
  sumProjectStatuses,
  type MoneyFormatter,
} from "@/pages/dashboard/dashboardMetrics";
import { projectStatusLabel } from "@/lib/statusLabels";

/** 财务账单 Tab 图标指标（format：分 → 当前展示货币） */
export function buildFinanceInsights(stats: AdminStats | null, format: MoneyFormatter): DashboardInsightItem[] {
  if (!stats) return [];

  const monthCharge = stats.usage_charge_month_fen ?? 0;
  const monthCost = stats.usage_cost_month_fen ?? 0;
  const profitFen = calcProfitFen(monthCharge, monthCost);

  const items: DashboardInsightItem[] = [
    {
      key: "paid-total",
      label: "Tổng nạp tiền",
      value: format(stats.order_paid_total_fen),
      hint: `Hôm nay ${format(stats.order_paid_today_fen)}`,
      icon: Banknote,
      tone: "blue",
    },
    {
      key: "charge-month",
      label: "Tiền đã trừ tháng này",
      value: format(monthCharge),
      hint: `Hôm nay ${format(stats.usage_charge_today_fen ?? 0)}`,
      icon: Zap,
      tone: "purple",
    },
    {
      key: "cost-month",
      label: "Chi phí tháng này",
      value: format(monthCost),
      hint: `Hôm nay ${format(stats.usage_cost_today_fen ?? 0)}`,
      icon: Wallet,
      tone: "sand",
    },
    {
      key: "profit-month",
      label: "Lợi nhuận gộp tháng này",
      value: format(profitFen),
      hint: monthCharge > 0 ? `Biên lợi nhuận ${((profitFen / monthCharge) * 100).toFixed(1)}%` : undefined,
      icon: Percent,
      tone: profitFen >= 0 ? "mint" : "rose",
    },
  ];

  items.push({
    key: "paid-today",
    label: "Đã cộng vào số dư hôm nay",
    value: format(stats.order_paid_today_fen),
    hint: "Đơn nạp tiền",
    icon: CircleDollarSign,
    tone: "teal",
  });

  return items;
}

const STATUS_META: Record<string, { icon: LucideIcon; tone: DashboardInsightItem["tone"] }> = {
  DONE: { icon: CheckCircle2, tone: "mint" },
  DRAFT: { icon: Layers, tone: "slate" },
  FAILED: { icon: TrendingDown, tone: "rose" },
  SCRIPTING: { icon: Clapperboard, tone: "blue" },
  IMAGING: { icon: Film, tone: "purple" },
  VIDEOING: { icon: Activity, tone: "teal" },
};

/** 项目运维 Tab 图标指标 */
export function buildProjectInsights(stats: AdminStats | null, periodDaily: ReturnType<typeof sumDailyUsage>): DashboardInsightItem[] {
  if (!stats) return [];

  const kepuTotal = sumProjectStatuses(stats.project_status_counts);
  const items: DashboardInsightItem[] = [
    {
      key: "kepu-total",
      label: "Dự án video ngắn",
      value: kepuTotal,
      hint: `${stats.drama_project_count ?? 0} dự án phim ngắn`,
      icon: Clapperboard,
      tone: "blue",
    },
    {
      key: "drama-total",
      label: "Dự án phim ngắn",
      value: stats.drama_project_count ?? 0,
      hint: "Toàn bộ dự án",
      icon: Film,
      tone: "teal",
    },
    {
      key: "calls-today",
      label: "Lượt gọi hôm nay",
      value: (stats.usage_calls_today ?? 0).toLocaleString("vi-VN"),
      hint: `Tháng này ${stats.usage_calls_month ?? 0} lượt`,
      icon: Activity,
      tone: "mint",
    },
    {
      key: "calls-total",
      label: "Tổng lượt gọi",
      value: (stats.usage_calls_total ?? 0).toLocaleString("vi-VN"),
      hint: `${periodDaily.calls.toLocaleString("vi-VN")} lượt trong kỳ`,
      icon: Layers,
      tone: "slate",
    },
  ];

  const statusEntries = Object.entries(stats.project_status_counts ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);

  for (const [status, count] of statusEntries) {
    const meta = STATUS_META[status] ?? { icon: Layers, tone: "sand" as const };
    items.push({
      key: `status-${status}`,
      label: projectStatusLabel(status),
      value: count,
      hint: kepuTotal > 0 ? `Chiếm ${((count / kepuTotal) * 100).toFixed(1)}% dự án video ngắn` : undefined,
      icon: meta.icon,
      tone: meta.tone,
    });
  }

  return items;
}
