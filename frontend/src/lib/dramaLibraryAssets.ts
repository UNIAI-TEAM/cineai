import type { DramaAsset } from '../api/drama'
import { getActiveLocale } from '../i18n/detect'
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
  if (!raw || raw === '未命名') return m.dramaAssets.common.untitled
  const key = DEFAULT_ASSET_NAME_KEYS[raw]
  return key ? m.dramaCanvas.defaultLabel[key] : raw
}
