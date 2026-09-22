import { formatFenActive } from '../currency/store'
import { getActiveLocale } from '../i18n/detect'
import { interpolate, type TVars } from '../i18n/lookup'
import { messages } from '../i18n/messages'
import { isInsufficientBalanceCode, markBillingMessage, notifyBillingErrorIfNeeded } from './billingError'

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

/** 队列等处只存文案时一并保存的错误码与状态，展示时据此还原分类 */
export type ErrorCodeFields = { errorCode?: string; errorStatus?: number }

/** 从异常中取错误码与状态；非 ApiError 返回空对象 */
export function errorCodeFields(err: unknown): ErrorCodeFields {
  return err instanceof ApiError ? { errorCode: err.code, errorStatus: err.status } : {}
}

/** 按当前界面语言取通用报错兜底文案（供非 React 的 api 层使用） */
export function apiErrorText(key: CommonKey): string {
  return messages[getActiveLocale()].common[key]
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

/**
 * 按错误码取当前界面语言的文案并插值；码未登记时返回空串。
 * 参数 code：后端错误码；params：后端 params（*_fen 按展示货币格式化）。
 */
export function translateErrorCode(code?: string | null, params?: unknown): string {
  if (!code) return ''
  const table = messages[getActiveLocale()].errors as Record<string, string>
  const template = table[code]
  if (!template) return ''
  const vars = params && typeof params === 'object' ? (params as ErrorParams) : {}
  return interpolate(template, toTemplateVars(vars))
}

/**
 * 落库错误（任务 error_message、项目 params 等）转展示文案：有已登记错误码则按界面语言翻译，否则原文。
 * 余额不足类会登记，供只拿到字符串的组件识别。
 */
export function localizeStoredError(
  message: string | null | undefined,
  code?: string | null,
  params?: unknown,
): string {
  const translated = translateErrorCode(code, params)
  if (translated && isInsufficientBalanceCode(code || undefined)) markBillingMessage(translated)
  return translated || message || ''
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
  const message =
    translateErrorCode(code, params) ||
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
