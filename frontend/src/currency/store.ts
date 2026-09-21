/** 展示货币的模块级状态：供非 React 工具函数读取（类似 i18n/detect 的 getActiveLocale） */
import {
  CURRENCIES,
  DEFAULT_PER_FEN,
  formatMoney,
  isCurrency,
  type Currency,
  type PerFen,
} from '../lib/money'

export const CURRENCY_STORAGE_KEY = 'printfilm.currency'

// 当前生效货币 / 汇率 / 可选项
let activeCurrency: Currency = 'VND'
let activePerFen: PerFen = { ...DEFAULT_PER_FEN }
let activeOptions: Currency[] = [...CURRENCIES]

/** 当前展示货币 */
export function getActiveCurrency(): Currency {
  return activeCurrency
}

/** 当前汇率表（1 分折合各货币） */
export function getActivePerFen(): PerFen {
  return activePerFen
}

/** 当前可选货币 */
export function getActiveCurrencyOptions(): Currency[] {
  return activeOptions
}

/** 读取用户手动选择的货币；无记录或非法返回 null */
export function readStoredCurrency(): Currency | null {
  try {
    const raw = localStorage.getItem(CURRENCY_STORAGE_KEY)
    return isCurrency(raw) ? raw : null
  } catch {
    return null
  }
}

/** 应用展示货币；persist 时写入 localStorage */
export function applyCurrency(currency: Currency, persist: boolean): void {
  activeCurrency = currency
  if (!persist) return
  try {
    localStorage.setItem(CURRENCY_STORAGE_KEY, currency)
  } catch {
    /* 私密模式 / 配额不足时忽略 */
  }
}

/** 应用服务端汇率与可选货币（缺项回落默认值） */
export function applyCurrencyRates(perFen: Partial<Record<string, number>>, options?: string[]): void {
  const next: PerFen = { ...DEFAULT_PER_FEN }
  for (const code of CURRENCIES) {
    const v = Number(perFen?.[code])
    if (Number.isFinite(v) && v > 0) next[code] = v
  }
  activePerFen = next
  const opts = (options || []).filter(isCurrency)
  activeOptions = opts.length ? opts : [...CURRENCIES]
}

/** 按当前展示货币格式化分（非 React 场景使用） */
export function formatFenActive(fen: number): string {
  return formatMoney(fen, activeCurrency, activePerFen)
}
