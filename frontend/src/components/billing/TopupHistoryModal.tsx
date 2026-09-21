import { useEffect, useState } from 'react'
import Modal from '../ui/Modal'
import { api, type BillingOrder } from '../../api'
import { useCurrency } from '../../currency'
import { isCurrency } from '../../lib/money'
import { formatDateTime, useI18n } from '../../i18n'

type Props = {
  open: boolean
  onClose: () => void
}

/** 充值记录弹窗：列出近期转账单、应付金额、到账额度与管理员确认状态（过期待确认单由后台自动关闭） */
export default function TopupHistoryModal({ open, onClose }: Props) {
  const { t, m, locale } = useI18n()
  const { format, formatAmount } = useCurrency()
  // 套餐名与订单状态文案：复用定价页 SKU 名，状态按后端 status 码映射
  const skuLabels = m.pricing.skus as Record<string, string>
  const statusLabels = m.billing.history.orderStatus as Record<string, string>
  /*
   * orders 订单列表
   * loading 加载中
   * error 错误信息
   */
  const [orders, setOrders] = useState<BillingOrder[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    setError('')
    api
      .listBillingOrders(50)
      .then((r) => {
        if (!cancelled) setOrders(r.orders || [])
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t('common.loadFailed'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, t])

  return (
    <Modal open={open} onClose={onClose} title={t('pricing.history')} size="lg" className="pf-topup-history-modal">
      {loading ? <p className="pf-muted">{t('common.loading')}</p> : null}
      {error ? <p className="pf-error">{error}</p> : null}
      {!loading && !error && orders.length === 0 ? (
        <p className="pf-muted">{t('billing.history.empty')}</p>
      ) : null}
      {!loading && orders.length > 0 ? (
        <ul className="pf-topup-list">
          {orders.map((o) => (
            <li key={o.out_trade_no} className="pf-topup-item">
              <div className="pf-topup-main">
                <strong>{skuLabels[o.sku_id] || o.sku_name}</strong>
                <span className="pf-muted">{formatDateTime(o.paid_at || o.created_at, locale)}</span>
              </div>
              <div className="pf-topup-meta">
                <em>
                  {o.pay_amount != null && isCurrency(o.pay_currency)
                    ? formatAmount(o.pay_amount, o.pay_currency)
                    : format(o.amount_fen)}
                </em>
                <span className="pf-muted">{t('billing.creditAmount', { amount: format(o.credit_fen) })}</span>
                <span className={`pf-topup-status is-${o.status}`}>
                  {statusLabels[o.status] || o.status}
                </span>
                {o.note ? <span className="pf-muted pf-topup-note">{o.note}</span> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Modal>
  )
}
