/**
 * 音色 × 内容语言（与后端 services/voice_lang.py 同一规则）：
 * - 音色能读的语言看 /api/voices 返回的 languages；缺失时视为不限（老接口 / 自定义音色）
 * - 每种语言在目录中排在最前的音色为默认音色；需要保持性别时取同性别的第一个
 */

/** 与 api.ts VoicePreset 兼容的最小结构（纯函数便于 node 测试） */
export type VoiceLike = {
  id: string
  speaker?: string
  gender?: string
  languages?: string[] | null
}

/** 音色是否能读该语言；语言未知或音色未声明 languages 时视为支持 */
export function voiceSupportsLang(voice: VoiceLike, lang: string | null | undefined): boolean {
  if (!lang) return true
  const langs = voice.languages
  if (!langs || !langs.length) return true
  return langs.includes(lang)
}

/**
 * 音色卡片列表：只保留支持项目内容语言的音色（目录顺序不变）；没有任何匹配时返回全部，避免空列表。
 */
export function voicesForLang<T extends VoiceLike>(voices: T[], lang: string | null | undefined): T[] {
  if (!lang) return voices
  const matched = voices.filter((v) => voiceSupportsLang(v, lang))
  return matched.length ? matched : voices
}

/** 该语言默认音色：同性别的第一个，否则该语言第一个；目录无该语言返回 undefined */
export function defaultVoiceForLang<T extends VoiceLike>(
  voices: T[],
  lang: string,
  gender?: string | null,
): T | undefined {
  const candidates = voices.filter((v) => (v.languages || []).includes(lang))
  if (!candidates.length) return undefined
  return (gender && candidates.find((v) => v.gender === gender)) || candidates[0]
}

/**
 * 当前所选音色不支持项目语言时给出替换音色的 key（speaker 优先），否则返回 null（保持用户选择）。
 * 参数 selectedKey：当前 voice_id / speaker
 */
export function voiceKeyForLang<T extends VoiceLike>(
  voices: T[],
  selectedKey: string,
  lang: string | null | undefined,
): string | null {
  if (!lang || !selectedKey) return null
  const current = voices.find((v) => v.id === selectedKey || v.speaker === selectedKey)
  if (!current || voiceSupportsLang(current, lang)) return null
  const next = defaultVoiceForLang(voices, lang, current.gender)
  if (!next) return null
  return next.speaker || next.id
}
