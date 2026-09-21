import { useCurrency } from '../../currency'
import { useI18n } from '../../i18n'

type Props = {
  /** 附加 class（如放在深色卡片上） */
  className?: string
}

/** VND / USD 展示货币切换：胶囊按钮组，样式同顶栏语言切换 */
export default function CurrencySwitch({ className }: Props) {
  const { currency, setCurrency, options } = useCurrency()
  const { t } = useI18n()

  return (
    <div
      className={`pf-currency-switch${className ? ` ${className}` : ''}`}
      role="group"
      aria-label={t('pricing.currency')}
    >
      {options.map((code) => (
        <button
          key={code}
          type="button"
          className={currency === code ? 'is-active' : undefined}
          aria-pressed={currency === code}
          onClick={() => setCurrency(code)}
        >
          {code}
        </button>
      ))}
    </div>
  )
}
