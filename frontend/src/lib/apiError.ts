import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { notifyBillingErrorIfNeeded } from './billingError'

type CommonKey = keyof (typeof messages)['zh']['common']

/** 按当前界面语言取通用报错兜底文案（供非 React 的 api 层使用） */
export function apiErrorText(key: CommonKey): string {
  return messages[getActiveLocale()].common[key]
}

/** 解析 FastAPI detail 并抛出；402 / 余额不足时弹出充值引导 */
export function throwApiError(status: number, detail: unknown, fallback?: string): never {
  const fallbackText = fallback || apiErrorText('requestFailed')
  const message =
    typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
        : fallbackText
  const finalMessage = message || fallbackText
  notifyBillingErrorIfNeeded(status, finalMessage)
  throw new Error(finalMessage)
}
