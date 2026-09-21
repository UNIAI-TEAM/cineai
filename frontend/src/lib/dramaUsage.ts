import type { DramaProjectUsageStats } from '../api/drama'
import { formatFenActive } from '../currency'
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { interpolate } from '../i18n/lookup'

/** 空用量占位，避免列表未返回 usage 时崩溃 */
export const EMPTY_DRAMA_USAGE: DramaProjectUsageStats = {
  charge_fen: 0,
  charge_yuan: 0,
  cost_fen: 0,
  cost_yuan: 0,
  tokens: 0,
  calls: 0,
  image_gens: 0,
  video_gens: 0,
}

/** 分 → 当前展示货币字符串 */
export type FenFormatter = (fen: number) => string

/** 格式化漫剧费用展示（按「分」换算到当前展示货币；可注入自定义格式化器） */
export function formatDramaCharge(fen: number | undefined | null, formatFen: FenFormatter = formatFenActive): string {
  return formatFen(Number(fen) || 0)
}

/** 列表/工作台短文案：费用 · 生图 · 生视频 · 调用 */
export function formatDramaUsageBrief(
  usage?: DramaProjectUsageStats | null,
  formatFen: FenFormatter = formatFenActive,
): string {
  const u = usage || EMPTY_DRAMA_USAGE
  const l = messages[getActiveLocale()].dramaList
  const parts = [
    formatDramaCharge(u.charge_fen, formatFen),
    interpolate(l.usageImages, { count: u.image_gens }),
    interpolate(l.usageVideos, { count: u.video_gens }),
  ]
  if (u.calls > 0) parts.push(interpolate(l.usageCalls, { count: u.calls }))
  return parts.join(' · ')
}
