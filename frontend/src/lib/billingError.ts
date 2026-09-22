import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { dialog } from './dialog'

export const PRICING_PATH = '/pricing'

// 由错误码识别出的余额不足文案（翻译后不再含「余额不足」，靠登记识别）
const billingMessages = new Set<string>()

/** 登记一条余额不足文案，供只拿到字符串的组件识别 */
export function markBillingMessage(message: string) {
  billingMessages.add(message)
}

/** 是否为余额不足 / 计费拦截类错误（错误码登记 + 旧中文文案兜底，漫剧第二阶段前保留） */
export function isBillingError(message: string) {
  return billingMessages.has(message) || /余额不足|请先充值|402|insufficient_balance/i.test(message)
}

/** 是否为余额不足类错误码（billing.insufficient_balance*） */
export function isInsufficientBalanceCode(code?: string): boolean {
  return Boolean(code && code.startsWith('billing.insufficient_balance'))
}

// 结构化判断：ApiError 带 402 或 billing.insufficient_balance* 码（不引入 apiError 以免循环依赖）
function isBillingErrorObject(err: unknown): boolean {
  if (!err || typeof err !== 'object') return false
  const e = err as { status?: unknown; code?: unknown }
  return e.status === 402 || (typeof e.code === 'string' && isInsufficientBalanceCode(e.code))
}

/** 跳转定价页充值 */
export function goToTopup() {
  if (typeof window !== 'undefined') {
    window.location.assign(PRICING_PATH)
  }
}

/**
 * 弹出余额不足提示；若用户选择去充值则跳转定价页。
 * @returns 是否已按计费错误处理
 */
export async function handleBillingError(
  err: unknown,
  navigate?: (path: string) => void,
): Promise<boolean> {
  const message = err instanceof Error ? err.message : String(err || '')
  if (!isBillingErrorObject(err) && !isBillingError(message)) return false
  // 非组件环境：按当前界面语言取文案
  const m = messages[getActiveLocale()]
  const go = await dialog.confirm({
    title: m.billing.insufficientTitle,
    message: message || m.billing.insufficientMessage,
    confirmText: m.billing.topup,
    cancelText: m.dialog.ok,
    tone: 'danger',
  })
  if (go) {
    if (navigate) navigate(PRICING_PATH)
    else goToTopup()
  }
  return true
}

/**
 * API 层全局拦截：402 / 余额不足时弹出充值引导（不吞掉原错误）。
 */
export function notifyBillingErrorIfNeeded(status: number, message: string) {
  if (status === 402 || isBillingError(message)) {
    void handleBillingError(new Error(message))
  }
}
