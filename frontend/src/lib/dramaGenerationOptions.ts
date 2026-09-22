/** 漫剧生图：模型 / 比例 / 清晰度选项（模型列表来自后台 TokenFree 目录） */
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'


// 当前界面语言的画布选项文案
function optionText(key: 'auto' | 'imageModel'): string {
  return messages[getActiveLocale()].dramaCanvas.options[key]
}

export type ImageGenerationModelId = string

export type GenerationAspectRatioId =
  | 'auto'
  | '16:9'
  | '21:9'
  | '9:16'
  | '4:3'
  | '3:4'
  | '1:1'

export type GenerationResolution = '3K' | '4K'

export type ImageGenerationOptions = {
  image_style_id?: string
  model_id: ImageGenerationModelId
  aspect_ratio: GenerationAspectRatioId
  resolution: GenerationResolution
}

/** 图片清晰度列表 */
export const GENERATION_RESOLUTION_OPTIONS: GenerationResolution[] = ['3K', '4K']

/** 比例列表 */
export const GENERATION_ASPECT_RATIO_OPTIONS: Array<{
  id: GenerationAspectRatioId
  label: string
}> = [
  {
    id: 'auto',
    // 展示名随界面语言变化；id 才是提交给后端的值
    get label() {
      return optionText('auto')
    },
  },
  { id: '16:9', label: '16:9' },
  { id: '21:9', label: '21:9' },
  { id: '9:16', label: '9:16' },
  { id: '4:3', label: '4:3' },
  { id: '3:4', label: '3:4' },
  { id: '1:1', label: '1:1' },
]

/** 生图模型由 /api/media-models 提供；此处仅占位默认 id */
export const IMAGE_GENERATION_MODELS: Array<{
  id: ImageGenerationModelId
  label: string
  description: string
}> = []

/** 默认生图选项（角色偏竖构图） */
export const DEFAULT_IMAGE_GENERATION_OPTIONS: ImageGenerationOptions = {
  model_id: '',
  aspect_ratio: '3:4',
  resolution: '3K',
}

/** 场景默认横构图 */
export function defaultOptionsForAssetKind(kind: string | undefined | null): ImageGenerationOptions {
  const k = String(kind || '').toLowerCase()
  if (k === 'scene') {
    return { model_id: DEFAULT_IMAGE_GENERATION_OPTIONS.model_id, aspect_ratio: '16:9', resolution: '3K' }
  }
  return { ...DEFAULT_IMAGE_GENERATION_OPTIONS }
}

/** 格式化比例·清晰度触发文案 */
export function formatOutputSettingsLabel(
  aspectRatio: GenerationAspectRatioId,
  resolution: GenerationResolution,
): string {
  if (aspectRatio === 'auto') return `${optionText('auto')} · ${resolution}`
  return `${aspectRatio} · ${resolution}`
}

/** 解析模型展示名（无目录时回退 id） */
export function getImageModelLabel(modelId: string | undefined | null): string {
  const id = (modelId || '').trim()
  return id || optionText('imageModel')
}

/** 任意非空字符串均可作为生图模型 id */
export function isImageGenerationModelId(id: string): id is ImageGenerationModelId {
  return Boolean((id || '').trim())
}
