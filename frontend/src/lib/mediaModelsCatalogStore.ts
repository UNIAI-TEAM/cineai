/** Cache danh mục model phía user theo scope; dùng chung cho hook và hàng đợi tạo (đọc đồng bộ khi gửi). */
import { api, type MediaModelScope, type MediaModelsCatalog } from '../api'

const cached = new Map<MediaModelScope, MediaModelsCatalog>()
const inflight = new Map<MediaModelScope, Promise<MediaModelsCatalog>>()

/** Tải catalog một scope; dùng chung request đang chạy; lỗi thì cho phép tải lại lần sau */
export function loadMediaModelsCatalog(scope: MediaModelScope): Promise<MediaModelsCatalog> {
  const hit = cached.get(scope)
  if (hit) return Promise.resolve(hit)
  let pending = inflight.get(scope)
  if (!pending) {
    pending = api.mediaModels(scope).then(
      (cat) => {
        cached.set(scope, cat)
        inflight.delete(scope)
        return cat
      },
      (err: unknown) => {
        inflight.delete(scope)
        throw err
      },
    )
    inflight.set(scope, pending)
  }
  return pending
}

/** Catalog đã tải của scope (null nếu chưa có) — không gọi mạng */
export function peekMediaModelsCatalog(scope: MediaModelScope): MediaModelsCatalog | null {
  return cached.get(scope) ?? null
}
