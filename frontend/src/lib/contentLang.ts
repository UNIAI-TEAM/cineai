/** 项目内容语言（AI 生成剧本 / 台词 / 旁白 / 字幕所用语言）：可选项与默认值，与后端 content_lang.py 对齐 */
import { ENABLED_LOCALES, type Locale } from '../i18n/detect.ts'

export type ContentLang = 'vi' | 'en' | 'zh'

/** 下拉 / 选项条的固定顺序 */
const CONTENT_LANG_ORDER: ContentLang[] = ['vi', 'en', 'zh']

/**
 * 把 'vi-VN' / 'en_US' / 'zh-CN' 等归一为 vi|en|zh；无法识别返回 null。
 */
export function normalizeContentLang(value: unknown): ContentLang | null {
  if (typeof value !== 'string') return null
  const head = value.trim().toLowerCase().replace('_', '-').split('-', 1)[0]
  return head === 'vi' || head === 'en' || head === 'zh' ? head : null
}

/**
 * 新建项目的默认内容语言：跟随界面语言；界面语言不可选时回落 vi。
 * 参数 enabled：可选的界面语言（默认 ENABLED_LOCALES）
 */
export function defaultContentLang(
  uiLocale: Locale,
  enabled: readonly Locale[] = ENABLED_LOCALES,
): ContentLang {
  return contentLangOptions(null, enabled).includes(uiLocale) ? uiLocale : 'vi'
}

/**
 * 可选的内容语言：vi / en 始终可选；zh 只在界面开放中文或项目当前就是中文时出现（保留老项目的原值）。
 * 参数 current：项目当前内容语言（新建时传 null）
 */
export function contentLangOptions(
  current?: string | null,
  enabled: readonly Locale[] = ENABLED_LOCALES,
): ContentLang[] {
  const cur = normalizeContentLang(current)
  return CONTENT_LANG_ORDER.filter(
    (lang) => lang !== 'zh' || enabled.includes('zh') || cur === 'zh',
  )
}
