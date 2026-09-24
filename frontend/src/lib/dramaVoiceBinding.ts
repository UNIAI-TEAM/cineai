/**
 * 角色/旁白音色绑定：开关常量 + 读取/写入 asset.params 里的 voiceAudio 绑定的纯函数。
 * VoiceBinding/readVoicePrompt/readAssetVoiceBinding/buildBoundParams 原在 CharacterVoiceBindModal.tsx，
 * 抽到这个叶子模块是为了让 useVoiceCatalog.ts 等 hook/工具能直接 import，不必反向依赖组件文件（避免循环依赖）。
 */
import type { DramaAsset } from '../api/drama'
import { translate } from '../i18n/translate'
import { displayDramaAssetName } from './dramaLibraryAssets'

/** 音色难控：暂不绑定、不提交 Seedance reference_audio，口播由模型自发挥。恢复时改 true。 */
export const DRAMA_VOICE_BINDING_ENABLED = false

/** 选择角色用于 TTS 配音的音色（资产详情框的「绑定音色」按钮 + 绑定音色弹窗）。独立于 DRAMA_VOICE_BINDING_ENABLED：后端不再向 Seedance 提交 reference_audio（SEEDANCE_ATTACH_REFERENCE_AUDIO=False），所绑定的音色只用于 TTS 配音。 */
export const DRAMA_CHARACTER_VOICE_PICK_ENABLED = true

export type VoiceBinding = {
  sourceAssetId: number
  url: string
  label: string
  voicePrompt?: string
}

// 读取 voice 资产的音色描述
export function readVoicePrompt(asset: DramaAsset): string {
  const params = (asset.params || {}) as Record<string, unknown>
  return typeof params.voicePrompt === 'string' ? params.voicePrompt.trim() : ''
}

// 从角色资产 params 读取已绑定音色（label 已转为展示名：旧的中文默认名按界面语言显示）
export function readAssetVoiceBinding(asset: DramaAsset): VoiceBinding | null {
  const params = (asset.params || {}) as Record<string, unknown>
  const raw = params.voiceAudio
  if (raw && typeof raw === 'object') {
    const data = raw as Record<string, unknown>
    const sourceAssetId =
      typeof data.sourceAssetId === 'number'
        ? data.sourceAssetId
        : typeof data.voiceId === 'string'
          ? Number.NaN
          : null
    const url =
      typeof data.url === 'string'
        ? data.url
        : typeof data.previewUrl === 'string'
          ? data.previewUrl
          : ''
    if (typeof sourceAssetId === 'number' && sourceAssetId > 0 && url) {
      return {
        sourceAssetId,
        url,
        label: typeof data.label === 'string' ? displayDramaAssetName(data.label) : translate('dramaAssets.common.voice'),
        voicePrompt: typeof data.voicePrompt === 'string' ? data.voicePrompt : undefined,
      }
    }
  }
  const canvas = params.canvas
  if (canvas && typeof canvas === 'object') {
    const voiceAudio = (canvas as Record<string, unknown>).voiceAudio
    if (voiceAudio && typeof voiceAudio === 'object') {
      const data = voiceAudio as Record<string, unknown>
      const sourceAssetId = typeof data.sourceAssetId === 'number' ? data.sourceAssetId : null
      const url = typeof data.url === 'string' ? data.url : ''
      if (sourceAssetId && url) {
        return { sourceAssetId, url, label: translate('dramaAssets.common.voice') }
      }
    }
  }
  return null
}

// 构建绑定后的 params（同时写 voiceAudio 与 canvas.voiceAudio）
export function buildBoundParams(asset: DramaAsset, voice: DramaAsset): Record<string, unknown> {
  const url = voice.url || ''
  const binding: VoiceBinding = {
    sourceAssetId: voice.id,
    url,
    // 无名称时按当前界面语言写入默认标签（用户数据，展示时 displayDramaAssetName 兼容旧的中文值）
    label: voice.name || translate('dramaAssets.common.voice'),
    voicePrompt: readVoicePrompt(voice) || undefined,
  }
  const prev = (asset.params || {}) as Record<string, unknown>
  const prevCanvas =
    prev.canvas && typeof prev.canvas === 'object'
      ? (prev.canvas as Record<string, unknown>)
      : {}
  return {
    ...prev,
    voiceAudio: binding,
    canvas: {
      ...prevCanvas,
      voiceAudio: { sourceAssetId: voice.id, url },
    },
  }
}
