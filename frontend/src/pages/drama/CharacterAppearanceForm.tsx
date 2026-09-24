/** Form 8 trường ngoại hình nhân vật + nút AI tách trường; chỉ hiển thị/sửa, việc lưu do DramaAssetDetailModal làm */
import { APPEARANCE_KEYS, appearanceIsEmpty, type Appearance, type AppearanceKey } from '../../lib/dramaAppearance'
import { useI18n } from '../../i18n/context'

type Props = {
  value: Appearance
  onChange: (next: Appearance) => void
  onExtract: () => void
  extracting: boolean
  disabled: boolean
}

// Trường dài hiển thị bằng textarea 2 dòng
const MULTILINE: ReadonlySet<AppearanceKey> = new Set(['outfit', 'style_note'])

// Render form ngoại hình
export function CharacterAppearanceForm({ value, onChange, onExtract, extracting, disabled }: Props) {
  const { t } = useI18n()
  const empty = appearanceIsEmpty(value)
  return (
    <section className="drama-appearance-form" aria-label={t('dramaAssets.appearance.title')}>
      <header className="drama-appearance-head">
        <strong>{t('dramaAssets.appearance.title')}</strong>
        <button type="button" className="pf-btn pf-btn-sm" disabled={disabled || extracting} onClick={onExtract}>
          {extracting ? t('dramaAssets.appearance.extracting') : t('dramaAssets.appearance.extract')}
        </button>
      </header>
      {empty ? <p className="drama-muted">{t('dramaAssets.appearance.emptyHint')}</p> : null}
      <div className="drama-appearance-grid">
        {APPEARANCE_KEYS.map((key) => (
          <label key={key} className={`drama-field${MULTILINE.has(key) ? ' drama-appearance-wide' : ''}`}>
            <span>{t(`dramaAssets.appearance.fields.${key}`)}</span>
            {MULTILINE.has(key) ? (
              <textarea
                rows={2}
                value={value[key]}
                disabled={disabled}
                onChange={(e) => onChange({ ...value, [key]: e.target.value })}
              />
            ) : (
              <input
                type="text"
                value={value[key]}
                disabled={disabled}
                onChange={(e) => onChange({ ...value, [key]: e.target.value })}
              />
            )}
          </label>
        ))}
      </div>
    </section>
  )
}
