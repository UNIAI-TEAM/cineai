import { formatFenActive } from '../currency/store'
import { getActiveLocale } from '../i18n/detect'
import { interpolate, type TVars } from '../i18n/lookup'
import { messages } from '../i18n/messages'
import { markBillingMessage, notifyBillingErrorIfNeeded } from './billingError'

type CommonKey = keyof (typeof messages)['zh']['common']
type ErrorParams = Record<string, unknown>

/** 接口错误：带 HTTP 状态与后端错误码；message 已按界面语言翻译 */
export class ApiError extends Error {
  status: number
  code?: string
  params?: ErrorParams

  constructor(message: string, status: number, code?: string, params?: ErrorParams) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.params = params
  }
}

/** 按当前界面语言取通用报错兜底文案（供非 React 的 api 层使用） */
export function apiErrorText(key: CommonKey): string {
  return messages[getActiveLocale()].common[key]
}

/** 是否为余额不足类错误码（billing.insufficient_balance*） */
export function isInsufficientBalanceCode(code?: string): boolean {
  return Boolean(code && code.startsWith('billing.insufficient_balance'))
}

// 后端 params → 插值变量：*_fen 按当前展示货币格式化并去掉后缀
function toTemplateVars(params: ErrorParams): TVars {
  const vars: TVars = {}
  for (const [key, value] of Object.entries(params)) {
    if (key.endsWith('_fen') && typeof value === 'number') {
      vars[key.slice(0, -4)] = formatFenActive(value)
    } else if (typeof value === 'string' || typeof value === 'number') {
      vars[key] = value
    }
  }
  return vars
}

// detail 转可读文案：字符串原样，422 校验数组拼接 msg
function detailText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
  }
  return ''
}

/**
 * 解析接口错误响应体。
 * 文案优先级：已翻译的 code → detail → fallback → 通用「请求失败」。
 */
export function parseApiError(status: number, body: unknown, fallback?: string): ApiError {
  const data = (body && typeof body === 'object' ? body : {}) as {
    detail?: unknown
    code?: unknown
    params?: unknown
  }
  const code = typeof data.code === 'string' ? data.code : undefined
  const params =
    data.params && typeof data.params === 'object' ? (data.params as ErrorParams) : undefined
  const table = messages[getActiveLocale()].errors as Record<string, string>
  const template = code ? table[code] : undefined
  const message =
    (template ? interpolate(template, toTemplateVars(params || {})) : '') ||
    detailText(data.detail) ||
    fallback ||
    apiErrorText('requestFailed')
  if (isInsufficientBalanceCode(code)) markBillingMessage(message)
  return new ApiError(message, status, code, params)
}

/** 解析并抛出接口错误；402 / 余额不足时弹出充值引导 */
export function throwApiError(status: number, body: unknown, fallback?: string): never {
  const error = parseApiError(status, body, fallback)
  notifyBillingErrorIfNeeded(status, error.message)
  throw error
}
