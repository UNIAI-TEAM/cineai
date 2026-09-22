/**
 * 漫剧分镜脚本校验（对齐 docs/EPISODE_RULES.md §3 / §9）
 * 用于生成前告警：时长、空镜误标对白、资产缺图/缺音色
 */
import type { DramaAsset, DramaFragment } from '../api/drama'
import {
  DRAMA_SEGMENT_DURATION_HARD_MAX,
  DRAMA_SEGMENT_DURATION_MAX,
  DRAMA_SEGMENT_DURATION_MIN,
  DRAMA_SHOT_DURATION_HARD_MAX,
  FRAGMENT_CONTENT_DURATION_MAX,
} from './dramaEpisodePromptEditor'
import { extractDurations, sumDuration } from './segmentDuration'
import { DRAMA_VOICE_BINDING_ENABLED } from './dramaVoiceBinding'
import { getActiveLocale } from '../i18n/detect'
import { interpolate, type TVars } from '../i18n/lookup'
import { messages } from '../i18n/messages'

type ValidateKey = keyof (typeof messages)['zh']['dramaEpisode']['validate']

// 按当前界面语言取校验提示文案（仅展示用，不进入提示词）
function vt(key: ValidateKey, vars?: TVars): string {
  return interpolate(messages[getActiveLocale()].dramaEpisode.validate[key], vars)
}

// 拼接名称列表（最多 5 个，超出加省略号）
function formatNameList(names: string[]): string {
  return `${names.slice(0, 5).join(vt('listSep'))}${names.length > 5 ? '…' : ''}`
}

/** 漫剧字幕 cue（与后端 DRAMA_SUBTITLE_CUE 一致） */
export const DRAMA_SUBTITLE_CUE = '【字幕：底部居中·简体中文·逐句轮换·与口播同步】'

/** 画面无配音前缀 */
export const VISUAL_PREFIX = '【画面·无配音仅环境音】'

/** 对白前缀 */
export const DIALOGUE_PREFIX = '【对白·慢速清晰·同步字幕】'

/** 旁白前缀 */
export const DRAMA_NARRATION_PREFIX = '【旁白·慢速清晰·同步字幕】'

// 空镜 / 景别冒号标签（与后端 VISUAL_SHOT_LABEL_RE 对齐）
const VISUAL_SHOT_LABEL_RE =
  /^(?:空镜|画面|远景|近景|中景|全景|特写|大特写|跟拍|俯拍|仰拍|航拍|推镜|拉镜|摇镜|环境|镜头|动作|转场|闪回|建立镜头|气氛镜头)\s*[：:]/

const VOICE_CUE_PREFIX_RE = /^【(?:对白|旁白|内心独白)[^】]*】\s*/

export type DramaScriptIssue = {
  level: 'error' | 'warn'
  message: string
}

// 去掉对白/旁白生产前缀
function stripVoiceCuePrefix(line: string): string {
  return (line || '').replace(VOICE_CUE_PREFIX_RE, '').trim()
}

// 角色是否已绑定可提交的参考音频
function assetHasVoiceBinding(asset: DramaAsset): boolean {
  const params = (asset.params || {}) as Record<string, unknown>
  const raw = params.voiceAudio
  if (raw && typeof raw === 'object') {
    const data = raw as Record<string, unknown>
    const url =
      typeof data.url === 'string'
        ? data.url
        : typeof data.previewUrl === 'string'
          ? data.previewUrl
          : ''
    if (url.trim()) return true
  }
  const canvas = params.canvas
  if (canvas && typeof canvas === 'object') {
    const voiceAudio = (canvas as Record<string, unknown>).voiceAudio
    if (voiceAudio && typeof voiceAudio === 'object') {
      const url = (voiceAudio as Record<string, unknown>).url
      if (typeof url === 'string' && url.trim()) return true
    }
  }
  return false
}

// 合并正文 @asset 与 asset_ids
function listFragmentAssetIds(frag: DramaFragment): number[] {
  const seen = new Set<number>()
  const out: number[] = []
  const re = /@asset:(\d+)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(frag.content || ''))) {
    const id = Number(m[1])
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  for (const id of frag.asset_ids || []) {
    if (!id || seen.has(id)) continue
    seen.add(id)
    out.push(id)
  }
  return out
}

// 判断正文是否为纯画面 / 空镜描写
export function isVisualDescriptionBody(text: string): boolean {
  let body = stripVoiceCuePrefix((text || '').trim())
  body = body.replace(/^【(?:画面|空镜)[^】]*】\s*/, '').trim()
  if (!body) return false
  if (VISUAL_SHOT_LABEL_RE.test(body)) return true
  if (body.startsWith('空镜') || body.startsWith('△') || body.startsWith('Δ')) return true
  return false
}

// 脚本是否含真实口播意图（排除空镜冒号）
function scriptLikelyNeedsVoice(content: string): boolean {
  for (const raw of (content || '').replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('@duration:')) continue
    if (
      line.startsWith('【字幕') ||
      line.startsWith('【BGM') ||
      line.startsWith('【人物介绍') ||
      line.startsWith('【片头') ||
      line.startsWith('【背景介绍')
    ) {
      continue
    }
    if (line.startsWith('【对白') || line.startsWith('【旁白') || line.startsWith('【内心独白')) {
      if (!isVisualDescriptionBody(line)) return true
      continue
    }
    if (isVisualDescriptionBody(line)) continue
    if (/^[^：:\n]{1,16}[：:]/.test(line) && !VISUAL_SHOT_LABEL_RE.test(line)) {
      return true
    }
  }
  return false
}

// 校验单镜脚本：时长 + 空镜误标
export function validateDramaFragmentScript(content: string): DramaScriptIssue[] {
  const issues: DramaScriptIssue[] = []
  const durations = extractDurations(content || '')
  const total = sumDuration(content || '')

  const badSegment = durations.find(
    (value) =>
      !Number.isFinite(value) ||
      value < DRAMA_SEGMENT_DURATION_MIN ||
      value > DRAMA_SEGMENT_DURATION_HARD_MAX,
  )
  if (badSegment != null) {
    issues.push({
      level: 'error',
      message: vt('segmentRange', {
        min: DRAMA_SEGMENT_DURATION_MIN,
        max: DRAMA_SEGMENT_DURATION_HARD_MAX,
      }),
    })
  } else if (durations.some((value) => value > DRAMA_SEGMENT_DURATION_MAX)) {
    issues.push({
      level: 'warn',
      message: vt('segmentOverSuggest', { max: DRAMA_SEGMENT_DURATION_MAX }),
    })
  }

  if (total > DRAMA_SHOT_DURATION_HARD_MAX) {
    issues.push({
      level: 'error',
      message: vt('totalOverHard', { total, max: DRAMA_SHOT_DURATION_HARD_MAX }),
    })
  } else if (total > FRAGMENT_CONTENT_DURATION_MAX) {
    issues.push({
      level: 'warn',
      message: vt('totalOverSuggest', { total, max: FRAGMENT_CONTENT_DURATION_MAX }),
    })
  }

  for (const raw of (content || '').replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('@duration:')) continue
    if (line.startsWith('【字幕') || line.startsWith('【BGM') || line.startsWith('【人物介绍')) {
      continue
    }
    if (VOICE_CUE_PREFIX_RE.test(line) && isVisualDescriptionBody(line)) {
      issues.push({
        level: 'error',
        message: vt('visualAsVoice'),
      })
      break
    }
  }

  return issues
}

// 校验本镜关联资产：缺图 / 说话角色缺音色（警告级，可继续生成）
export function validateDramaFragmentAssets(
  frag: DramaFragment | null | undefined,
  assets: DramaAsset[],
): DramaScriptIssue[] {
  const issues: DramaScriptIssue[] = []
  if (!frag) return issues

  const byId = new Map(assets.map((a) => [a.id, a]))
  const ids = listFragmentAssetIds(frag)
  const needsVoice = scriptLikelyNeedsVoice(frag.content || '')

  const missingImage: string[] = []
  const missingVoice: string[] = []

  for (const id of ids) {
    const asset = byId.get(id)
    if (!asset) {
      missingImage.push(`#${id}`)
      continue
    }
    const kind = (asset.type || '').toLowerCase()
    const hasImage = Boolean((asset.cover || asset.url || '').trim())
    if ((kind === 'character' || kind === 'scene' || kind === 'prop') && !hasImage) {
      missingImage.push(asset.name || `#${id}`)
    }
    if (DRAMA_VOICE_BINDING_ENABLED && kind === 'character' && needsVoice && !assetHasVoiceBinding(asset)) {
      missingVoice.push(asset.name || `#${id}`)
    }
  }

  if (missingImage.length > 0) {
    issues.push({
      level: 'warn',
      message: vt('missingImage', { names: formatNameList(missingImage) }),
    })
  }

  if (missingVoice.length > 0) {
    issues.push({
      level: 'warn',
      message: vt('missingVoice', { names: formatNameList(missingVoice) }),
    })
  }

  return issues
}

// 合并脚本与资产问题；有 error 则不可直接生成
export function collectDramaGenerateGateIssues(
  frag: DramaFragment | null | undefined,
  assets: DramaAsset[],
): { blocking: DramaScriptIssue[]; warnings: DramaScriptIssue[] } {
  const scriptIssues = validateDramaFragmentScript(frag?.content || '')
  const assetIssues = validateDramaFragmentAssets(frag, assets)
  const all = [...scriptIssues, ...assetIssues]
  return {
    blocking: all.filter((i) => i.level === 'error'),
    warnings: all.filter((i) => i.level === 'warn'),
  }
}

// 把问题列表拼成确认框文案
export function formatDramaGateMessage(
  blocking: DramaScriptIssue[],
  warnings: DramaScriptIssue[],
  baseMessage: string,
): string {
  const parts = [baseMessage]
  if (blocking.length > 0) {
    parts.push('', vt('mustFix'), ...blocking.map((i) => `· ${i.message}`))
  }
  if (warnings.length > 0) {
    parts.push('', vt('suggested'), ...warnings.map((i) => `· ${i.message}`))
  }
  return parts.join('\n')
}
