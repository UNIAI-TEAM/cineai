/** 浏览器语言检测、本地覆盖与 html lang 同步 */

export type Locale = 'zh' | 'en' | 'vi'

export const LOCALES: Locale[] = ['zh', 'en', 'vi']

/** 界面可选语言：中文暂时关闭（文案保留，恢复时把 'zh' 加回即可） */
export const ENABLED_LOCALES: Locale[] = ['vi', 'en']

/** 未指定或不可用时的默认语言 */
export const DEFAULT_LOCALE: Locale = 'vi'

export const LOCALE_STORAGE_KEY = 'printfilm.locale'

export const LOCALE_HTML: Record<Locale, string> = {
  zh: 'zh-CN',
  en: 'en',
  vi: 'vi',
}

export const LOCALE_DATE: Record<Locale, string> = {
  zh: 'zh-CN',
  en: 'en-US',
  vi: 'vi-VN',
}

// 当前生效语言（供非 React 工具函数读取）
let activeLocale: Locale = DEFAULT_LOCALE

// 是否为已支持的语言代码
export function isLocale(value: unknown): value is Locale {
  return value === 'zh' || value === 'en' || value === 'vi'
}

// 是否为当前开放可选的语言
export function isLocaleEnabled(value: unknown): value is Locale {
  return isLocale(value) && ENABLED_LOCALES.includes(value)
}

// 从 Accept-Language / navigator 映射到已开放语言：vi* → vi，其余（含 zh*）→ en
export function localeFromBrowser(lang?: string): Locale {
  const raw = (lang || '').trim().toLowerCase()
  if (raw.startsWith('vi')) return 'vi'
  if (raw.startsWith('zh') && isLocaleEnabled('zh')) return 'zh'
  return 'en'
}

// 读取用户手动选择；无记录则返回 null（跟随浏览器）
export function readStoredLocale(): Locale | null {
  try {
    const raw = localStorage.getItem(LOCALE_STORAGE_KEY)
    // 旧的 zh 偏好在中文关闭期间忽略，改跟浏览器
    return isLocaleEnabled(raw) ? raw : null
  } catch {
    return null
  }
}

// 首次进入：有手动选择用手动，否则跟浏览器
export function detectLocale(): Locale {
  const stored = typeof window === 'undefined' ? null : readStoredLocale()
  if (stored) return stored
  if (typeof navigator === 'undefined') return DEFAULT_LOCALE
  const hint = navigator.language || navigator.languages?.[0] || DEFAULT_LOCALE
  return localeFromBrowser(hint)
}

export function getActiveLocale(): Locale {
  return activeLocale
}

// 应用语言：写 html lang；persist 时才写入 localStorage
export function applyLocale(locale: Locale, persist: boolean): void {
  activeLocale = locale
  if (persist) {
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    } catch {
      /* ignore quota / private mode */
    }
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = LOCALE_HTML[locale]
  }
}

// 日期时间按当前语言格式化
export function formatDateTime(value?: string | Date | null, locale: Locale = activeLocale): string {
  if (!value) return '—'
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(LOCALE_DATE[locale], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
