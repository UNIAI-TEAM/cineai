/**
 * 漫剧生成失败说明：把错误转成可读标题 / 说明 / 处理建议（文案走 i18n 的 dramaGenError）。
 * - 接口错误（ApiError 带 code）按错误码 / 状态码分类；
 * - 任务落库的 error_message（后台任务写入、暂无错误码）与生成队列自己的中文文案仍按文本分类。
 */

import { getActiveLocale } from '../i18n/detect'
import { interpolate, type TVars } from '../i18n/lookup'
import { messages } from '../i18n/messages'
import { ApiError } from './apiError'
import { isBillingError, isInsufficientBalanceCode } from './billingError'
import { dialog } from './dialog'

export type DramaGenErrorView = {
  /** 短标题 */
  title: string
  /** 用户可读说明 */
  message: string
  /** 建议操作 */
  suggestion?: string
  /** 是否余额不足（展示充值跳转） */
  billingBlocked?: boolean
  /** 是否上游模型账户欠费（提醒管理员，非用户钱包） */
  upstreamAccountBlocked?: boolean
}

type SlotKey = keyof (typeof messages)['zh']['dramaGenError']['slot']

// 后端 content_labels 里的中文槽位名 → 文案 key
const SLOT_KEYS: Record<string, SlotKey> = {
  角色: 'character',
  场景: 'scene',
  道具: 'prop',
  旁白: 'narration',
  参考图: 'reference',
  音色: 'voice',
}

// 表示「分镜已变更 / 已失效」的错误码
const FRAGMENT_CHANGED_CODES = new Set(['drama.fragment_not_found', 'drama.no_fragments_to_generate'])

/** 当前界面语言的 dramaGenError 文案 */
function copy() {
  return messages[getActiveLocale()].dramaGenError
}

/** 插值简写 */
function fmt(template: string, vars?: TVars): string {
  return interpolate(template, vars)
}

/** 超长原文截断 */
function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

/** 是否为上游 Seedream 账户欠费 */
export function isUpstreamAccountError(message: string): boolean {
  return /AccountOverdueError|上游 Seedream 账户欠费|上游.*账户欠费/i.test(message)
}

// 从 Seedance JSON 文案里取出 content[n]
function extractContentIndex(raw: string): number | null {
  const m = raw.match(/content\[(\d+)\]/i)
  if (!m) return null
  const n = Number(m[1])
  return Number.isFinite(n) ? n : null
}

/** 「提交内容第 n 项 / content[i]」 */
function contentItemText(idx: number): string {
  return fmt(copy().contentItem, { n: idx + 1, idx })
}

/** 判断文案是否像「具体根因」（优先于「重试上限」等包装句） */
function looksLikeRootCause(text: string): boolean {
  return /PrivacyInformation|InputImageSensitive|SensitiveContentDetected|参考图疑似|参考音频过短|may contain real person|Seedance create error|上一镜失败|无法衔接|分镜已变更|分镜上下文|InputTextSensitive|resource download failed|audio_url|audio duration|Credits insufficient|File type not supported|参考图格式不支持/i.test(
    text,
  )
}

/**
 * 从错误里抽出已标注的槽位（后端 content_labels，如「角色「小明」」）。
 * 参数 kinds：允许的中文槽位名。返回翻译后的槽位名与原名称，找不到为 null。
 */
function extractNamedSlot(
  text: string,
  kinds: string[] = ['角色', '场景', '道具', '旁白', '参考图', '音色'],
): { label: string; name: string } | null {
  const named = text.match(new RegExp(`(${kinds.join('|')})「([^」]+)」`))
  if (!named) return null
  const key = SLOT_KEYS[named[1]]
  const kind = key ? copy().slot[key] : named[1]
  return { label: fmt(copy().slotNamed, { kind, name: named[2] }), name: named[2] }
}

/**
 * 从多条候选错误里挑出最具体的根因（例如隐私图审核），
 * 避免只展示「重试超过上限」这类包装文案。
 */
export function pickRootDramaGenError(
  candidates: Array<string | null | undefined>,
): string {
  const cleaned = candidates.map((c) => String(c || '').trim()).filter(Boolean)
  const root = cleaned.find(looksLikeRootCause)
  if (root) return root
  return cleaned[0] || ''
}

/**
 * 接口错误按错误码 / 状态码分类；无 code 时返回 null，交给文本分类。
 * message 已由 parseApiError 按界面语言翻译。
 */
function formatApiError(err: ApiError): DramaGenErrorView | null {
  const c = copy()
  const code = err.code
  if (err.status === 402 || isInsufficientBalanceCode(code)) {
    return {
      title: c.billing.title,
      message: err.message || c.billing.message,
      suggestion: c.billing.suggestion,
      billingBlocked: true,
    }
  }
  if (!code) return null
  if (FRAGMENT_CHANGED_CODES.has(code)) {
    return {
      title: c.fragmentChanged.title,
      message: c.fragmentChanged.message,
      suggestion: c.fragmentChanged.suggestion,
    }
  }
  if (code === 'drama.prev_fragment_required') {
    return {
      title: c.prevFailed.title,
      message: err.message,
      suggestion: c.prevFailed.suggestion,
    }
  }
  return {
    title: c.genericFailed,
    message: err.message,
    suggestion: c.hintFollow,
  }
}

/**
 * 按文本分类：任务落库的 error_message、上游原始报错、生成队列自己的中文文案。
 * 已是中文短句时尽量保留，仅补建议。
 */
function formatErrorText(raw: string | null | undefined): DramaGenErrorView {
  const c = copy()
  const text = String(raw || '').trim()
  if (!text) {
    return { title: c.genericFailed, message: c.empty.message, suggestion: c.empty.suggestion }
  }

  if (/ReadTimeout|WriteTimeout|等待上游超时|响应超时/i.test(text)) {
    return { title: c.timeout.title, message: clip(text, 200), suggestion: c.timeout.suggestion }
  }

  if (/网络错误|ConnectError|ConnectTimeout|无法连接上游|tokenfree\.com|api\.kie\.ai/i.test(text)) {
    return { title: c.network.title, message: clip(text, 200), suggestion: c.network.suggestion }
  }

  // 生图队列兜底文案（dramaImageGenQueue 写入）
  if (/^生图失败$/.test(text)) {
    return {
      title: c.imageFailedLegacy.title,
      message: c.imageFailedLegacy.message,
      suggestion: c.imageFailedLegacy.suggestion,
    }
  }

  if (isUpstreamAccountError(text) || (/Seedream error 403/i.test(text) && /AccountOverdue/i.test(text))) {
    return {
      title: c.upstreamAccount.title,
      message: c.upstreamAccount.message,
      suggestion: c.upstreamAccount.suggestion,
      upstreamAccountBlocked: true,
    }
  }

  if (isBillingError(text)) {
    return {
      title: c.billing.title,
      message: text || c.billing.message,
      suggestion: c.billing.suggestion,
      billingBlocked: true,
    }
  }

  if (
    /参考图疑似真人|PrivacyInformation|InputImageSensitive|SensitiveContentDetected|may contain real person/i.test(
      text,
    )
  ) {
    const named = extractNamedSlot(text, ['角色', '场景', '道具', '参考图'])
    if (named) {
      return {
        title: c.realPerson.title,
        message: fmt(c.realPerson.namedMessage, { slot: named.label }),
        suggestion: fmt(c.realPerson.namedSuggestion, { name: named.name }),
      }
    }
    const idx = extractContentIndex(text)
    const where =
      idx != null ? fmt(c.realPerson.whereIndex, { item: contentItemText(idx) }) : c.realPerson.whereUnknown
    return {
      title: c.realPerson.title,
      message: fmt(c.realPerson.message, { where }),
      suggestion: c.realPerson.suggestion,
    }
  }

  if (/重试超过上限|超过重试上限|内部自动重试超过上限/.test(text)) {
    return { title: c.retryExhausted.title, message: text, suggestion: c.retryExhausted.suggestion }
  }

  if (/上一镜失败|无法衔接尾帧/.test(text)) {
    return { title: c.prevFailed.title, message: c.prevFailed.message, suggestion: c.prevFailed.suggestion }
  }

  // 后台任务落库文案（jobs.py「分镜不存在」等），接口错误已改按错误码判断
  if (/分镜已变更|分镜上下文丢失|分镜不存在/.test(text)) {
    return {
      title: c.fragmentChanged.title,
      message: c.fragmentChanged.message,
      suggestion: c.fragmentChanged.suggestion,
    }
  }

  if (/InputTextSensitive|text.*sensitive|敏感/i.test(text) && /Seedance|create error/i.test(text)) {
    return {
      title: c.textSensitive.title,
      message: c.textSensitive.message,
      suggestion: c.textSensitive.suggestion,
    }
  }

  if (/resource download failed|audio_url/i.test(text) && !/audio duration/i.test(text)) {
    return {
      title: c.audioDownload.title,
      message: c.audioDownload.message,
      suggestion: c.audioDownload.suggestion,
    }
  }

  // Seedance r2v：reference_audio 须 ≥ 1.8 秒（不是参考图）
  if (/audio duration|参考音频过短|1\.8/i.test(text) && /audio|音色|reference_audio|content\[/i.test(text)) {
    const idx = extractContentIndex(text)
    const named = extractNamedSlot(text)
    const where =
      named?.label ||
      (idx != null
        ? fmt(c.audioTooShort.whereIndex, { item: contentItemText(idx) })
        : c.audioTooShort.whereUnknown)
    return {
      title: c.audioTooShort.title,
      message: fmt(c.audioTooShort.message, { where }),
      suggestion: c.audioTooShort.suggestion,
    }
  }

  if (/only support adaptive aspect ratio|adaptive aspect ratio/i.test(text)) {
    return { title: c.aspectRatio.title, message: c.aspectRatio.message, suggestion: c.aspectRatio.suggestion }
  }

  if (/Credits insufficient|积分不足|余额不足.*[Kk]ie|Kie.*积分/i.test(text)) {
    return {
      title: c.channelCredits.title,
      message: c.channelCredits.message,
      suggestion: c.channelCredits.suggestion,
      upstreamAccountBlocked: true,
    }
  }

  if (/File type not supported|参考图格式不支持|不支持 SVG/i.test(text)) {
    return {
      title: c.fileType.title,
      message: text.includes('参考图格式不支持') ? text : c.fileType.message,
      suggestion: c.fileType.suggestion,
    }
  }

  if (/Seedance create error\s*400|Kie createTask error/i.test(text)) {
    const idx = extractContentIndex(text)
    const named = extractNamedSlot(text)
    const where = named
      ? fmt(c.rejected.whereIndex, { item: named.label })
      : idx != null
        ? fmt(c.rejected.whereIndex, { item: contentItemText(idx) })
        : ''
    return {
      title: c.rejected.title,
      message: fmt(c.rejected.message, { where }),
      suggestion: c.rejected.suggestion,
    }
  }

  if (/Seedance|上游生成失败/i.test(text)) {
    return { title: c.videoFailed.title, message: clip(text, 160), suggestion: c.videoFailed.suggestion }
  }

  if (/跳过重复任务|分镜已生成完成/.test(text)) {
    return {
      title: c.duplicateSkipped.title,
      message: c.duplicateSkipped.message,
      suggestion: c.duplicateSkipped.suggestion,
    }
  }

  // 生成队列写入的「已取消」「生图已取消」「任务已中断，请重新生成」按界面语言展示，其余原文保留
  if (/已取消|任务已中断/.test(text)) {
    const cancelled = text.includes('取消')
    const known = /^(已取消|生图已取消|任务已中断，请重新生成)$/.test(text)
    return {
      title: cancelled ? c.cancelled.title : c.cancelled.interruptedTitle,
      message: known ? (cancelled ? c.cancelled.message : c.cancelled.interruptedMessage) : text,
      suggestion: c.cancelled.suggestion,
    }
  }

  // 已是较短中文：原样展示，补通用建议
  if (!/[{\\[\]"]/.test(text) && text.length <= 120 && /[一-鿿]/.test(text)) {
    return { title: c.genericFailed, message: text, suggestion: c.hintFollow }
  }

  return { title: c.genericFailed, message: clip(text, 200), suggestion: c.hintDefault }
}

/**
 * 将错误转为前端展示文案。
 * 参数 raw：接口抛出的 ApiError（按错误码分类）、其他 Error，或任务 error / error_message 字符串（按文本分类）。
 */
export function formatDramaGenError(raw: unknown): DramaGenErrorView {
  if (raw instanceof ApiError) {
    const view = formatApiError(raw)
    if (view) return view
  }
  const text = raw instanceof Error ? raw.message : typeof raw === 'string' ? raw : String(raw ?? '')
  return formatErrorText(text)
}

/** 弹窗展示生成失败（含上游欠费 / 用户余额不足等）；raw 同 formatDramaGenError */
export async function alertDramaGenError(raw: unknown): Promise<void> {
  const view = formatDramaGenError(raw)
  const body = [view.message, view.suggestion].filter(Boolean).join('\n\n')
  await dialog.alert({
    title: view.title,
    message: body || view.title,
    tone: 'danger',
  })
}
