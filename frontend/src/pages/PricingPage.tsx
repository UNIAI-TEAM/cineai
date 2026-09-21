import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Check, CreditCard, Infinity, Landmark, ShieldCheck, Zap } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import CurrencySwitch from '../components/billing/CurrencySwitch'
import PaymentModal, { type PayCheckout } from '../components/billing/PaymentModal'
import PricingWalletCard from '../components/billing/PricingWalletCard'
import TopupHistoryModal from '../components/billing/TopupHistoryModal'
import { api, type BillingSku, type UsageSummary, type Wallet } from '../api'
import { useCurrency } from '../currency'
import { isCurrency } from '../lib/money'
import { useI18n } from '../i18n'

const HERO_FEATURE_KEYS = ['featInstant', 'featSafe', 'featForever'] as const

/** 定价与充值页：选择 VND 档位 → 银行转账 → 管理员确认到账 */
export default function PricingPage() {
  const nav = useNavigate()
  const { t, m } = useI18n()
  const { currency, format, formatAmount } = useCurrency()
  const [params] = useSearchParams()
  /*
   * wallet / usage / updatedAt 余额卡数据
   * skus 充值档位；skuCurrency 档位金额币种；topupEnabled 收款账户是否已配置
   * busy 下单中的档位 id；error / hint 顶部提示
   * checkout 当前转账单（弹窗）；historyOpen 充值记录弹窗
   */
  const [wallet, setWallet] = useState<Wallet | null>(null)
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [skus, setSkus] = useState<BillingSku[]>([])
  const [skuCurrency, setSkuCurrency] = useState<'VND' | 'USD'>('VND')
  const [topupEnabled, setTopupEnabled] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  const [checkout, setCheckout] = useState<PayCheckout | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const loggedIn = Boolean(localStorage.getItem('token'))

  async function refresh() {
    if (!loggedIn) {
      setWallet(null)
      setUsage(null)
      setUpdatedAt(null)
      return
    }
    try {
      const [w, u] = await Promise.all([api.wallet(), api.usageSummary()])
      setWallet(w)
      setUsage(u)
      setUpdatedAt(new Date())
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    api
      .billingSkus()
      .then((r) => {
        setSkus(r.skus || [])
        setTopupEnabled(r.topup_enabled !== false)
        if (isCurrency(r.currency)) setSkuCurrency(r.currency)
      })
      .catch(() => setSkus([]))
    refresh()
    if (params.get('paid') === '1') {
      setHint(t('pricing.paidHint'))
      const timerId = window.setInterval(() => refresh(), 2500)
      return () => window.clearInterval(timerId)
    }
  }, [])

  /** 下单：未登录先跳登录；成功后打开转账信息弹窗 */
  async function pay(sku: BillingSku) {
    if (!loggedIn) {
      nav(`/auth?next=${encodeURIComponent(`/pricing#sku-${sku.id}`)}`)
      return
    }
    setBusy(sku.id)
    setError('')
    try {
      const order = await api.createBillingOrder(sku.id)
      const label = m.pricing.skus[sku.id as keyof typeof m.pricing.skus] || sku.name
      setCheckout({ ...order, sku_id: order.sku_id || sku.id, sku_name: label, bonus_pct: Number(sku.bonus_pct) || 0 })
    } catch (e) {
      setError(e instanceof Error ? e.message : t('pricing.orderFailed'))
    } finally {
      setBusy(null)
    }
  }

  async function onPaid() {
    setHint(t('pricing.paidOk'))
    await refresh()
  }

  return (
    <AppShell active="pricing" hideFooter wide>
      <div className="pf-pricing-page">
        <section className="pf-pricing-hero-band">
          <div className="pf-pricing-hero-inner">
            <div className="pf-pricing-hero-copy">
              <h1>{t('pricing.title')}</h1>
              <p>{t('pricing.lead')}</p>
              <ul className="pf-pricing-hero-features">
                {HERO_FEATURE_KEYS.map((key, i) => {
                  const icons = [Zap, ShieldCheck, Infinity] as const
                  const Icon = icons[i]
                  return (
                    <li key={key}>
                      <span className="pf-pricing-hero-feature-icon" aria-hidden>
                        <Icon size={15} strokeWidth={2.2} />
                      </span>
                      {t(`pricing.${key}`)}
                    </li>
                  )
                })}
              </ul>
              {!loggedIn ? (
                <p className="pf-pricing-guest-tip">
                  {t('pricing.guestPrefix')}
                  <Link to="/auth?next=%2Fpricing">{t('pricing.guestLogin')}</Link>
                  {t('pricing.guestSuffix')}
                </p>
              ) : null}
            </div>
            <PricingWalletCard
              wallet={wallet}
              usage={usage}
              loggedIn={loggedIn}
              updatedAt={updatedAt}
              onHistory={() => setHistoryOpen(true)}
            />
          </div>
        </section>

        <div className="pf-pricing-body">
          {hint ? <p className="pf-pricing-hint">{hint}</p> : null}
          {error ? <p className="pf-error pf-pricing-error">{error}</p> : null}

          <section className="pf-pricing-skus" id="pricing-skus">
            <header className="pf-pricing-section-head is-row">
              <h2>{t('pricing.chooseAmount')}</h2>
              <div className="pf-pricing-currency">
                <span>{t('pricing.currency')}</span>
                <CurrencySwitch />
              </div>
            </header>

            <p className="pf-pricing-transfer-line">
              <Landmark size={16} aria-hidden />
              <span>
                <strong>{t('pricing.bankTransfer')}</strong> · {t('pricing.bankTransferHint')}
              </span>
            </p>

            {!topupEnabled ? <p className="pf-pricing-topup-notice">{t('pricing.topupClosed')}</p> : null}

            <div className="pf-pricing-sku-grid">
              {skus.map((sku) => {
                const bonusFen = Math.max(0, sku.credit_fen - sku.amount_fen)
                const bonusPct = Number(sku.bonus_pct) || 0
                // 展示货币与定价货币一致时按面额精确显示，避免「分」取整带来的 100.008 ₫ 这类尾差
                const sameCurrency = currency === skuCurrency
                const creditText = sameCurrency
                  ? formatAmount((sku.amount_vnd * (100 + bonusPct)) / 100, skuCurrency)
                  : format(sku.credit_fen)
                const bonusText = sameCurrency
                  ? formatAmount((sku.amount_vnd * bonusPct) / 100, skuCurrency)
                  : format(bonusFen)
                const recommended = Boolean(sku.recommended)
                const label = m.pricing.skus[sku.id as keyof typeof m.pricing.skus] || sku.name
                const tierHint =
                  m.pricing.skuHints[sku.id as keyof typeof m.pricing.skuHints] || t('pricing.foreverHint')
                return (
                  <article
                    key={sku.id}
                    id={`sku-${sku.id}`}
                    className={`pf-pricing-sku-card${recommended ? ' is-recommended' : ''}`}
                  >
                    {recommended ? <span className="pf-pricing-rec-badge">{t('pricing.recommended')}</span> : null}
                    <p className="pf-pricing-sku-tier">{label}</p>
                    <p className="pf-pricing-sku-hint">{tierHint}</p>
                    <div className="pf-pricing-sku-price">
                      <strong>{formatAmount(sku.amount_vnd, skuCurrency)}</strong>
                      {bonusPct > 0 ? (
                        <span className="pf-pricing-sku-pct">{t('pricing.bonusPct', { pct: bonusPct })}</span>
                      ) : null}
                    </div>
                    <p className="pf-pricing-sku-credit">
                      {t('pricing.credit')} <em>{creditText}</em>
                    </p>
                    {bonusFen > 0 ? (
                      <p className="pf-pricing-sku-bonus">{t('pricing.bonus', { amount: bonusText })}</p>
                    ) : (
                      <p className="pf-pricing-sku-bonus is-empty">&nbsp;</p>
                    )}
                    <button
                      type="button"
                      className={`pf-pricing-sku-cta${recommended ? ' is-primary' : ''}`}
                      disabled={Boolean(busy) || !topupEnabled}
                      onClick={() => pay(sku)}
                    >
                      {busy === sku.id ? t('pricing.ordering') : t('pricing.payNow')}
                    </button>
                  </article>
                )
              })}
            </div>
          </section>

          <section className="pf-pricing-info">
            <article className="pf-pricing-info-card">
              <div className="pf-pricing-info-visual is-billing" aria-hidden>
                <CreditCard size={28} strokeWidth={1.6} />
              </div>
              <div>
                <h3>{t('pricing.billingTitle')}</h3>
                <ul>
                  <li>{t('pricing.billing1')}</li>
                  <li>{t('pricing.billing2')}</li>
                  <li>{t('pricing.billing3')}</li>
                </ul>
              </div>
            </article>
            <article className="pf-pricing-info-card">
              <div className="pf-pricing-info-visual is-value" aria-hidden>
                <Check size={28} strokeWidth={2.5} />
              </div>
              <div>
                <h3>{t('pricing.whyTitle')}</h3>
                <ul className="pf-pricing-checks">
                  <li>{t('pricing.why1')}</li>
                  <li>{t('pricing.why2')}</li>
                  <li>{t('pricing.why3')}</li>
                </ul>
              </div>
            </article>
          </section>

          <footer className="pf-pricing-site-foot">
            <p className="pf-pricing-site-brand">
              <Link to="/">PRINTFILM</Link>
              <span> · {t('pricing.footBrand')}</span>
            </p>
            <nav className="pf-pricing-site-links" aria-label={t('footer.links')}>
              <Link to="/terms">{t('footer.terms')}</Link>
              <Link to="/privacy">{t('footer.privacy')}</Link>
              <Link to="/contact">{t('footer.contact')}</Link>
            </nav>
            <p className="pf-pricing-site-copy">© {new Date().getFullYear()} PRINTFILM. All rights reserved.</p>
          </footer>
        </div>
      </div>

      <PaymentModal
        open={Boolean(checkout)}
        checkout={checkout}
        onClose={() => setCheckout(null)}
        onPaid={() => void onPaid()}
      />
      <TopupHistoryModal open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </AppShell>
  )
}
