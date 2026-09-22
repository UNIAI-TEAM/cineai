import type { MediaModelOption } from '../../api'
import { modelProviderLabel } from '../../lib/mediaModelChoice'

type MediaModelGridProps = {
  title: string
  hint: string
  emptyText: string
  recommendedLabel: string
  autoLabel: string
  autoDesc: string
  models: MediaModelOption[]
  value: string
  onChange: (id: string) => void
}

/** Lưới chọn model ảnh/video ở trang phong cách video kiến thức: ô "Tự động" (rỗng) + các model; catalog rỗng thì hiện lời nhắc */
export default function MediaModelGrid({
  title,
  hint,
  emptyText,
  recommendedLabel,
  autoLabel,
  autoDesc,
  models,
  value,
  onChange,
}: MediaModelGridProps) {
  return (
    <div className="pf-style-block">
      <h3>{title}</h3>
      <p className="pf-muted" style={{ fontSize: '0.78rem', margin: '0 0 0.65rem' }}>
        {hint}
      </p>
      {models.length === 0 ? (
        <p className="pf-muted" role="status" style={{ fontSize: '0.85rem', margin: 0 }}>
          {emptyText}
        </p>
      ) : (
        <div className="pf-model-grid">
          <button
            type="button"
            className={!value ? 'pf-model-opt selected' : 'pf-model-opt'}
            onClick={() => onChange('')}
          >
            <div className="pf-model-opt-title">
              <span>{autoLabel}</span>
            </div>
            <div className="pf-model-opt-desc">{autoDesc}</div>
          </button>
          {models.map((m) => (
            <button
              key={m.id}
              type="button"
              className={value === m.id ? 'pf-model-opt selected' : 'pf-model-opt'}
              onClick={() => onChange(m.id)}
            >
              <div className="pf-model-opt-title">
                <span>{m.label}</span>
                {m.recommended ? <span className="pf-model-badge">{recommendedLabel}</span> : null}
              </div>
              <div className="pf-model-opt-desc">{modelProviderLabel(m)}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
