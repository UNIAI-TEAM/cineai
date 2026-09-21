import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type UsageSummary } from '../../api'
import { useCurrency } from '../../currency'
import { useI18n } from '../../i18n'
import { LOCALE_DATE, type Locale } from '../../i18n/detect'

/** 格式化 token 数量，过大时用 k/M 缩写 */
function formatTokens(n: number, locale: Locale) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`
  if (n >= 10_000) return `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k`
  return n.toLocaleString(LOCALE_DATE[locale])
}

type MonthlyUsageCardProps = {
  /** compact 嵌入定价/设置卡片；panel 独立侧栏样式 */
  variant?: 'panel' | 'compact'
  /** 是否显示「去充值」按钮（定价页已可直接充值时可关闭） */
  showTopup?: boolean
}

/** 本月用量卡片：Token / 费用 / 余额，供定价页与个人中心复用 */
export default function MonthlyUsageCard({
  variant = 'panel',
  showTopup = true,
}: MonthlyUsageCardProps) {
  const { t, locale } = useI18n()
  const { format } = useCurrency()
  const [usage, setUsage] = useState<UsageSummary | null>(null)

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setUsage(null)
      return
    }
    api
      .usageSummary()
      .then(setUsage)
      .catch(() => setUsage(null))
  }, [])

  const tokenPct = Math.min(100, Math.log10((usage?.tokens || 0) + 1) * 18)
  const chargePct = Math.min(100, (usage?.charge_fen || 0) / 20)

  return (
    <div className={`pf-usage-card${variant === 'compact' ? ' is-compact' : ''}`}>
      <header className="pf-usage-card-head">
        <h3>{t('billing.usageCard.title')}</h3>
        <p>{t('billing.usageCard.subtitle')}</p>
      </header>

      <div className="pf-usage-row">
        <span>{t('billing.usageCard.tokens')}</span>
        <span className="pf-usage-val">{formatTokens(usage?.tokens ?? 0, locale)}</span>
      </div>
      <div className="pf-meter">
        <i style={{ width: `${tokenPct}%` }} />
      </div>

      <div className="pf-usage-row">
        <span>{t('billing.usageCard.monthCharge')}</span>
        <span className="pf-usage-val">{format(usage?.charge_fen ?? 0)}</span>
      </div>
      <div className="pf-meter">
        <i style={{ width: `${chargePct}%` }} />
      </div>

      <div className="pf-usage-row">
        <span>{t('pricing.walletBalance')}</span>
        <span className="pf-usage-val">{format(usage?.balance_fen ?? 0)}</span>
      </div>
      {(usage?.frozen_fen ?? 0) > 0 ? (
        <div className="pf-usage-row">
          <span>{t('billing.usageCard.frozen')}</span>
          <span className="pf-muted">{format(usage?.frozen_fen ?? 0)}</span>
        </div>
      ) : null}

      <div className="pf-usage-foot">
        <span className="pf-muted">{t('billing.usageCard.calls', { count: usage?.calls ?? 0 })}</span>
        {showTopup ? (
          <Link to="/pricing" className="pf-btn pf-btn-lime pf-btn-sm">
            {t('billing.topup')}
          </Link>
        ) : null}
      </div>
    </div>
  )
}
