import type { AdminDailyUsage, AdminStats, AdminUsageBucket } from "@/api/client";
import type { DashboardMetric } from "@/pages/dashboard/DashboardFilters";

/** 分 → 展示货币字符串（由组件通过 useCurrency().format 传入） */
export type MoneyFormatter = (fen: number) => string;

/** 时间窗内日趋势汇总 */
export function sumDailyUsage(daily: AdminDailyUsage[]) {
  return daily.reduce(
    (acc, row) => ({
      calls: acc.calls + row.calls,
      charge_fen: acc.charge_fen + row.charge_fen,
      cost_fen: acc.cost_fen + (row.cost_fen ?? 0),
    }),
    { calls: 0, charge_fen: 0, cost_fen: 0 },
  );
}

/** 按当前图表指标读取桶数值 */
export function readBucketMetric(row: AdminUsageBucket, metric: DashboardMetric): number {
  if (metric === "cost") return row.cost_fen ?? 0;
  if (metric === "calls") return row.calls;
  return row.charge_fen;
}

/** 格式化指标展示值（金额按传入的格式化器换算为展示货币） */
export function formatDashboardMetric(value: number, metric: DashboardMetric, format: MoneyFormatter): string {
  if (metric === "calls") return value.toLocaleString("vi-VN");
  return format(value);
}

/** 估算毛利（扣费 - 成本） */
export function calcProfitFen(chargeFen: number, costFen: number): number {
  return chargeFen - costFen;
}

/** 科普项目总数（各状态之和） */
export function sumProjectStatuses(counts: Record<string, number> | undefined): number {
  return Object.values(counts ?? {}).reduce((sum, n) => sum + n, 0);
}

/** 漫剧 + 科普项目规模摘要 */
export function projectScaleHint(stats: AdminStats | null): string | undefined {
  if (!stats) return undefined;
  const kepu = sumProjectStatuses(stats.project_status_counts);
  const drama = stats.drama_project_count ?? 0;
  return `Video ngắn ${kepu} · Phim ngắn ${drama}`;
}
