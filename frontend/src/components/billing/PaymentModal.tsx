import { useEffect, useEffectEvent, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import Modal from '../ui/Modal'
import { api, type BillingCheckout } from '../../api'
import { useCurrency } from '../../currency'
import { isCurrency } from '../../lib/money'
import { useI18n } from '../../i18n'

/** 转账单 + 下单时的赠送比例（用于按面额精确展示到账金额） */
export type PayCheckout = BillingCheckout & { bonus_pct?: number }

type Props = {
  open: boolean
  checkout: PayCheckout | null
  onClose: () => void
  onPaid: () => void
}

/** 订单状态轮询间隔（毫秒） */
const POLL_MS = 10_000

/** 剩余时间：≥1 小时显示「Xh Ym」，否则 mm:ss */
function formatRemain(sec: number) {
  if (sec >= 3600) {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    return `${h}h ${String(m).padStart(2, '0')}m`
  }
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** 可复制的一行收款信息 */
function CopyRow({
  label,
  value,
  copied,
  onCopy,
  highlight,
  copyLabel,
  copiedLabel,
}: {
  label: string
  value: string
  copied: boolean
  onCopy: () => void
  highlight?: boolean
  copyLabel: string
  copiedLabel: string
}) {
  return (
    <div className={`pf-pay-bank-row${highlight ? ' is-highlight' : ''}`}>
      <span className="pf-pay-bank-label">{label}</span>
      <code className="pf-pay-bank-value">{value || '—'}</code>
      <button
        type="button"
        className="pf-pay-bank-copy"
        onClick={onCopy}
        disabled={!value}
        aria-label={copied ? copiedLabel : `${copyLabel} ${label}`}
      >
        {copied ? <Check size={14} strokeWidth={2.2} aria-hidden /> : <Copy size={14} strokeWidth={2} aria-hidden />}
        <span>{copied ? copiedLabel : copyLabel}</span>
      </button>
    </div>
  )
}

/** 银行转账弹窗：展示收款账户 / 转账备注 / VietQR，并每 10 秒轮询订单直到管理员确认到账 */
export default function PaymentModal({ open, checkout, onClose, onPaid }: Props) {
  const { t, m } = useI18n()
  const { currency, format, formatAmount } = useCurrency()
  /*
   * remain 剩余秒数
   * status 订单状态（waiting 待确认 / paid 已到账 / closed 已关闭或过期）
   * copiedKey 刚复制的字段
   * qrFailed VietQR 图片加载失败
   * cancelling 取消订单请求中
   */
  const [remain, setRemain] = useState(0)
  const [status, setStatus] = useState<'waiting' | 'paid' | 'closed'>('waiting')
  const [copiedKey, setCopiedKey] = useState('')
  const [qrFailed, setQrFailed] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [error, setError] = useState('')

  const handlePaid = useEffectEvent(() => {
    onPaid()
  })

  useEffect(() => {
    if (!open || !checkout) return
    const expireSeconds = checkout.expire_seconds ?? 86_400
    const expiredAt = Date.now() + expireSeconds * 1000
    setRemain(expireSeconds)
    setStatus('waiting')
    setCopiedKey('')
    setQrFailed(false)
    setCancelling(false)
    setError('')

    // 倒计时：每秒刷新，归零视为订单失效
    const tick = window.setInterval(() => {
      const left = Math.max(0, Math.ceil((expiredAt - Date.now()) / 1000))
      setRemain(left)
      if (left <= 0) {
        setStatus('closed')
        window.clearInterval(tick)
      }
    }, 1000)

    // 轮询订单：管理员确认后 status=paid
    async function pollOnce() {
      try {
        const order = await api.getBillingOrder(checkout!.out_trade_no)
        if (order.status === 'paid') {
          setStatus('paid')
          window.clearInterval(poll)
          window.clearInterval(tick)
          handlePaid()
        } else if (order.status === 'closed') {
          setStatus('closed')
          window.clearInterval(poll)
          window.clearInterval(tick)
        }
      } catch {
        /* 瞬时网络错误忽略，下次继续 */
      }
    }
    const poll = window.setInterval(() => void pollOnce(), POLL_MS)

    return () => {
      window.clearInterval(tick)
      window.clearInterval(poll)
    }
  }, [open, checkout])

  /** 复制字段到剪贴板并短暂显示「已复制」 */
  async function copyValue(key: string, value: string) {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopiedKey(key)
      window.setTimeout(() => setCopiedKey((cur) => (cur === key ? '' : cur)), 1800)
    } catch {
      /* 剪贴板不可用时用户仍可手动选中复制 */
    }
  }

  /** 取消订单：调用关闭接口后退出弹窗 */
  async function cancelOrder() {
    if (!checkout) return
    setCancelling(true)
    setError('')
    try {
      if (status === 'waiting') await api.closeBillingOrder(checkout.out_trade_no)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : t('common.fail'))
    } finally {
      setCancelling(false)
    }
  }

  if (!checkout) return null

  const payCurrency = isCurrency(checkout.pay_currency) ? checkout.pay_currency : 'VND'
  // 展示货币与支付货币一致时按面额 ×(1+赠送) 精确显示，避免「分」取整尾差
  const creditText =
    currency === payCurrency && typeof checkout.bonus_pct === 'number'
      ? formatAmount((checkout.pay_amount * (100 + checkout.bonus_pct)) / 100, payCurrency)
      : format(checkout.credit_fen)
  const bank = checkout.bank || { name: '', account: '', holder: '' }
  const transferNote = checkout.transfer_note || checkout.out_trade_no
  const vietqr = (checkout.vietqr_url || '').trim()
  const copyLabel = t('billing.transfer.copy')
  const copiedLabel = t('billing.transfer.copied')

  return (
    <Modal open={open} onClose={onClose} className="pf-pay-modal" size="md">
      <div className="pf-pay-sheet">
        <header className="pf-pay-sheet-head">
          <div className="pf-pay-sheet-title">
            <strong>{t('billing.transfer.title')}</strong>
          </div>
          <button type="button" className="pf-pay-sheet-close" onClick={onClose} aria-label={t('common.close')}>
            ×
          </button>
        </header>

        <div className="pf-pay-sku-box">
          <strong>{(m.pricing.skus as Record<string, string>)[checkout.sku_id] || checkout.sku_name}</strong>
          <span>{t('billing.creditAmount', { amount: creditText })}</span>
        </div>

        <div className="pf-pay-amount">
          <span>{t('billing.transfer.amount')}</span>
          <em>{formatAmount(checkout.pay_amount, payCurrency)}</em>
        </div>

        {status === 'paid' ? (
          <div className="pf-pay-success">
            <span className="pf-pay-success-icon" aria-hidden>
              <Check size={26} strokeWidth={3} />
            </span>
            <p>{t('billing.transfer.paidWait')}</p>
          </div>
        ) : (
          <>
            {vietqr && !qrFailed ? (
              <div className="pf-pay-qr is-vietqr">
                <img
                  src={vietqr}
                  alt={t('billing.transfer.qrAlt')}
                  onError={() => setQrFailed(true)}
                />
                <p className="pf-pay-tip">{t('billing.transfer.scanHint')}</p>
              </div>
            ) : null}

            <div className="pf-pay-bank">
              <CopyRow
                label={t('billing.transfer.bankName')}
                value={bank.name}
                copied={copiedKey === 'name'}
                onCopy={() => void copyValue('name', bank.name)}
                copyLabel={copyLabel}
                copiedLabel={copiedLabel}
              />
              <CopyRow
                label={t('billing.transfer.account')}
                value={bank.account}
                copied={copiedKey === 'account'}
                onCopy={() => void copyValue('account', bank.account)}
                copyLabel={copyLabel}
                copiedLabel={copiedLabel}
              />
              <CopyRow
                label={t('billing.transfer.holder')}
                value={bank.holder}
                copied={copiedKey === 'holder'}
                onCopy={() => void copyValue('holder', bank.holder)}
                copyLabel={copyLabel}
                copiedLabel={copiedLabel}
              />
              <CopyRow
                label={t('billing.transfer.note')}
                value={transferNote}
                copied={copiedKey === 'note'}
                onCopy={() => void copyValue('note', transferNote)}
                highlight
                copyLabel={copyLabel}
                copiedLabel={copiedLabel}
              />
            </div>
            <p className="pf-pay-note-hint">{t('billing.transfer.noteHint')}</p>
          </>
        )}

        <div className="pf-pay-status-block">
          {status !== 'paid' ? (
            <p className={`pf-pay-expire${status === 'closed' ? ' is-expired' : ''}`}>
              <span className="pf-pay-clock" aria-hidden />
              {status === 'closed'
                ? t('billing.transfer.expired')
                : t('billing.transfer.expiresIn', { time: formatRemain(remain) })}
            </p>
          ) : null}
          <p className={`pf-pay-wait${status === 'paid' ? ' is-paid' : ''}`}>
            <span className="pf-pay-dot" aria-hidden />
            {status === 'paid'
              ? t('billing.transfer.paidWait')
              : status === 'closed'
                ? t('billing.transfer.closed')
                : t('billing.transfer.waiting')}
          </p>
          {status === 'waiting' ? <p className="pf-pay-confirm-hint">{t('billing.transfer.confirmHint')}</p> : null}
        </div>

        {error ? <p className="pf-error pf-pay-error">{error}</p> : null}

        <div className="pf-pay-actions">
          {status === 'paid' ? (
            <button type="button" className="pf-pay-btn primary pf-pay-btn-wide" onClick={onClose}>
              {t('billing.transfer.done')}
            </button>
          ) : (
            <>
              <button
                type="button"
                className="pf-pay-btn ghost"
                disabled={cancelling}
                onClick={() => void cancelOrder()}
              >
                {status === 'closed' ? t('common.close') : t('billing.transfer.cancel')}
              </button>
              <button
                type="button"
                className="pf-pay-btn primary"
                disabled={status === 'closed'}
                onClick={onClose}
              >
                {t('billing.transfer.transferred')}
              </button>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}
