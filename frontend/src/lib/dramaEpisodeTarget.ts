/**
 * 单集目标成片时长（与后端 services/drama/episode_target.py 对齐）：分集 params → 项目 params → 默认 90s；0 = 自动。
 * 公式改动时两边一起改，并重新生成 backend/tests/fixtures/episode_target_table.json（两边测试共用该表防漂移）。
 */

export const EPISODE_TARGET_OPTIONS = [0, 30, 60, 90, 120, 180] as const
export type EpisodeTargetSec = (typeof EPISODE_TARGET_OPTIONS)[number]
export const EPISODE_TARGET_DEFAULT: EpisodeTargetSec = 90
/** 单镜硬上限（后端 FRAGMENT_TOTAL_MAX） */
export const FRAGMENT_MAX_SEC = 15
/** 单镜推荐下限（分镜提示词「优先 6–15 秒」），用于估算条数上沿 */
const FRAGMENT_PREFERRED_MIN_SEC = 6
/** 自动模式条数安全上限（后端 EPISODE_FRAGMENT_MAX_AUTO） */
const EPISODE_FRAGMENT_MAX_AUTO = 30
/** 平均单镜秒数：由目标时长推算条数上限（后端 _AVG_FRAGMENT_SEC） */
const AVG_FRAGMENT_SEC = 9
/** 默认正文最少字数（后端 MIN_EPISODE_CONTENT_CHARS） */
export const DEFAULT_MIN_BODY_CHARS = 450

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

/** 目标时长 → 最多分镜条数（90s → 10，后端 episode_fragment_budget） */
export function episodeMaxFragments(target: number): number {
  if (!target) return EPISODE_FRAGMENT_MAX_AUTO
  if (target === EPISODE_TARGET_DEFAULT) return 10
  return Math.max(3, Math.min(EPISODE_FRAGMENT_MAX_AUTO, Math.ceil(target / AVG_FRAGMENT_SEC)))
}

/**
 * 预计分镜条数区间 [最少, 最多]（每条一次视频生成），无法估算返回 null。
 * 按单镜 6–15 秒推算，上沿不超过条数上限；有目标时长且剧本更短时按剧本估时（AI 不会凭空加戏）。
 * scriptEstimateSec=0 时与后端 fragment_count_range 一致。
 */
export function estimateFragmentRange(target: number, scriptEstimateSec: number): [number, number] | null {
  const script = Math.max(0, scriptEstimateSec)
  const sec = target ? (script > 0 ? Math.min(target, script) : target) : script
  if (sec <= 0) return null
  const low = Math.max(1, Math.ceil(sec / FRAGMENT_MAX_SEC))
  const high = Math.min(episodeMaxFragments(target), Math.ceil(sec / FRAGMENT_PREFERRED_MIN_SEC))
  return [low, Math.max(low, high)]
}

/** 区间展示文本：6–10 / 4 */
export function formatFragmentRange(range: [number, number]): string {
  return range[0] === range[1] ? String(range[0]) : `${range[0]}–${range[1]}`
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
