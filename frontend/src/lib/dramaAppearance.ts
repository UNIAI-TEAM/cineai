/** Ngoại hình nhân vật theo trường (params.appearance) — cùng 8 khóa / thứ tự với backend appearance_prompt.py */

export const APPEARANCE_KEYS = [
  'gender',
  'age',
  'face',
  'hair',
  'build',
  'outfit',
  'signature',
  'style_note',
] as const

export type AppearanceKey = (typeof APPEARANCE_KEYS)[number]
export type Appearance = Record<AppearanceKey, string>

// Ngoại hình rỗng (đủ 8 khóa)
export function emptyAppearance(): Appearance {
  return Object.fromEntries(APPEARANCE_KEYS.map((k) => [k, ''])) as Appearance
}

// Đọc params.appearance: đủ 8 khóa, ép chuỗi + trim; kiểu sai → rỗng
export function readAppearance(asset: { params?: unknown }): Appearance {
  const params = (asset.params && typeof asset.params === 'object' ? asset.params : {}) as Record<string, unknown>
  const raw = params.appearance && typeof params.appearance === 'object' ? (params.appearance as Record<string, unknown>) : {}
  const out = emptyAppearance()
  for (const k of APPEARANCE_KEYS) {
    const v = raw[k]
    out[k] = v === null || v === undefined ? '' : String(v).trim()
  }
  return out
}

// Mọi trường đều rỗng
export function appearanceIsEmpty(a: Appearance): boolean {
  return APPEARANCE_KEYS.every((k) => !a[k].trim())
}

// So sánh hai bộ ngoại hình (bỏ khoảng trắng đầu/cuối)
export function appearanceEqual(a: Appearance, b: Appearance): boolean {
  return APPEARANCE_KEYS.every((k) => a[k].trim() === b[k].trim())
}

// Prompt đang ở chế độ chỉnh tay (backend không tự ghép đè)
export function readPromptManual(asset: { params?: unknown }): boolean {
  const params = (asset.params && typeof asset.params === 'object' ? asset.params : {}) as Record<string, unknown>
  return params.promptManual === true
}

/**
 * Dựng params cho PATCH khi lưu:
 * - sửa ô prompt → chuyển chỉnh tay, gửi nguyên văn prompt;
 * - chỉ sửa trường khi đang tự ghép → gửi appearance + promptManual:false (backend ghép lại);
 * - sửa trường khi đang chỉnh tay → chỉ gửi appearance (prompt tay giữ nguyên);
 * - không đổi gì → null.
 */
export function buildAppearanceSave(opts: {
  appearance: Appearance
  appearanceDirty: boolean
  promptText: string
  promptDirty: boolean
  wasManual: boolean
}): Record<string, unknown> | null {
  const { appearance, appearanceDirty, promptDirty, wasManual } = opts
  const prompt = opts.promptText.trim()
  if (!appearanceDirty && !promptDirty) return null
  const out: Record<string, unknown> = {}
  if (appearanceDirty) out.appearance = appearance
  if (promptDirty) {
    out.promptManual = true
    out.visualPrompt = prompt
    out.visualImage = prompt
  } else if (!wasManual) {
    out.promptManual = false
  }
  return out
}
