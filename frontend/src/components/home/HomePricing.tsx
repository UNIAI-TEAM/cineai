import { useEffect, useState } from 'react'
import { Check, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, type BillingSku } from '../../api'
import { useCurrency, type Currency } from '../../currency'
import { useI18n } from '../../i18n'
import { isCurrency } from '../../lib/money'
import { homeImage, type HomeCopy } from './homeContent'

/** Pick three distinct top-up tiers for the homepage: first, featured-or-middle, and last. */
function pickSkus(skus: BillingSku[]) {
  const middle = skus.find((sku) => sku.recommended) ?? skus[Math.floor(skus.length / 2)]
  const seen = new Set<string>()
  return [skus[0], middle, skus[skus.length - 1]].filter((sku): sku is BillingSku => {
    if (!sku || seen.has(sku.id)) return false
    seen.add(sku.id)
    return true
  })
}

/** Homepage pricing preview driven by real billing SKUs, with fallback states linking to the full pricing page. */
export default function HomePricing({ copy }: { copy: HomeCopy }) {
  const { m } = useI18n()
  const { formatAmount } = useCurrency()
  const [skus, setSkus] = useState<BillingSku[]>([])
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [topupEnabled, setTopupEnabled] = useState(true)
  const [skuCurrency, setSkuCurrency] = useState<Currency>('VND')

  useEffect(() => {
    let cancelled = false
    api
      .billingSkus()
      .then((res) => {
        if (cancelled) return
        if (isCurrency(res.currency)) setSkuCurrency(res.currency)
        setTopupEnabled(res.topup_enabled !== false)
        const next = pickSkus(res.skus || [])
        setSkus(next)
        setStatus(next.length ? 'ready' : 'error')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const message =
    status === 'loading' ? copy.pricingLoading : topupEnabled ? copy.pricingError : m.pricing.topupClosed

  return (
    <section id="pricing" className="home-pricing home-section">
      <div className="home-pricing-heading">
        <p className="home-kicker">{copy.pricingKicker}</p>
        <h2>
          {copy.pricingHeading.map((line) => (
            <span key={line}>{line}</span>
          ))}
        </h2>
        <p className="home-subtitle">{copy.pricingLead}</p>
        {!topupEnabled ? <p className="home-pricing-note">{m.pricing.topupClosed}</p> : null}
        {status !== 'ready' ? (
          <div className="home-pricing-state" aria-live="polite">
            <p>{message}</p>
            <Link to="/pricing" className="home-button home-button-outline">
              {copy.pricingLink}
            </Link>
          </div>
        ) : null}
      </div>

      <div className="home-pricing-cards">
        {skus.map((sku) => {
          const label = m.pricing.skus[sku.id as keyof typeof m.pricing.skus] || sku.name
          const hint = m.pricing.skuHints[sku.id as keyof typeof m.pricing.skuHints] || m.pricing.foreverHint
          const bonusPct = Number(sku.bonus_pct) || 0
          const bonusAmount = formatAmount((sku.amount_vnd * bonusPct) / 100, skuCurrency)
          return (
            <article key={sku.id} className={`home-price-card${sku.recommended ? ' is-featured' : ''}`}>
              {sku.recommended ? (
                <p className="home-price-badge">
                  <Star size={14} strokeWidth={2.2} />
                  {copy.recommended}
                </p>
              ) : null}
              <h3 className="home-price-name">{label}</h3>
              <p className="home-price-hint">{hint}</p>
              <div className="home-price-amount">
                <strong className="home-price">{formatAmount(sku.amount_vnd, skuCurrency)}</strong>
                <span>{copy.credit}</span>
              </div>
              <ul className="home-price-features">
                {copy.pricingFeatures.map((feature) => (
                  <li key={feature}>
                    <Check size={16} strokeWidth={2.4} />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>
              {bonusPct > 0 ? (
                <p className="home-price-bonus">
                  <span>{copy.bonus}</span>
                  <strong>{bonusAmount}</strong>
                </p>
              ) : (
                <p className="home-price-bonus is-empty">{m.pricing.foreverHint}</p>
              )}
              <Link
                to={`/pricing#sku-${sku.id}`}
                className={sku.recommended ? 'home-button' : 'home-button home-button-outline'}
              >
                {copy.pricingLink}
              </Link>
            </article>
          )
        })}
      </div>

      <div className="home-pricing-art">
        <img src={homeImage('sunset')} alt="" loading="lazy" />
        <p className="home-handwriting">
          Create today.
          <br />
          Build tomorrow.
        </p>
      </div>
    </section>
  )
}
