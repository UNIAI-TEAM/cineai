/**
 * 剧本结构标签的展示翻译（只改显示，不改数据）。
 * 剧本正文里的「出场人物：」「日 内 …」「【空镜：…】」是后端 build_fragments / seed 解析用的固定中文标签，
 * vi / en 界面预览时换成当前语言的说法；编辑框里仍是原文。
 */

/** 标签文案（取自 dramaProject.preview） */
export type ScriptLabelCopy = {
  castLabel: string
  establishing: string
  listSep: string
  sceneTime: Record<'day' | 'night' | 'dawn' | 'dusk' | 'evening' | 'beforeDawn' | 'earlyMorning' | 'morning' | 'noon' | 'late', string>
  scenePlace: Record<'interior' | 'exterior' | 'both', string>
}

// 场景时间标签 → 文案 key（长的放前面，避免「清晨」被「晨」截断）
const TIME_KEYS: Array<[string, keyof ScriptLabelCopy['sceneTime']]> = [
  ['黄昏', 'dusk'],
  ['傍晚', 'evening'],
  ['凌晨', 'beforeDawn'],
  ['清晨', 'earlyMorning'],
  ['日', 'day'],
  ['夜', 'night'],
  ['晨', 'dawn'],
  ['早', 'morning'],
  ['午', 'noon'],
  ['晚', 'late'],
]

const PLACE_KEYS: Record<string, keyof ScriptLabelCopy['scenePlace']> = {
  内外: 'both',
  内: 'interior',
  外: 'exterior',
}

const CAST_RE = /^出场人物\s*[：:]\s*(.*)$/
const TIME_PLACE_RE = /^(黄昏|傍晚|凌晨|清晨|日|夜|晨|早|午|晚)\s*(内外|内|外)(?:\s+(.*))?$/
const ESTABLISHING_RE = /^【空镜\s*[：:]\s*(.*?)】?$/

/**
 * 翻译元信息行：「出场人物：A、B」→「Cast: A, B」；「日 内 教室」→「Day · INT. · 教室」。
 * 不认识的行原样返回。
 */
export function localizeScriptMetaLine(text: string, copy: ScriptLabelCopy): string {
  const trimmed = text.trim()
  const cast = trimmed.match(CAST_RE)
  if (cast) {
    const names = cast[1]
      .split(/[、,，]+/)
      .map((n) => n.trim())
      .filter(Boolean)
    return `${copy.castLabel}: ${names.join(copy.listSep)}`
  }
  const tp = trimmed.match(TIME_PLACE_RE)
  if (tp) {
    const timeKey = TIME_KEYS.find(([zh]) => zh === tp[1])?.[1]
    const placeKey = PLACE_KEYS[tp[2]]
    const parts = [timeKey ? copy.sceneTime[timeKey] : tp[1], placeKey ? copy.scenePlace[placeKey] : tp[2]]
    const rest = (tp[3] || '').trim()
    if (rest) parts.push(rest)
    return parts.join(' · ')
  }
  return text
}

/** 翻译空镜行：「【空镜：江面薄雾】」→「【Establishing shot: 江面薄雾】」；其他行原样返回 */
export function localizeScriptActionLine(text: string, copy: ScriptLabelCopy): string {
  const m = text.trim().match(ESTABLISHING_RE)
  if (!m) return text
  return `【${copy.establishing}: ${m[1].trim()}】`
}
