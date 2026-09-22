/** 漫剧画布 / 分集：视频生成选项（模型列表来自后台 /api/media-models?scope=drama） */
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'


export type VideoGenerationModelId = string

export type VideoAspectRatio = '9:16' | '16:9' | '1:1'
export type VideoResolution = '480p' | '720p' | '1080p'

export type VideoGenerationOptions = {
  image_style_id?: string
  model_id: VideoGenerationModelId
  aspect_ratio: VideoAspectRatio
  resolution: VideoResolution
  duration_sec: number
}

export const VIDEO_ASPECT_RATIO_OPTIONS: VideoAspectRatio[] = ['9:16', '16:9', '1:1']
export const VIDEO_RESOLUTION_OPTIONS: VideoResolution[] = ['480p', '720p', '1080p']
export const VIDEO_DURATION_PRESETS = [5, 8, 10, 15] as const
export const VIDEO_DURATION_MIN = 4
export const VIDEO_DURATION_MAX = 30

export const DEFAULT_VIDEO_GENERATION_OPTIONS: VideoGenerationOptions = {
  model_id: '',
  aspect_ratio: '9:16',
  resolution: '720p',
  duration_sec: 8,
}

/** 夹紧时长到允许区间 */
export function clampVideoDuration(sec: number) {
  const n = Math.round(Number(sec) || DEFAULT_VIDEO_GENERATION_OPTIONS.duration_sec)
  return Math.min(VIDEO_DURATION_MAX, Math.max(VIDEO_DURATION_MIN, n))
}

/** 格式化比例 · 清晰度 */
export function formatVideoOutputLabel(
  aspectRatio: VideoAspectRatio,
  resolution: VideoResolution,
) {
  return `${aspectRatio} · ${resolution}`
}

/** 解析模型展示名（无目录时回退 id） */
export function getVideoModelLabel(modelId: string | undefined | null) {
  const id = (modelId || '').trim()
  return id || messages[getActiveLocale()].dramaCanvas.options.videoModel
}

/** 任意非空字符串均可作为视频模型 id（由后台功能分配决定是否可用） */
export function isVideoGenerationModelId(id: string): id is VideoGenerationModelId {
  return Boolean((id || '').trim())
}

/** 从节点 data 恢复视频选项 */
export function readVideoGenerationOptions(raw: unknown): VideoGenerationOptions {
  const row = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const modelId = String(row.model_id || '').trim()
  const aspect = String(row.aspect_ratio || '')
  const resolution = String(row.resolution || '')
  return {
    image_style_id: typeof row.image_style_id === 'string' ? row.image_style_id : undefined,
    model_id: modelId || DEFAULT_VIDEO_GENERATION_OPTIONS.model_id,
    aspect_ratio: VIDEO_ASPECT_RATIO_OPTIONS.includes(aspect as VideoAspectRatio)
      ? (aspect as VideoAspectRatio)
      : DEFAULT_VIDEO_GENERATION_OPTIONS.aspect_ratio,
    resolution: VIDEO_RESOLUTION_OPTIONS.includes(resolution as VideoResolution)
      ? (resolution as VideoResolution)
      : DEFAULT_VIDEO_GENERATION_OPTIONS.resolution,
    duration_sec: clampVideoDuration(Number(row.duration_sec)),
  }
}
