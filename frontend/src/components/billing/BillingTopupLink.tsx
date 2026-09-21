import { Link } from 'react-router-dom'
import { useI18n } from '../../i18n'
import { PRICING_PATH } from '../../lib/billingError'

type Props = {
  className?: string
  children?: string
}

/** 内联「去充值」快速跳转 */
export default function BillingTopupLink({ className = 'pf-link pf-billing-topup-link', children }: Props) {
  const { t } = useI18n()
  return (
    <Link to={PRICING_PATH} className={className}>
      {children ?? t('billing.topupLink')}
    </Link>
  )
}
