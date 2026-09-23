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

const CJK_RE = /[぀-ヿ㐀-鿿]/
/* 越南语特有字母（与后端 content_lang._VI_CHARS_RE 一致）：不含 é/à/ô 等法语/英语外来词也用的字母 */
const VI_CHARS_RE =
  /[ăđơưằẳẵắặầẩẫấậềểễếệồổỗốộờởỡớợừửữứựạảẹẻẽịỉĩọỏụủũỳỷỹỵ]/i
/* 与其他拉丁语言共用的越南语声调字母：需多数词都带才算越南语 */
const VI_SHARED_CHARS_RE = /[àáèéìíòóùúýỳâêôãõ]/i
/* 其中英语外来词少见的（重音符 / 扬抑符）：一个词带就够；é 等锐音符（café、Pokémon）需 ≥2 个词 */
const VI_SHARED_STRONG_RE = /[àèìòùỳâêô]/i

/**
 * 按文本猜语言（与后端 guess_text_lang 一致）：含中日文字 → zh；像越南语 → vi；有拉丁字母 → en；否则 null。
 * 像越南语：含越南语特有字母；或带共用声调字母的词占一半以上，且 ≥2 个或含重音符 / 扬抑符（「Tôi là ai」「Xin chào」）。
 * 「Pokémon evolution」「café」→ en；不带声调的越南语无法区分 → en。
 */
export function guessTextLang(text: string): ContentLang | null {
  const raw = String(text || '').trim()
  if (!raw) return null
  if (CJK_RE.test(raw)) return 'zh'
  if (VI_CHARS_RE.test(raw)) return 'vi'
  const words = raw.match(/\p{L}+/gu) || []
  const accented = words.filter((w) => VI_SHARED_CHARS_RE.test(w))
  if (
    accented.length &&
    accented.length * 2 >= words.length &&
    (accented.length >= 2 || accented.some((w) => VI_SHARED_STRONG_RE.test(w)))
  )
    return 'vi'
  if (/[A-Za-z]/.test(raw)) return 'en'
  return null
}

/**
 * 科普创建页的主题 / 标题长度上限（与后端 kepu_text.parse_expand_content 一致）：
 * zh 主题 100 字、标题 24 字；vi / en 同样信息量字符数约 3–4 倍 → 主题 400、标题 80。
 */
export function kepuTextLimits(lang: ContentLang): { theme: number; title: number } {
  return lang === 'zh' ? { theme: 100, title: 24 } : { theme: 400, title: 80 }
}

/**
 * 截到 limit 字符以内：中日文按字截；拉丁文字按词边界截（不切半个词，与后端 cut_words 一致），
 * 整段没有空格时才硬截。未超长原样返回。
 */
export function cutToLimit(text: string, limit: number): string {
  const raw = String(text || '')
  if (raw.length <= limit) return raw
  if (CJK_RE.test(raw)) return raw.slice(0, limit)
  let head = raw.slice(0, limit)
  if (!/\s/.test(raw.charAt(limit))) {
    const lastSpace = head.search(/\s\S*$/)
    if (lastSpace > 0) head = head.slice(0, lastSpace)
  }
  return head.replace(/[\s,.;:!?\-–—]+$/, '')
}
