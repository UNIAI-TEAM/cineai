import {
  Clapperboard,
  Film,
  Image,
  MessageSquareText,
  Mic,
  Palette,
  Video,
  Webhook,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { AdminUsageBucket } from "@/api/client";
import type { DashboardMetric } from "@/pages/dashboard/DashboardFilters";
import type { DashboardInsightItem, DashboardInsightTone } from "@/pages/dashboard/DashboardInsightGrid";
import { formatDashboardMetric, readBucketMetric, type MoneyFormatter } from "@/pages/dashboard/dashboardMetrics";

const CAPABILITY_META: Record<string, { label: string; icon: LucideIcon; tone: DashboardInsightTone }> = {
  llm: { label: "Văn bản (LLM)", icon: MessageSquareText, tone: "purple" },
  image: { label: "Tạo ảnh", icon: Image, tone: "blue" },
  video: { label: "Video", icon: Video, tone: "teal" },
  tts: { label: "Giọng đọc", icon: Mic, tone: "sand" },
  unknown: { label: "Khác", icon: Wrench, tone: "slate" },
};

const DOMAIN_META: Record<string, { label: string; icon: LucideIcon; tone: DashboardInsightTone }> = {
  drama: { label: "Phim ngắn AI", icon: Film, tone: "teal" },
  kepu: { label: "Video ngắn AI", icon: Clapperboard, tone: "blue" },
  api: { label: "API mở", icon: Webhook, tone: "purple" },
  tools: { label: "Công cụ", icon: Wrench, tone: "sand" },
  studio: { label: "Studio", icon: Palette, tone: "mint" },
  unknown: { label: "Khác", icon: Wrench, tone: "slate" },
};

function buildInsightItems(
  rows: AdminUsageBucket[],
  metric: DashboardMetric,
  metaMap: Record<string, { label: string; icon: LucideIcon; tone: DashboardInsightTone }>,
  format: MoneyFormatter,
  labelForKey?: (key: string) => string,
): DashboardInsightItem[] {
  const prepared = [...rows]
    .map((row) => ({
      row,
      value: readBucketMetric(row, metric),
    }))
    .filter((item) => item.value > 0);
  const total = prepared.reduce((sum, item) => sum + item.value, 0);

  return prepared
    .sort((a, b) => b.value - a.value)
    .map(({ row, value }) => {
      const meta = metaMap[row.key] ?? metaMap.unknown;
      const sharePct = total > 0 ? ((value / total) * 100).toFixed(1) : null;
      const shareHint = sharePct ? `Chiếm ${sharePct}%` : undefined;
      return {
        key: row.key,
        label: labelForKey?.(row.key) ?? meta.label,
        value: formatDashboardMetric(value, metric, format),
        hint: [shareHint, `${row.calls.toLocaleString("vi-VN")} lượt gọi`].filter(Boolean).join(" · "),
        icon: meta.icon,
        tone: meta.tone,
      };
    });
}

/** 能力分布洞察卡片 */
export function buildCapabilityInsights(
  rows: AdminUsageBucket[],
  metric: DashboardMetric,
  format: MoneyFormatter,
): DashboardInsightItem[] {
  return buildInsightItems(rows, metric, CAPABILITY_META, format);
}

/** 领域分布洞察卡片 */
export function buildDomainInsights(
  rows: AdminUsageBucket[],
  metric: DashboardMetric,
  format: MoneyFormatter,
  labelForKey: (key: string) => string,
): DashboardInsightItem[] {
  return buildInsightItems(rows, metric, DOMAIN_META, format, labelForKey);
}
