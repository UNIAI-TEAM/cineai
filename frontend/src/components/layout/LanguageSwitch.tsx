import { ENABLED_LOCALES, type Locale } from '../../i18n/detect'
import { useI18n } from '../../i18n'

// 各语言在顶栏上的短标签对应的文案 key
const LANG_LABEL_KEY: Record<Locale, string> = {
  zh: 'nav.langZh',
  en: 'nav.langEn',
  vi: 'nav.langVi',
}

/** 顶栏语言切换（只列 ENABLED_LOCALES，中文暂不开放）：点击后写入偏好，覆盖浏览器语言 */
export default function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n()

  return (
    <div className="pf-nav-lang" role="group" aria-label={t('nav.language')}>
      {ENABLED_LOCALES.map((code: Locale) => (
        <button
          key={code}
          type="button"
          className={locale === code ? 'is-active' : undefined}
          aria-pressed={locale === code}
          onClick={() => setLocale(code)}
        >
          {t(LANG_LABEL_KEY[code])}
        </button>
      ))}
    </div>
  )
}
