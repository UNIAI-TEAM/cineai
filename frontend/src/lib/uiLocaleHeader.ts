/** 界面语言请求头：后端据此决定 AI 生成内容的输出语言（backend/app/services/content_lang.py） */
import { getActiveLocale } from '../i18n/detect'

export const UI_LOCALE_HEADER = 'X-UI-Locale'

// 每个 API 请求都带上当前界面语言
export function uiLocaleHeaders(): Record<string, string> {
  return { [UI_LOCALE_HEADER]: getActiveLocale() }
}
