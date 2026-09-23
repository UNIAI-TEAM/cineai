/**
 * 剧本 / 分镜正文结构标签的「显示 ↔ 规范」双向转换（纯函数，无 DOM）。
 *
 * 数据库里存的是后端解析器与提示词依赖的中文标签（规范形态）：
 *   剧本：「### 场1-2」「日 内 教室」「出场人物：A、B」「【空镜：…】」「旁白（vo）：」
 *   分镜：「【对白·慢速清晰·同步字幕】」「【BGM：…；音量低于人声】」「空镜：/远景：…」等
 * vi / en 界面在「载入编辑框 / 只读展示」时调用 toDisplayScript 换成当前语言，
 * 在「保存 / 提交 / 校验」前调用 toCanonicalScript 换回中文标签。中文界面两者都是原样返回。
 *
 * 只认结构位置（行首、### 之后、行首【…】标记之后），台词正文与句中文字一律不动。
 * 规范写法（全角冒号、标签后无空格、「日 内 X」/「日内 X」）可精确往返：
 *   toCanonicalScript(toDisplayScript(x)) === x
 * 非规范写法（半角冒号、「场景1-2」、名单里的「, 」等）保存时会被规整成规范写法，语义不变。
 * 用户直接粘贴的中文标签在 toCanonicalScript 中原样保留。
 */
import type { Locale } from '../i18n/detect'
import { messages } from '../i18n/messages'

type ScriptMessages = (typeof messages)['zh']['dramaEpisode']['scriptLabels']
type CameraItemId = keyof (typeof messages)['zh']['dramaEpisode']['camera']['items']
type ShotKey = keyof ScriptMessages['shots']
type MarkerKey = keyof ScriptMessages['markers']
type MoodKey = keyof ScriptMessages['bgm']['moods']
type TimeKey = keyof (typeof messages)['zh']['dramaProject']['preview']['sceneTime']
type PlaceKey = keyof (typeof messages)['zh']['dramaProject']['preview']['scenePlace']

/** 景别 / 运镜 / 画面类行首标签（与后端 VISUAL_SHOT_LABEL_RE + 运镜词库对齐）→ 文案来源 */
const SHOT_LABELS: Array<[string, { camera: CameraItemId } | { shot: ShotKey }]> = [
  ['空镜', { camera: 'empty' }],
  ['远景', { camera: 'wide' }],
  ['全景', { camera: 'full' }],
  ['中景', { camera: 'medium' }],
  ['近景', { camera: 'close' }],
  ['特写', { camera: 'closeup' }],
  ['大特写', { camera: 'ecu' }],
  ['建立镜头', { camera: 'establish' }],
  ['气氛镜头', { camera: 'atmosphere' }],
  ['推镜', { camera: 'push' }],
  ['拉镜', { camera: 'pull' }],
  ['摇镜', { camera: 'pan' }],
  ['移镜', { camera: 'truck' }],
  ['跟拍', { camera: 'follow' }],
  ['俯拍', { camera: 'high' }],
  ['仰拍', { camera: 'low' }],
  ['航拍', { camera: 'aerial' }],
  ['画面', { shot: 'visual' }],
  ['环境', { shot: 'ambient' }],
  ['镜头', { shot: 'camera' }],
  ['动作', { shot: 'action' }],
  ['转场', { shot: 'transition' }],
  ['闪回', { shot: 'flashback' }],
]

/** 分镜正文行首固定协议标记（【】内文字，与后端 build_fragments / seedance_segments 常量一致） */
const MARKERS: Array<[string, MarkerKey]> = [
  ['对白·慢速清晰·同步字幕', 'dialogueSub'],
  ['对白·慢速清晰', 'dialogue'],
  ['旁白·慢速清晰·同步字幕', 'narrationSub'],
  ['旁白·慢速清晰', 'narration'],
  ['旁白·自然语速·同步字幕', 'narrationNaturalSub'],
  ['旁白·自然语速', 'narrationNatural'],
  ['内心独白·同步字幕', 'innerSub'],
  ['内心独白', 'inner'],
  ['画面·无配音仅环境音', 'visualOnly'],
  ['空镜·可仅环境音与 BGM', 'emptyShot'],
  ['人物介绍·画面叠字·角色身旁', 'characterIntro'],
  ['人物介绍·画面叠字', 'characterIntroLegacy'],
  ['片头·集号叠字', 'openingEpisodeNo'],
  ['片头·集名叠字', 'openingEpisodeTitle'],
  ['片头·剧名叠字', 'openingSeriesTitle'],
  ['片头·类型标注', 'openingGenre'],
  ['背景介绍·画面叠字', 'backgroundIntro'],
  ['字幕：底部居中·简体中文·逐句轮换·与口播同步', 'subtitleZh'],
  ['字幕：底部居中·越南语·逐句轮换·与口播同步', 'subtitleVi'],
  ['字幕：底部居中·英语·逐句轮换·与口播同步', 'subtitleEn'],
  ['字幕：底部居中·简体中文·仅标记段落同步', 'subtitleZhLegacyMarked'],
  ['字幕：底部居中·简体中文', 'subtitleZhLegacyPlain'],
  ['字幕：全程简体中文字幕，旁白逐句同步烧录', 'subtitleZhLegacyFull'],
]

/** 后端 _infer_bgm_mood 的固定配乐描述 */
const BGM_MOODS: Array<[string, MoodKey]> = [
  ['低沉紧张、鼓点渐强，烘托压迫与危机感', 'tense'],
  ['庄重史诗、弦乐铺底，气势恢宏但不抢戏', 'epic'],
  ['神秘悬疑、低频铺底，留白感强', 'mystery'],
  ['流动感环境音乐，水声与弦乐交织', 'water'],
  ['轻柔开阔、希望感，钢琴或弦乐为主', 'hopeful'],
  ['贴合剧情氛围的轻量配乐，情绪随画面起伏', 'neutral'],
]
const BGM_QUIETER = '音量低于人声'

// 时间标签（长的放前面，避免「清晨」被「晨」截断）
const TIME_LABELS: Array<[string, TimeKey]> = [
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
const PLACE_LABELS: Array<[string, PlaceKey]> = [
  ['内外', 'both'],
  ['内', 'interior'],
  ['外', 'exterior'],
]

const CANON_SCENE = '场'
const CANON_CAST = '出场人物'
const CANON_NO_CAST = '无'
const CANON_NARRATOR = '旁白'
const CANON_CAST_SEP = '、'

/** 某一界面语言下的全部对照表与正则（按语言缓存） */
type LocaleTables = {
  sceneHeading: string
  castLabel: string
  noCast: string
  listSep: string
  narrator: string
  emptyShot: string
  bgmQuieter: string
  shotToDisplay: Map<string, string>
  shotFromDisplay: Map<string, string>
  markerToDisplay: Map<string, string>
  markerFromDisplay: Map<string, string>
  moodToDisplay: Map<string, string>
  moodFromDisplay: Map<string, string>
  timeToDisplay: Map<string, string>
  timeFromDisplay: Map<string, string>
  placeToDisplay: Map<string, string>
  placeFromDisplay: Map<string, string>
  displayHeadingRe: RegExp
  displayCastRe: RegExp
  displayTimePlaceRe: RegExp
  displayShotRe: RegExp
  displayNarratorRe: RegExp
  displayEmptyTokenRe: RegExp
  displayBgmRe: RegExp
}

// 正则转义
function escapeRe(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')
}

// 多个候选词拼成正则分支（长词优先，避免前缀截断）
function alternation(words: string[]): string {
  return [...new Set(words.filter(Boolean))]
    .sort((a, b) => b.length - a.length)
    .map(escapeRe)
    .join('|')
}

// 显示名反查用 key：大小写不敏感
function foldKey(text: string): string {
  return text.trim().toLocaleLowerCase()
}

// 建立双向对照：canonical → display，display(小写) → canonical
function buildPairs<K extends string>(
  pairs: Array<[string, K]>,
  resolve: (key: K) => string,
): { to: Map<string, string>; from: Map<string, string> } {
  const to = new Map<string, string>()
  const from = new Map<string, string>()
  for (const [canon, key] of pairs) {
    const display = resolve(key)
    to.set(canon, display)
    from.set(foldKey(display), canon)
  }
  return { to, from }
}

const tablesCache = new Map<Locale, LocaleTables>()

// 取（并缓存）某语言的对照表；zh 不会走到这里
function tablesFor(locale: Locale): LocaleTables {
  const cached = tablesCache.get(locale)
  if (cached) return cached
  const m = messages[locale]
  const sl = m.dramaEpisode.scriptLabels
  const preview = m.dramaProject.preview
  const cameraItems = m.dramaEpisode.camera.items

  const shots = buildPairs(SHOT_LABELS.map(([c], i) => [c, String(i)] as [string, string]), (i) => {
    const src = SHOT_LABELS[Number(i)][1]
    return 'camera' in src ? cameraItems[src.camera].label : sl.shots[src.shot]
  })
  const markers = buildPairs(MARKERS, (k) => sl.markers[k])
  const moods = buildPairs(BGM_MOODS, (k) => sl.bgm.moods[k])
  const times = buildPairs(TIME_LABELS, (k) => preview.sceneTime[k])
  const places = buildPairs(PLACE_LABELS, (k) => preview.scenePlace[k])

  const headingAlt = alternation([sl.sceneHeading, sl.sceneHeadingAlt])
  const castAlt = alternation([preview.castLabel, sl.castLabelAlt])
  const timeAlt = alternation([...times.to.values()])
  const placeAlt = alternation([...places.to.values()])
  const shotAlt = alternation([...shots.to.values()])
  const emptyShot = shots.to.get('空镜') || ''

  const tables: LocaleTables = {
    sceneHeading: sl.sceneHeading,
    castLabel: preview.castLabel,
    noCast: sl.noCast,
    listSep: preview.listSep,
    narrator: sl.narrator,
    emptyShot,
    bgmQuieter: sl.bgm.quieter,
    shotToDisplay: shots.to,
    shotFromDisplay: shots.from,
    markerToDisplay: markers.to,
    markerFromDisplay: markers.from,
    moodToDisplay: moods.to,
    moodFromDisplay: moods.from,
    timeToDisplay: times.to,
    timeFromDisplay: times.from,
    placeToDisplay: places.to,
    placeFromDisplay: places.from,
    displayHeadingRe: new RegExp(`^(#{1,3})(\\s*)(?:${headingAlt})( ?)(\\s*\\d.*)$`, 'iu'),
    displayCastRe: new RegExp(`^(?:${castAlt})[ \\t]*[:：] ?(.*)$`, 'iu'),
    displayTimePlaceRe: new RegExp(
      `^(?:(${timeAlt})([ \\t]*·[ \\t]*))?(${placeAlt})(?:[ \\t]*·[ \\t]*(.*))?$`,
      'iu',
    ),
    displayShotRe: new RegExp(`^(${shotAlt})[ \\t]*[:：] ?(.*)$`, 'iu'),
    displayNarratorRe: new RegExp(
      `^(?:${escapeRe(sl.narrator)})(?:[ \\t]*[（(]([^）)\\n]*)[）)])?[ \\t]*[:：] ?(.*)$`,
      'iu',
    ),
    displayEmptyTokenRe: new RegExp(`^【(?:${escapeRe(emptyShot)})[ \\t]*[:：] ?([^】]*)】$`, 'iu'),
    displayBgmRe: new RegExp(`^【BGM[ \\t]*[:：] ?(.*?)(; ${escapeRe(sl.bgm.quieter)})?】$`, 'iu'),
  }
  tablesCache.set(locale, tables)
  return tables
}

// ---------- 规范 → 显示 ----------

const CANON_HEADING_RE = /^(#{1,3})(\s*)场(?:景)?(\s*\d.*)$/
const CANON_CAST_RE = /^出场人物[ \t]*[：:](.*)$/
const CANON_TIME_PLACE_RE = /^(黄昏|傍晚|凌晨|清晨|日|夜|晨|早|午|晚)?([ \t]*)(内外|内|外)(?:([ \t]+)(.*))?$/
const CANON_SHOT_RE = new RegExp(`^(${alternation(SHOT_LABELS.map(([c]) => c))})[ \\t]*[：:](.*)$`)
const CANON_NARRATOR_RE = /^旁白(?:[ \t]*[（(]([^）)\n]*)[）)])?[ \t]*[：:](.*)$/
const CANON_EMPTY_TOKEN_RE = /^【空镜[ \t]*[：:]([^】]*)】$/
const CANON_BGM_RE = /^【BGM[ \t]*：(.*?)(；音量低于人声)?】$/
// 行首：可选 @duration，随后是若干【…】标记，最后是正文
const LINE_PREFIX_RE = /^((?:@duration:\d+[ \t]*)?(?:【[^】\n]*】[ \t]*)*)(.*)$/
const TOKEN_RE = /【[^】\n]*】/g

// 名单：「A、B」→「A, B」；整栏为「无」时换成「Không có / None」
function castNamesToDisplay(rest: string, t: LocaleTables): string {
  const m = rest.match(/^(\s*)无(\s*)$/)
  if (m) return `${m[1]}${t.noCast}${m[2]}`
  return rest.split(CANON_CAST_SEP).join(t.listSep)
}

// 单个【…】标记 → 显示
function tokenToDisplay(token: string, t: LocaleTables): string {
  const inner = token.slice(1, -1)
  const fixed = t.markerToDisplay.get(inner)
  if (fixed) return `【${fixed}】`
  const empty = token.match(CANON_EMPTY_TOKEN_RE)
  if (empty) return `【${t.emptyShot}: ${empty[1]}】`
  const bgm = token.match(CANON_BGM_RE)
  if (bgm) {
    const mood = t.moodToDisplay.get(bgm[1]) ?? bgm[1]
    return `【BGM: ${mood}${bgm[2] ? `; ${t.bgmQuieter}` : ''}】`
  }
  return token
}

// 行首【…】之后的正文标签（景别 / 旁白）→ 显示
function bodyLabelToDisplay(body: string, t: LocaleTables): string {
  const shot = body.match(CANON_SHOT_RE)
  if (shot) return `${t.shotToDisplay.get(shot[1]) ?? shot[1]}: ${shot[2]}`
  const narr = body.match(CANON_NARRATOR_RE)
  if (narr) {
    const paren = narr[1] !== undefined ? ` (${narr[1]})` : ''
    return `${t.narrator}${paren}: ${narr[2]}`
  }
  return body
}

// 单行（不含换行符）规范 → 显示
function lineToDisplay(line: string, t: LocaleTables): string {
  const lead = line.match(/^[ \t　]*/)?.[0] ?? ''
  const body = line.slice(lead.length)
  if (!body) return line

  const heading = body.match(CANON_HEADING_RE)
  if (heading) return `${lead}${heading[1]}${heading[2]}${t.sceneHeading} ${heading[3]}`

  const cast = body.match(CANON_CAST_RE)
  if (cast) return `${lead}${t.castLabel}: ${castNamesToDisplay(cast[1], t)}`

  const tp = body.match(CANON_TIME_PLACE_RE)
  if (tp && (tp[1] || tp[5] !== undefined)) {
    const place = t.placeToDisplay.get(tp[3]) ?? tp[3]
    let out = place
    if (tp[1]) out = `${t.timeToDisplay.get(tp[1]) ?? tp[1]}${tp[2] === '' ? '·' : ' · '}${place}`
    if (tp[5] !== undefined) out += ` · ${tp[5]}`
    return `${lead}${out}`
  }

  const pm = body.match(LINE_PREFIX_RE)
  if (!pm) return line
  const prefix = pm[1].replace(TOKEN_RE, (tok) => tokenToDisplay(tok, t))
  return `${lead}${prefix}${bodyLabelToDisplay(pm[2], t)}`
}

// ---------- 显示 → 规范 ----------

// 名单：「A, B」→「A、B」；「Không có / None」→「无」
function castNamesToCanonical(rest: string, t: LocaleTables): string {
  const m = rest.match(/^(\s*)(.*?)(\s*)$/)
  if (m && m[2] && foldKey(m[2]) === foldKey(t.noCast)) return `${m[1]}${CANON_NO_CAST}${m[3]}`
  return rest.split(t.listSep).join(CANON_CAST_SEP)
}

// 单个【…】标记 → 规范
function tokenToCanonical(token: string, t: LocaleTables): string {
  const inner = token.slice(1, -1)
  const fixed = t.markerFromDisplay.get(foldKey(inner))
  if (fixed) return `【${fixed}】`
  const empty = token.match(t.displayEmptyTokenRe)
  if (empty) return `【空镜：${empty[1]}】`
  const bgm = token.match(t.displayBgmRe)
  if (bgm) {
    const mood = t.moodFromDisplay.get(foldKey(bgm[1])) ?? bgm[1]
    return `【BGM：${mood}${bgm[2] ? `；${BGM_QUIETER}` : ''}】`
  }
  return token
}

// 行首【…】之后的显示标签 → 规范
function bodyLabelToCanonical(body: string, t: LocaleTables): string {
  const shot = body.match(t.displayShotRe)
  if (shot) {
    const canon = t.shotFromDisplay.get(foldKey(shot[1]))
    if (canon) return `${canon}：${shot[2]}`
  }
  const narr = body.match(t.displayNarratorRe)
  if (narr) {
    const paren = narr[1] !== undefined ? `（${narr[1]}）` : ''
    return `${CANON_NARRATOR}${paren}：${narr[2]}`
  }
  return body
}

// 单行显示 → 规范（中文标签原样保留）
function lineToCanonical(line: string, t: LocaleTables): string {
  const lead = line.match(/^[ \t　]*/)?.[0] ?? ''
  const body = line.slice(lead.length)
  if (!body) return line

  const heading = body.match(t.displayHeadingRe)
  if (heading) return `${lead}${heading[1]}${heading[2]}${CANON_SCENE}${heading[4]}`

  const cast = body.match(t.displayCastRe)
  if (cast) return `${lead}${CANON_CAST}：${castNamesToCanonical(cast[1], t)}`

  const tp = body.match(t.displayTimePlaceRe)
  if (tp && (tp[1] || tp[4] !== undefined)) {
    const place = t.placeFromDisplay.get(foldKey(tp[3]))
    const time = tp[1] ? t.timeFromDisplay.get(foldKey(tp[1])) : ''
    if (place && time !== undefined) {
      let out = place
      if (time) out = `${time}${tp[2] === '·' ? '' : ' '}${place}`
      if (tp[4] !== undefined) out += ` ${tp[4]}`
      return `${lead}${out}`
    }
  }

  const pm = body.match(LINE_PREFIX_RE)
  if (!pm) return line
  const prefix = pm[1].replace(TOKEN_RE, (tok) => tokenToCanonical(tok, t))
  return `${lead}${prefix}${bodyLabelToCanonical(pm[2], t)}`
}

// 逐行转换，保留原换行符（\n / \r\n）
function mapLines(text: string, fn: (line: string) => string): string {
  const parts = text.split(/(\r?\n)/)
  for (let i = 0; i < parts.length; i += 2) parts[i] = fn(parts[i])
  return parts.join('')
}

/**
 * 规范（中文标签）→ 当前界面语言的显示文本。用于载入编辑框 / 只读展示。
 * @param text 数据库里的剧本或分镜正文
 * @param locale 界面语言；zh 原样返回
 */
export function toDisplayScript(text: string, locale: Locale): string {
  if (!text || locale === 'zh') return text
  const t = tablesFor(locale)
  return mapLines(text, (line) => lineToDisplay(line, t))
}

/**
 * 显示文本 → 规范（中文标签）。用于保存 / 提交 AI / 客户端校验之前。
 * 同时接受当前语言的显示标签与原有中文标签（粘贴旧剧本）；zh 原样返回。
 */
export function toCanonicalScript(text: string, locale: Locale): string {
  if (!text || locale === 'zh') return text
  const t = tablesFor(locale)
  return mapLines(text, (line) => lineToCanonical(line, t))
}

/** 台词说话人显示名：「旁白」→ 当前语言；角色名原样 */
export function displayScriptSpeaker(speaker: string, locale: Locale): string {
  if (locale === 'zh' || speaker.trim() !== CANON_NARRATOR) return speaker
  return tablesFor(locale).narrator
}
