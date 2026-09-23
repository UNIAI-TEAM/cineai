import { useCallback, useEffect, useRef } from 'react'
import { api } from '../../api'
import { useCurrency } from '../../currency'
import { useI18n } from '../../i18n'
import { dialog } from '../../lib/dialog'

type BillingAlertItem = {
  id: number
  kind: string
  title: string
  message: string
  milestone_fen: number
  milestone_yuan: number
  total_charged_fen?: number | null
  created_at?: string | null
}

/** 轮询待展示的用户额度告警并弹窗提示（标题 / 正文按界面语言拼，不用后端中文 title / message）。 */
export default function BillingAlertHost() {
  const { t } = useI18n()
  const { format } = useCurrency()
  // 在发起 pending 请求前就上锁，避免 focus/interval/StrictMode 并发重入
  const showingRef = useRef(false)

  const checkAlerts = useCallback(async () => {
    if (!localStorage.getItem('token') || showingRef.current) return
    showingRef.current = true
    try {
      const res = await api.billingAlertsPending()
      const items = (res.items ?? []) as BillingAlertItem[]
      if (!items.length) return
      for (const item of items) {
        const milestone = format(item.milestone_fen || 0)
        const message =
          typeof item.total_charged_fen === 'number'
            ? t('billing.alertMessage', { milestone, total: format(item.total_charged_fen) })
            : t('billing.alertMessageShort', { milestone })
        await dialog.alert({
          title: t('billing.alertTitle'),
          message,
          confirmText: t('dialog.ok'),
        })
        try {
          await api.billingAlertAck(item.id)
        } catch {
          // 已确认或并发 ack 导致 404 时忽略，避免反复重试刷屏
        }
      }
    } catch {
      // 未登录或网络异常时静默跳过
    } finally {
      showingRef.current = false
    }
  }, [t, format])

  useEffect(() => {
    void checkAlerts()
    const timer = window.setInterval(() => void checkAlerts(), 30_000)
    const onFocus = () => void checkAlerts()
    window.addEventListener('focus', onFocus)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [checkAlerts])

  return null
}
