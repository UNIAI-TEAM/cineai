import type { DramaAsset } from '../api/drama'
import { getActiveLocale } from '../i18n/detect'
import { interpolate } from '../i18n/lookup'
import { messages } from '../i18n/messages'

/** 后端落库的中文默认资产名（画布新建节点 / 导入未命名）→ 展示用文案 key */
const DEFAULT_ASSET_NAME_KEYS: Record<string, 'character' | 'scene' | 'video' | 'image' | 'text' | 'audio'> = {
  新角色: 'character',
  新场景: 'scene',
  新视频: 'video',
  新图片: 'image',
  文本: 'text',
  新音频: 'audio',
}

/** 画布专用资产 type，不出现在全局/项目资产库列表 */
export const DRAMA_CANVAS_ONLY_ASSET_TYPES = new Set(['video', 'audio', 'text'])

/** 已停用的库类型（历史素材/none 不再展示） */
export const DRAMA_LIBRARY_DISABLED_TYPES = new Set(['material', 'none'])

// 判断资产是否应出现在资产库（角色/场景/道具/音色等）
export function isDramaLibraryAsset(asset: DramaAsset): boolean {
  const type = (asset.type || '').toLowerCase()
  if (DRAMA_CANVAS_ONLY_ASSET_TYPES.has(type)) return false
  if (DRAMA_LIBRARY_DISABLED_TYPES.has(type)) return false
  const assetType = (asset.asset_type || '').toLowerCase()
  if (assetType === 'video') return false
  return true
}

// 过滤出资产库可见项
export function filterDramaLibraryAssets(assets: DramaAsset[]): DramaAsset[] {
  return assets.filter(isDramaLibraryAsset)
}

/** 资产展示名：空名或仍是中文默认名时按当前语言显示，用户改过的名称原样返回 */
export function displayDramaAssetName(name: string | null | undefined): string {
  const raw = (name || '').trim()
  const m = messages[getActiveLocale()]
  const c = m.dramaAssets.common
  if (!raw || raw === '未命名' || raw === '未命名资产') return c.untitled
  const key = DEFAULT_ASSET_NAME_KEYS[raw]
  if (key) return m.dramaCanvas.defaultLabel[key]
  // 音色类默认名（前端 / 后端生成时写入的中文）
  if (raw === '未命名音色') return c.untitledVoice
  if (raw === '音色') return c.voice
  if (raw === '旁白音色') return c.narratorVoice
  if (raw === '角色音色') return c.characterVoice
  // 画布 / 后端编号默认名：「节点 3」「资产 12」
  const node = raw.match(/^节点 (\d+)$/)
  if (node) return interpolate(c.nodeNo, { n: Number(node[1]) })
  const asset = raw.match(/^资产 (\d+)$/)
  if (asset) return interpolate(c.assetNo, { n: Number(asset[1]) })
  // 「{角色名}音色」：角色名是用户数据，原样保留
  const voiceOf = raw.match(/^(.+)音色$/)
  if (voiceOf) return interpolate(c.voiceOf, { name: voiceOf[1].trim() })
  return raw
}
