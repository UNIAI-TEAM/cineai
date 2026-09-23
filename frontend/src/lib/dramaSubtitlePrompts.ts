/** 分镜正文的模型字幕提示词（cue）：按内容语言补回 / 去掉（纯函数，无 i18n 依赖，供 node 测试） */

import { guessTextLang, type ContentLang } from './contentLang.ts'

/** 本集字幕方式：模型自出（正文带字幕 cue）/ 后期拼接（去掉 cue）；dramaSubtitleBoard 从这里 re-export */
export type DramaSubtitleMode = 'model' | 'post'

const DRAMA_SUBTITLE_CUE = '【字幕：底部居中·简体中文·逐句轮换·与口播同步】'
/* 字幕 cue 按台词语言选择（与后端 seedance_segments.DRAMA_SUBTITLE_CUES_BY_LANG 一致）：
   框架是给视频模型的协议标记，保持中文；只把语言词换成越南语 / 英语 */
const DRAMA_SUBTITLE_CUES_BY_LANG: Record<'zh' | 'vi' | 'en', string> = {
  zh: DRAMA_SUBTITLE_CUE,
  vi: '【字幕：底部居中·越南语·逐句轮换·与口播同步】',
  en: '【字幕：底部居中·英语·逐句轮换·与口播同步】',
}

// 去掉【…】协议标记、@引用后按台词文字判断字幕语言；已有非中文 cue 时沿用。
export function detectSubtitleLang(content: string): 'zh' | 'vi' | 'en' {
  const source = String(content || '')
  if (source.includes(DRAMA_SUBTITLE_CUES_BY_LANG.vi)) return 'vi'
  if (source.includes(DRAMA_SUBTITLE_CUES_BY_LANG.en)) return 'en'
  const spoken = source.replace(/【[^】]*】/g, ' ').replace(/@\w+:\S+/g, ' ').replace(/[△Δ]/g, ' ')
  return guessTextLang(spoken) ?? 'zh'
}
const LEGACY_SUBTITLE_CUES = [
  '【字幕：底部居中·简体中文·仅标记段落同步】',
  '【字幕：底部居中·简体中文】',
  '【字幕：全程简体中文字幕，旁白逐句同步烧录】',
]

const STRIP_PREFIX_MAP: Array<[string, string]> = [
  ['【对白·慢速清晰·同步字幕】', '【对白·慢速清晰】'],
  ['【旁白·慢速清晰·同步字幕】', '【旁白·慢速清晰】'],
  ['【旁白·自然语速·同步字幕】', '【旁白·自然语速】'],
  ['【内心独白·同步字幕】', '【内心独白】'],
]

// 判断是否为字幕 cue 行（含历史文案）。
function isSubtitleCueLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed.startsWith('【字幕')) return false
  return (
    trimmed === DRAMA_SUBTITLE_CUE ||
    LEGACY_SUBTITLE_CUES.includes(trimmed) ||
    /同步|烧录|底部居中/.test(trimmed)
  )
}

// 从单条分镜正文去掉模型字幕提示词，保留对白/旁白本身。
export function stripSubtitlePromptsFromContent(content: string): string {
  const lines = String(content || '')
    .replace(/\r\n/g, '\n')
    .split('\n')
  const next: string[] = []
  for (const raw of lines) {
    const trimmed = raw.trim()
    if (!trimmed) {
      next.push(raw)
      continue
    }
    if (isSubtitleCueLine(trimmed)) continue
    let line = trimmed
    for (const [src, dest] of STRIP_PREFIX_MAP) {
      if (line.startsWith(src)) {
        line = line.replace(src, dest)
        break
      }
    }
    next.push(line)
  }
  return next.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd()
}

// 为单条分镜正文补回模型字幕提示词（已有则不重复）；lang 缺省时按台词文字判断字幕语言。
export function applySubtitlePromptsToContent(content: string, lang?: ContentLang): string {
  const source = String(content || '').replace(/\r\n/g, '\n')
  if (!source.trim()) return source
  const cue = DRAMA_SUBTITLE_CUES_BY_LANG[lang ?? detectSubtitleLang(source)]
  const lines = source.split('\n')
  const next: string[] = []
  let hasCue = false
  for (const raw of lines) {
    const trimmed = raw.trim()
    if (!trimmed) {
      next.push(raw)
      continue
    }
    if (isSubtitleCueLine(trimmed)) {
      if (!hasCue) {
        next.push(cue)
        hasCue = true
      }
      continue
    }
    let line = trimmed
    for (const [withSub, withoutSub] of STRIP_PREFIX_MAP) {
      if (line.startsWith(withoutSub) && !line.startsWith(withSub)) {
        line = line.replace(withoutSub, withSub)
        break
      }
    }
    next.push(line)
  }
  if (!hasCue) {
    const insertAt = next.findIndex((line) => line.trim().startsWith('【BGM'))
    if (insertAt >= 0) next.splice(insertAt, 0, cue)
    else next.unshift(cue)
  }
  return next.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd()
}

// 按字幕方式批量改写分镜正文。
// lang：项目内容语言（project.content_lang）；缺省时才按每条台词文字判断 cue 语言。
export function applySubtitleModeToFragments<T extends { content?: string | null }>(
  fragments: T[],
  mode: DramaSubtitleMode,
  lang?: ContentLang | null,
): T[] {
  const transform = (content: string) =>
    mode === 'model'
      ? applySubtitlePromptsToContent(content, lang ?? undefined)
      : stripSubtitlePromptsFromContent(content)
  return fragments.map((fragment) => {
    const prev = String(fragment.content || '')
    const next = transform(prev)
    if (next === prev) return fragment
    return { ...fragment, content: next }
  })
}
