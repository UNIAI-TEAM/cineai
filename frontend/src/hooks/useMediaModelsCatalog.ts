/** Hook lấy danh mục model ảnh/video phía user theo scope sản phẩm (kepu / drama / tools). */
import { useEffect, useState } from 'react'
import type { MediaModelOption, MediaModelScope, MediaModelsCatalog } from '../api'
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { loadMediaModelsCatalog, peekMediaModelsCatalog } from '../lib/mediaModelsCatalogStore'

/** Catalog của scope; null khi chưa về hoặc tải lỗi */
export function useMediaModelsCatalog(scope: MediaModelScope) {
  const [catalog, setCatalog] = useState<MediaModelsCatalog | null>(() => peekMediaModelsCatalog(scope))

  useEffect(() => {
    let cancelled = false
    loadMediaModelsCatalog(scope)
      .then((cat) => {
        if (!cancelled) setCatalog(cat)
      })
      .catch(() => {
        if (!cancelled) setCatalog(null)
      })
    return () => {
      cancelled = true
    }
  }, [scope])

  return catalog
}

/** Model video trong catalog hiện tại; catalog chưa về thì rỗng. */
export function catalogVideoModels(catalog: MediaModelsCatalog | null): MediaModelOption[] {
  return catalog?.video_models ?? []
}

/** Model ảnh trong catalog hiện tại; catalog chưa về thì rỗng. */
export function catalogImageModels(catalog: MediaModelsCatalog | null): MediaModelOption[] {
  return catalog?.image_models ?? []
}

/** Hiển thị tên model theo label trong catalog, không tìm thấy thì hiện id; id rỗng thì hiện fallback (bên gọi truyền chữ "Tự động"). */
export function catalogModelLabel(
  modelId: string | undefined | null,
  models: Array<{ id: string; label: string }>,
  fallback = messages[getActiveLocale()].dramaEpisode.modelFallback,
): string {
  const id = (modelId || '').trim()
  if (!id) return fallback
  return models.find((m) => m.id === id)?.label || id
}
