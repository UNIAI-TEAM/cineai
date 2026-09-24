/** 单集目标成片时长（与后端 services/drama/episode_target.py 对齐）：分集 params → 项目 params → 默认 90s；0 = 自动 */

export const EPISODE_TARGET_OPTIONS = [0, 30, 60, 90, 120, 180] as const
export type EpisodeTargetSec = (typeof EPISODE_TARGET_OPTIONS)[number]
export const EPISODE_TARGET_DEFAULT: EpisodeTargetSec = 90
/** 单镜硬上限（后端 FRAGMENT_TOTAL_MAX） */
export const FRAGMENT_MAX_SEC = 15
/** 自动模式条数安全上限（后端 EPISODE_FRAGMENT_MAX_AUTO） */
const EPISODE_FRAGMENT_MAX_AUTO = 30
/** 默认正文最少字数（与前端既有 MIN_EPISODE_BODY_CHARS 一致） */
const DEFAULT_MIN_BODY_CHARS = 500

// 合法选项返回秒数，否则 null
export function normalizeEpisodeTargetSec(raw: unknown): EpisodeTargetSec | null {
  if (raw == null || typeof raw === 'boolean') return null
  const n = typeof raw === 'number' ? raw : Number(String(raw).trim())
  if (!Number.isInteger(n)) return null
  return (EPISODE_TARGET_OPTIONS as readonly number[]).includes(n) ? (n as EpisodeTargetSec) : null
}

// 按「分集 → 项目 → 默认」解析目标时长
export function resolveEpisodeTargetSec(
  ...sources: Array<Record<string, unknown> | null | undefined>
): EpisodeTargetSec {
  for (const params of sources) {
    const picked = normalizeEpisodeTargetSec(params?.episodeTargetSec)
    if (picked != null) return picked
  }
  return EPISODE_TARGET_DEFAULT
}

/** 目标时长 → 最多分镜条数（90s → 10，与后端一致） */
export function episodeMaxFragments(target: number): number {
  if (!target) return EPISODE_FRAGMENT_MAX_AUTO
  if (target === 90) return 10
  return Math.max(3, Math.min(EPISODE_FRAGMENT_MAX_AUTO, Math.ceil(target / 9)))
}

/** 预计分镜条数（每条一次视频生成）：自动模式按剧本估时，否则按目标时长 */
export function estimateFragmentCount(target: number, scriptEstimateSec: number): number {
  const sec = target || scriptEstimateSec
  if (sec <= 0) return 0
  return Math.min(episodeMaxFragments(target), Math.max(1, Math.ceil(sec / 12)))
}

/** 正文最少字数：短时长按比例放宽（后端 episode_content_length 的最少字数口径） */
export function minEpisodeBodyChars(target: number): number {
  if (!target) return DEFAULT_MIN_BODY_CHARS
  return Math.min(DEFAULT_MIN_BODY_CHARS, Math.max(120, Math.round(target * 5)))
}

/** 剧本估时明显超出目标（超过 1.5 倍）时提示会被 AI 压缩 */
export function isScriptOverTarget(target: number, scriptEstimateSec: number): boolean {
  return target > 0 && scriptEstimateSec > target * 1.5
}
