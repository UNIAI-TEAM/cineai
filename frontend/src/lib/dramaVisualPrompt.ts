/** 从资产 params 读取/拼装视觉生图提示词（对齐 manju buildCharacterParams + 弱提示检测） */
import type { DramaAsset } from '../api/drama'
import { CJK_RE } from './contentLang.ts'
import { appearanceIsEmpty, readAppearance } from './dramaAppearance.ts'

const WEAK_PROMPT = /^(character|scene|prop|material|none|image|audio|video)\s+\S+$/i

const GENERIC_MARKERS = [
  '影视级写实环境空间',
  '构图层次分明、光影有戏剧张力',
  '适合短剧横屏拍摄',
  '影视级写实场景，构图清晰，适合短剧拍摄',
  '影视级写实人物',
  '白底全身定妆照',
  // 越南语 / 英文项目的规则模板（后端 seed_asset_params.build_scene_params）
  'cinematic photorealistic environment, clear composition',
]

/* 生图提示词语言：中文项目用中文标签；越南语 / 英文项目用英文（生图模型对英文理解更好） */
type PromptLang = 'zh' | 'vi' | 'en'

// 未显式给出项目语言时按已有文字判断（含中文 → zh；空内容保持中文旧行为）
function resolvePromptLang(lang: PromptLang | undefined, sample: string): PromptLang {
  if (lang) return lang
  if (!sample.trim() || CJK_RE.test(sample)) return 'zh'
  return 'en'
}

const MIN_LEN: Record<string, number> = {
  character: 120,
  scene: 100,
  prop: 70,
  material: 70,
  video: 8,
}

// 是否模板化套话
function isGenericTemplate(text: string): boolean {
  if (text.length >= 180) return false
  return GENERIC_MARKERS.some((m) => text.includes(m))
}

// 判断提示词是否过短、占位或模板化
function isWeakVisualPrompt(prompt: string, assetName: string, kind: string): boolean {
  const text = prompt.trim()
  /* 含 @asset: 引用的是用户正文，不要当弱占位清掉 */
  if (/@asset:\d+/.test(text)) return false
  const kindLower = kind.toLowerCase()
  const minLen = MIN_LEN[kindLower] ?? 60
  if (text.length < minLen) return true
  const name = assetName.trim()
  if (name && (text.toLowerCase() === `${kindLower} ${name}`.toLowerCase() || text === name)) {
    return true
  }
  if (WEAK_PROMPT.test(text)) return true
  if (isGenericTemplate(text)) return true
  return false
}

// 按 manju buildCharacterParams 规则拼接（与后端 seed_asset_params.manju_join_character_prompt 一致）
function manjuJoinCharacterPrompt(params: Record<string, unknown>, lang?: PromptLang): string {
  const visual = String(params.visualImage || params.visualPrompt || '').trim()
  const raw = [params.title, params.roleType, params.coreTags, params.personality].map((v) =>
    String(v || '').trim(),
  )
  const zh = resolvePromptLang(lang, [visual, ...raw].join(' ')) === 'zh'
  /* 越南语 / 英文项目：丢掉 stub 里的中文占位值（如「出场人物」「配角」） */
  const [title, roleType, coreTags, personality] = zh ? raw : raw.map((v) => (CJK_RE.test(v) ? '' : v))
  const labels = zh
    ? ['身份：', '定位：', '标签：', '性格：']
    : ['Identity: ', 'Role: ', 'Tags: ', 'Personality: ']
  const parts = [
    visual,
    title ? `${labels[0]}${title}` : '',
    roleType ? `${labels[1]}${roleType}` : '',
    coreTags ? `${labels[2]}${coreTags}` : '',
    personality ? `${labels[3]}${personality}` : '',
  ].filter(Boolean)
  return parts.join(zh ? '。' : '. ')
}

/**
 * 读取资产视觉提示词：完整描述优先，过短/模板化时从角色字段拼装。
 * lang：项目内容语言（DramaProject.content_lang）；缺省时按资产文字判断。
 */
export function readVisualPrompt(asset: DramaAsset, lang?: PromptLang): string {
  const params = (asset.params || {}) as Record<string, unknown>
  const kind = (asset.type || '').toLowerCase()
  const name = asset.name || ''

  const canvas = params.canvas
  const canvasGen =
    canvas && typeof canvas === 'object'
      ? (canvas as Record<string, unknown>).generation
      : null
  const canvasPrompt =
    canvasGen && typeof canvasGen === 'object'
      ? String((canvasGen as Record<string, unknown>).prompt || '').trim()
      : ''
  const stored =
    String(params.visualPrompt || params.visualImage || canvasPrompt || '').trim()

  if (stored && !isWeakVisualPrompt(stored, name, kind)) {
    return stored
  }

  /* 按字段拼出的 / 手动编辑的角色提示词本身就是成品（已含身份/定位标签），短也不当弱占位再拼一遍，
     否则会重复追加「Role: …」（与后端 has_field_composed_prompt / promptManual 规则一致） */
  if (
    stored &&
    kind === 'character' &&
    (params.promptManual === true || !appearanceIsEmpty(readAppearance({ params })))
  ) {
    return stored
  }

  if (kind === 'character') {
    const composed = manjuJoinCharacterPrompt(params, lang)
    if (composed && !isWeakVisualPrompt(composed, name, kind)) return composed
  }

  if (kind === 'scene' && name) {
    if (resolvePromptLang(lang, name) === 'zh') {
      return `场景：${name}，影视级写实场景，构图清晰，适合短剧拍摄`
    }
    return `Scene: ${name}, cinematic photorealistic environment, clear composition, suitable for short drama filming`
  }

  if (stored) return stored
  return `${kind} ${name}`.trim()
}

/**
 * 画布/编辑用提示词：过滤「character 新角色」等弱占位，避免误填。
 */
export function readEditableVisualPrompt(asset: DramaAsset, lang?: PromptLang): string {
  const kind = (asset.type || '').toLowerCase()
  const name = asset.name || ''
  const prompt = readVisualPrompt(asset, lang).trim()
  if (!prompt || isWeakVisualPrompt(prompt, name, kind)) return ''
  return prompt
}

/** 文本是否为弱视觉提示词（占位/过短/模板） */
export function isWeakEditablePrompt(prompt: string, name = '', kind = ''): boolean {
  return isWeakVisualPrompt(prompt, name, kind)
}
