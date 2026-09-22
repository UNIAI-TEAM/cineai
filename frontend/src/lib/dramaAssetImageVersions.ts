/** 资产形象历史版本读写 */
import { resolveDramaMediaUrl, type DramaAsset } from '../api/drama'
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'

export type AssetImageVersion = {
  id: string
  url: string
  cover?: string
  prompt?: string | null
  createdAt?: string
  source?: string
}

// 从 params.image_versions 读取可展示的历史形象
export function readAssetImageVersions(asset: DramaAsset | null | undefined): AssetImageVersion[] {
  const raw = (asset?.params as Record<string, unknown> | null | undefined)?.image_versions
  if (!Array.isArray(raw)) return []
  const out: AssetImageVersion[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const id = String(row.id || '').trim()
    const url = String(row.url || row.cover || '').trim()
    if (!id || !url) continue
    out.push({
      id,
      url,
      cover: typeof row.cover === 'string' ? row.cover : undefined,
      prompt: typeof row.prompt === 'string' ? row.prompt : null,
      createdAt: typeof row.createdAt === 'string' ? row.createdAt : undefined,
      source: typeof row.source === 'string' ? row.source : undefined,
    })
  }
  return out
}

export function resolveAssetImageVersionUrl(version: AssetImageVersion): string {
  return resolveDramaMediaUrl(version.cover || version.url) || version.url
}

// 历史版本来源文案（按当前界面语言）
export function formatAssetImageVersionLabel(version: AssetImageVersion): string {
  const labels = messages[getActiveLocale()].dramaAssets.imageVersion
  const src = (version.source || '').toLowerCase()
  if (src === 'upload') return labels.upload
  if (src === 'replaced') return labels.replaced
  if (src === 'generate') return labels.generate
  if (src === 'restored') return labels.restored
  return labels.history
}
