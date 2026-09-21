import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import type { UsageSummary, Wallet } from '../../api'
import { useCurrency } from '../../currency'
import { formatDateTime, useI18n } from '../../i18n'

type Props = {
  wallet: Wallet | null
  usage: UsageSummary | null
  loggedIn: boolean
  updatedAt: Date | null
  onHistory: () => void
}

/** 定价页深色余额卡片：余额、本月消耗、冻结、充值记录 */
export default function PricingWalletCard({ wallet, usage, loggedIn, updatedAt, onHistory }: Props) {
  const { t, locale } = useI18n()
  const { format } = useCurrency()
  const [balanceVisible, setBalanceVisible] = useState(true)

  // 一律从「分」换算展示，不再读取 *_yuan
  const balanceFen = wallet?.balance_fen ?? usage?.balance_fen ?? 0
  const frozenFen = wallet?.frozen_fen ?? usage?.frozen_fen ?? 0
  const monthChargeFen = usage?.charge_fen ?? 0

  return (
    <aside className="pf-pricing-wallet-dark">
      <div className="pf-pricing-wallet-dark-head">
        <span className="pf-pricing-wallet-dark-label">{t('pricing.walletBalance')}</span>
        <div className="pf-pricing-wallet-dark-actions">
          <button
            type="button"
            className="pf-pricing-wallet-eye"
            aria-label={balanceVisible ? t('pricing.hideBalance') : t('pricing.showBalance')}
            onClick={() => setBalanceVisible((v) => !v)}
          >
            {balanceVisible ? <Eye size={16} /> : <EyeOff size={16} />}
          </button>
          <button
            type="button"
            className="pf-pricing-wallet-history"
            disabled={!loggedIn}
            title={loggedIn ? t('billing.wallet.viewHistory') : t('pricing.loginFirst')}
            onClick={onHistory}
          >
            {t('pricing.history')}
          </button>
        </div>
      </div>

      <strong className="pf-pricing-wallet-dark-balance">
        {balanceVisible ? format(balanceFen) : '****'}
      </strong>

      <dl className="pf-pricing-wallet-dark-meta">
        <div>
          <dt>{t('pricing.monthCharge')}</dt>
          <dd>{loggedIn ? format(monthChargeFen) : '—'}</dd>
        </div>
        <div>
          <dt>{t('billing.wallet.frozenAmount')}</dt>
          <dd>{loggedIn ? format(frozenFen) : '—'}</dd>
        </div>
      </dl>

      <p className="pf-pricing-wallet-dark-updated">{t('pricing.updatedAt', { time: formatDateTime(updatedAt, locale) })}</p>
    </aside>
  )
}
