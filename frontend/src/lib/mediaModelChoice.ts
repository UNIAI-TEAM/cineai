/**
 * Chọn model phía user (thuần, không import runtime). Model rỗng = "Tự động": backend chia luân phiên
 * theo weight trong các model admin đã bật cho chức năng đó.
 * - models null (catalog chưa về / tải lỗi) → giữ nguyên (backend vẫn nhận giá trị cũ không đổi)
 * - model còn trong catalog (so khớp không phân biệt hoa/thường và khoảng trắng, như backend
 *   normalize_model_name) → trả về đúng id trong catalog
 * - model đã bị gỡ, hoặc catalog rỗng → '' (Tự động); không bao giờ tự ghim model mặc định
 */

/** Chuẩn hoá tên model để so khớp: bỏ khoảng trắng, chữ thường — giống backend normalize_model_name */
function normalizeModelId(value: string): string {
  return value.replace(/\s+/g, '').toLowerCase()
}

export function reconcileCatalogModel(
  current: string | null | undefined,
  models: ReadonlyArray<{ id: string }> | null,
): string {
  const cur = (current || '').trim()
  if (models === null) return cur
  if (!cur) return ''
  const normCur = normalizeModelId(cur)
  const match = models.find((m) => normalizeModelId(m.id) === normCur)
  return match ? match.id : ''
}

/** Dòng phụ dưới tên model: mô tả nếu có, không thì tên provider */
export function modelProviderLabel(m: { description?: string; provider?: string }): string {
  return (m.description || '').trim() || (m.provider || '').trim()
}
