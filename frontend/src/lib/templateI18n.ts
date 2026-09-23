/** 模板 / 音色等后端目录数据的展示名按界面语言取值：优先当前语言译文，其次其他已开放语言（vi↔en），最后回落中文主值 */
import { ENABLED_LOCALES, getActiveLocale, type Locale } from '../i18n/detect'

type TemplateLike = {
  name: string
  description?: string
  i18n?: Record<string, { name?: string; description?: string }> | null
}

// 译文查找顺序：当前语言 → 其他已开放的非中文语言（中文主值由调用方兜底）
function fallbackLocales(locale: Locale): Locale[] {
  if (locale === 'zh') return []
  return [locale, ...ENABLED_LOCALES.filter((l) => l !== locale && l !== 'zh')]
}

// 按顺序取第一个非空译文
function firstLocalized(pick: (l: Locale) => string | undefined, locale: Locale): string {
  for (const l of fallbackLocales(locale)) {
    const value = pick(l)?.trim()
    if (value) return value
  }
  return ''
}

// 按语言取模板名称；未提供 locale 时用当前生效语言
export function templateName(tpl: TemplateLike, locale: Locale = getActiveLocale()): string {
  return firstLocalized((l) => tpl.i18n?.[l]?.name, locale) || tpl.name
}

// 按语言取模板描述；未提供 locale 时用当前生效语言
export function templateDescription(tpl: TemplateLike, locale: Locale = getActiveLocale()): string {
  return firstLocalized((l) => tpl.i18n?.[l]?.description, locale) || tpl.description || ''
}

type LabeledLike = { label: string; label_i18n?: Record<string, string> | null }

// 按语言取带 label_i18n 的目录项（如音色）展示名；未提供 locale 时用当前生效语言
export function localizedLabel(item: LabeledLike, locale: Locale = getActiveLocale()): string {
  return firstLocalized((l) => item.label_i18n?.[l], locale) || item.label
}
