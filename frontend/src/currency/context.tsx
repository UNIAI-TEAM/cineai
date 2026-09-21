import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api'
import {
  CURRENCIES,
  DEFAULT_PER_FEN,
  formatAmount,
  formatMoney,
  isCurrency,
  type Currency,
  type PerFen,
} from '../lib/money'
import {
  applyCurrency,
  applyCurrencyRates,
  getActiveCurrencyOptions,
  getActivePerFen,
  readStoredCurrency,
} from './store'

type CurrencyValue = {
  /** 当前展示货币 */
  currency: Currency
  /** 手动切换（写入 localStorage） */
  setCurrency: (next: Currency) => void
  /** 服务端允许的货币 */
  options: Currency[]
  /** 1 分折合各货币 */
  perFen: PerFen
  /** 分 → 当前货币格式化字符串 */
  format: (fen: number) => string
  /** 已换算金额（如订单 pay_amount）→ 格式化字符串，默认用当前货币 */
  formatAmount: (amount: number, currency?: Currency) => string
  /** 服务端汇率是否已加载 */
  ready: boolean
}

const CurrencyContext = createContext<CurrencyValue | null>(null)

/** 全站展示货币：启动时拉取 /api/billing/currency，用户选择持久化到 localStorage */
export function CurrencyProvider({ children }: { children: ReactNode }) {
  /*
   * currency 当前货币（先用本地记录，否则等服务端默认）
   * options 可选货币
   * perFen 汇率
   * ready 汇率是否已加载
   */
  const [currency, setCurrencyState] = useState<Currency>(() => {
    const stored = readStoredCurrency()
    const next = stored ?? 'VND'
    applyCurrency(next, false)
    return next
  })
  const [options, setOptions] = useState<Currency[]>(() => getActiveCurrencyOptions())
  const [perFen, setPerFen] = useState<PerFen>(() => ({ ...DEFAULT_PER_FEN }))
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .billingCurrency()
      .then((res) => {
        if (cancelled) return
        applyCurrencyRates(res.per_fen || {}, res.options)
        setPerFen({ ...getActivePerFen() })
        setOptions(getActiveCurrencyOptions())
        // 无本地记录时采用服务端默认货币
        if (!readStoredCurrency() && isCurrency(res.default)) {
          applyCurrency(res.default, false)
          setCurrencyState(res.default)
        }
        setReady(true)
      })
      .catch(() => {
        /* 汇率拉取失败：沿用默认值，不阻塞页面 */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const setCurrency = useCallback((next: Currency) => {
    if (!CURRENCIES.includes(next)) return
    applyCurrency(next, true)
    setCurrencyState(next)
  }, [])

  const format = useCallback((fen: number) => formatMoney(fen, currency, perFen), [currency, perFen])
  const formatAmountFn = useCallback(
    (amount: number, code?: Currency) => formatAmount(amount, code ?? currency),
    [currency],
  )

  const value = useMemo<CurrencyValue>(
    () => ({ currency, setCurrency, options, perFen, format, formatAmount: formatAmountFn, ready }),
    [currency, setCurrency, options, perFen, format, formatAmountFn, ready],
  )

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
}

/** 读取展示货币上下文（须在 CurrencyProvider 内使用） */
export function useCurrency(): CurrencyValue {
  const ctx = useContext(CurrencyContext)
  if (!ctx) throw new Error('useCurrency must be used within CurrencyProvider')
  return ctx
}
