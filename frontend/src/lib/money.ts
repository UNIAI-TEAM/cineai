/** 金额展示：钱包内部以「分」记账，界面按展示货币（VND / USD）换算并格式化 */

export type Currency = 'VND' | 'USD'

/** 1 分折合各货币的数值，由 /api/billing/currency 下发 */
export type PerFen = Record<Currency, number>

export const CURRENCIES: Currency[] = ['VND', 'USD']

/** 服务端未返回汇率时的保守默认值（1 CNY ≈ 3600 VND，1 USD ≈ 7 CNY） */
export const DEFAULT_PER_FEN: PerFen = { VND: 36, USD: 1 / 700 }

/** 是否为支持的货币代码 */
export function isCurrency(value: unknown): value is Currency {
  return value === 'VND' || value === 'USD'
}

/** 分 → 展示货币数值（未取整） */
export function fenToAmount(fen: number, currency: Currency, perFen: PerFen): number {
  const n = Number(fen) || 0
  const rate = perFen[currency] ?? DEFAULT_PER_FEN[currency]
  return n * rate
}

/**
 * 格式化已换算好的金额（如订单的 pay_amount）
 * VND：取整并按 vi-VN 分组，后缀 ₫（1.000.000 ₫）；USD：$ 前缀两位小数（$12.34）
 */
export function formatAmount(amount: number, currency: Currency): string {
  const n = Number(amount) || 0
  if (currency === 'USD') {
    const abs = Math.abs(n).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return `${n < 0 ? '-' : ''}$${abs}`
  }
  const rounded = Math.round(n)
  return `${rounded.toLocaleString('vi-VN', { maximumFractionDigits: 0 })} ₫`
}

/** 分 → 按货币格式化后的字符串 */
export function formatMoney(fen: number, currency: Currency, perFen: PerFen): string {
  return formatAmount(fenToAmount(fen, currency, perFen), currency)
}
