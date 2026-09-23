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

/** 中日文字（平假名 / 片假名 / CJK 统一表意文字）：全前端共用，判断「是否中文内容」 */
export const CJK_RE = /[\u3040-\u30ff\u3400-\u9fff]/
/* 越南语特有字母（与后端 content_lang._VI_CHARS_RE 一致）：不含 é/à/ô 等法语/英语外来词也用的字母 */
const VI_CHARS_RE =
  /[ăđơưằẳẵắặầẩẫấậềểễếệồổỗốộờởỡớợừửữứựạảẹẻẽịỉĩọỏụủũỳỷỹỵ]/i
/* 与其他拉丁语言共用的越南语声调字母：需配合常用词或多数词都带才算越南语 */
const VI_SHARED_CHARS_RE = /[àáèéìíòóùúýỳâêôãõ]/i
/* 其中英语外来词少见的（重音符 / 扬抑符）：一个词带就够；é 等锐音符（café、Pokémon）需 ≥2 个词 */
const VI_SHARED_STRONG_RE = /[àèìòùỳâêô]/i
/* 越南语常用词（与后端 _VI_COMMON_WORDS 一致）：文本带共用声调字母时出现其一即判 vi（「Bé」「Cá voi」）；
   不收与英语 / 西语撞词的 ai、ba、con、em、hay、la、va、co、may 等 */
const VI_COMMON_WORDS = new Set(
  `và là có không khong tôi toi cá voi bé má cho này các cac bà ông nhà thì mà gì xin chào chao
   trên trong vì nên cô chú mèo chó gà bò lá cây núi sông biển
   mot nguoi nhung cua duoc`.split(/\s+/),
)

/* 常用词捷径的最低信号词占比（与后端 _VI_SIGNAL_RATIO_TENTHS = 3 一致） */
const VI_SIGNAL_RATIO = 0.3

/**
 * 按文本猜语言（与后端 guess_text_lang 同一规则，共用测试向量 backend/tests/fixtures/content_lang_vectors.json）：
 * 含中日文字 → zh；像越南语 → vi；有拉丁字母 → en；否则 null。
 * 像越南语：含越南语特有字母；或含共用声调字母且（出现越南语常用词且信号词占 ≥30%，或带声调的词占一半以上且 ≥2 个 / 含重音符、扬抑符）。
 * 「Pokémon evolution」「café」→ en；「Crème brûlée」→ vi（已知取舍）；不带声调的越南语无法区分 → en。
 */
export function guessTextLang(text: string): ContentLang | null {
  const raw = String(text || '').trim().normalize('NFC')
  if (!raw) return null
  if (CJK_RE.test(raw)) return 'zh'
  if (VI_CHARS_RE.test(raw)) return 'vi'
  const words = raw.match(/\p{L}+/gu) || []
  const accented = words.filter((w) => VI_SHARED_CHARS_RE.test(w))
  if (accented.length) {
    // 常用词捷径：越南语信号词（共用声调字母或常用词）占 ≥30% 才生效（「Bà Nà Hills」「cá kho」夹在英文句里 → en）
    const signals = words.filter((w) => VI_SHARED_CHARS_RE.test(w) || VI_COMMON_WORDS.has(w.toLowerCase())).length
    if (signals >= words.length * VI_SIGNAL_RATIO && words.some((w) => VI_COMMON_WORDS.has(w.toLowerCase())))
      return 'vi'
    if (
      accented.length * 2 >= words.length &&
      (accented.length >= 2 || accented.some((w) => VI_SHARED_STRONG_RE.test(w)))
    )
      return 'vi'
  }
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
 * 截到 limit 字符以内（与后端 text_lang.cut_words 一致：「词」= 不含空白的连续片段，只在空白处断开）：
 * - 截点两侧都是非空白、非中日文字 → 退到该片段开头（don't、3.5、state-of-the-art 整体保留）；
 * - 中日文字没有空格分词，截点挨着中日文字时逐字截（片段里夹拉丁时退到最后一个中日文字之后）；
 * - 整段就是一个超长拉丁片段时才硬截。去掉结尾的空白与标点。未超长原样返回（不合并空白）。
 */
export function cutToLimit(text: string, limit: number): string {
  const raw = String(text || '')
  if (raw.length <= limit) return raw
  let head = raw.slice(0, limit)
  const last = head.charAt(head.length - 1)
  const next = raw.charAt(limit)
  const breakable = (ch: string) => /\s/.test(ch) || CJK_RE.test(ch)
  if (!breakable(last) && !breakable(next)) {
    let i = head.length
    while (i > 0 && !breakable(head.charAt(i - 1))) i -= 1
    if (i > 0) head = head.slice(0, i)
  }
  return head.replace(/[\s,.;:!?\-–—，。；：！？、]+$/, '')
}

/**
 * 主题 / 标题是否超过内容语言的上限（切换语言不会改用户内容，由界面提示并阻止创建）。
 * 文案模式正文上限 8000 与语言无关，只检查主题模式的 sourceText。
 */
export function kepuDraftOverflow(
  draft: { sourceText: string; title: string },
  lang: ContentLang,
  mode: 'theme' | 'script',
): { themeOver: boolean; titleOver: boolean; any: boolean } {
  const limits = kepuTextLimits(lang)
  const themeOver = mode === 'theme' && draft.sourceText.length > limits.theme
  const titleOver = draft.title.trim().length > limits.title
  return { themeOver, titleOver, any: themeOver || titleOver }
}

/**
 * 「Cắt cho vừa」：用户确认后按当前语言上限截断主题 / 标题（cutToLimit，拉丁词不切半）。
 * 例：vi 下 350 字主题切到 zh 后点按钮 → 截到 ≤100 字。
 */
export function fitKepuDraft(
  draft: { sourceText: string; title: string },
  lang: ContentLang,
  mode: 'theme' | 'script',
): { sourceText: string; title: string } {
  const limits = kepuTextLimits(lang)
  return {
    sourceText: mode === 'theme' ? cutToLimit(draft.sourceText, limits.theme) : draft.sourceText,
    title: cutToLimit(draft.title, limits.title),
  }
}

/**
 * 输入框 onChange：超过上限时不接受「变长」的修改，但从不截掉已有内容（切换语言后已超限的文字保留，
 * 用户可删减或点「Cắt cho vừa」）。返回应写入的新值。
 */
export function acceptLimitedInput(prev: string, next: string, limit: number): string {
  if (next.length <= limit || next.length <= prev.length) return next
  return prev.length > limit ? prev : next.slice(0, limit)
}
