/** 模板 / 音色等后端目录数据的展示名按界面语言取值：优先译文，缺省回落中文主值 */
import { getActiveLocale, type Locale } from '../i18n/detect'

type TemplateLike = {
  name: string
  description?: string
  i18n?: Record<string, { name?: string; description?: string }> | null
}

// 按语言取模板名称；未提供 locale 时用当前生效语言
export function templateName(tpl: TemplateLike, locale: Locale = getActiveLocale()): string {
  const localized = tpl.i18n?.[locale]?.name?.trim()
  return localized || tpl.name
}

// 按语言取模板描述；未提供 locale 时用当前生效语言
export function templateDescription(tpl: TemplateLike, locale: Locale = getActiveLocale()): string {
  const localized = tpl.i18n?.[locale]?.description?.trim()
  return localized || tpl.description || ''
}

type LabeledLike = { label: string; label_i18n?: Record<string, string> | null }

// 按语言取带 label_i18n 的目录项（如音色）展示名；未提供 locale 时用当前生效语言
export function localizedLabel(item: LabeledLike, locale: Locale = getActiveLocale()): string {
  const localized = item.label_i18n?.[locale]?.trim()
  return localized || item.label
}
