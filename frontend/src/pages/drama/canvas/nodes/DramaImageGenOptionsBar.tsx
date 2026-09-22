/** 漫剧生图：风格 / 模型 / 画幅选择条（内置风格，无手填） */
import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { BarChart3, ChevronDown, RectangleVertical, Smile } from 'lucide-react'
import {
  getImageStyleLabel,
  IMAGE_STYLE_OPTIONS,
  type ImageStyleId,
} from '../../../../lib/dramaImageStyles'
import { DramaImageStylePreviewImg } from '../../../../components/drama/DramaImageStylePreviewImg'
import {
  formatOutputSettingsLabel,
  GENERATION_ASPECT_RATIO_OPTIONS,
  GENERATION_RESOLUTION_OPTIONS,
  type GenerationAspectRatioId,
  type GenerationResolution,
  type ImageGenerationOptions,
} from '../../../../lib/dramaGenerationOptions'
import {
  catalogImageModels,
  catalogModelLabel,
  useMediaModelsCatalog,
} from '../../../../hooks/useMediaModelsCatalog'
import { useI18n } from '../../../../i18n/context'
import './dramaImageGenOptions.css'

type DramaImageGenOptionsBarProps = {
  value: ImageGenerationOptions
  onChange: (next: ImageGenerationOptions) => void
  disabled?: boolean
  /** 是否持久化风格到项目（Assets 步骤用） */
  onStylePersist?: (styleId: string) => void | Promise<void>
}

type OpenPanel = 'style' | 'model' | 'output' | null

/** 渲染生图选项条：风格 · 模型 · 比例清晰度 */
export function DramaImageGenOptionsBar({
  value,
  onChange,
  disabled = false,
  onStylePersist,
}: DramaImageGenOptionsBarProps) {
  const { t } = useI18n()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState<OpenPanel>(null)
  const catalog = useMediaModelsCatalog()
  const imageModels = catalogImageModels(catalog)

  useEffect(() => {
    // 目录到达后，把旧 Kie/方舟 id 换成后台默认图片模型
    if (!catalog || disabled) return
    const ids = imageModels.map((m) => m.id)
    if (!ids.length) return
    if (value.model_id && ids.includes(value.model_id)) return
    const next = catalog.defaults.image_model || ids[0]
    if (next && next !== value.model_id) onChange({ ...value, model_id: next })
  }, [catalog, disabled])

  useEffect(() => {
    if (!open) return
    // 点击外部关闭弹层
    function onDoc(e: Event) {
      const target = e.target as Node | null
      if (rootRef.current && target && !rootRef.current.contains(target)) {
        setOpen(null)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const stop = (e: MouseEvent) => {
    e.stopPropagation()
  }

  const styleLabel = getImageStyleLabel(value.image_style_id) || t('dramaCanvas.genOptions.style')
  const modelLabel = catalogModelLabel(value.model_id, imageModels, t('dramaCanvas.options.imageModel'))
  const outputLabel = formatOutputSettingsLabel(value.aspect_ratio, value.resolution)

  return (
    <div ref={rootRef} className="fc-gen-opts" onMouseDown={stop} onPointerDown={stop}>
      <div className="fc-gen-opts-triggers">
        <button
          type="button"
          className={`fc-gen-opt-btn${open === 'style' || value.image_style_id ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => setOpen((c) => (c === 'style' ? null : 'style'))}
        >
          <Smile size={14} strokeWidth={1.8} />
          <span className="fc-gen-opt-label">{styleLabel}</span>
          <ChevronDown size={12} />
        </button>
        <button
          type="button"
          className={`fc-gen-opt-btn${open === 'model' ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => setOpen((c) => (c === 'model' ? null : 'model'))}
        >
          <BarChart3 size={14} strokeWidth={1.8} />
          <span className="fc-gen-opt-label">{modelLabel}</span>
          <ChevronDown size={12} />
        </button>
        <button
          type="button"
          className={`fc-gen-opt-btn${open === 'output' ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => setOpen((c) => (c === 'output' ? null : 'output'))}
        >
          <RectangleVertical size={14} strokeWidth={1.8} />
          <span className="fc-gen-opt-label">{outputLabel}</span>
          <ChevronDown size={12} />
        </button>
      </div>

      {open === 'style' ? (
        <div className="fc-gen-opt-panel fc-gen-style-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.imageStyle')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.imageStyle')}</div>
          <div className="fc-gen-style-grid">
            {IMAGE_STYLE_OPTIONS.map((opt) => {
              const selected = value.image_style_id === opt.id
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`fc-gen-style-card${selected ? ' selected' : ''}`}
                  onClick={() => {
                    onChange({ ...value, image_style_id: opt.id })
                    void onStylePersist?.(opt.id)
                    setOpen(null)
                  }}
                >
                  <DramaImageStylePreviewImg styleId={opt.id} alt={getImageStyleLabel(opt.id) || opt.label} loading="lazy" />
                  <span>{getImageStyleLabel(opt.id) || opt.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      ) : null}

      {open === 'model' ? (
        <div className="fc-gen-opt-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.imageModelAria')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.model')}</div>
          <div className="fc-gen-model-list">
            {imageModels.length === 0 ? (
              <p className="fc-gen-model-empty">{t('dramaCanvas.genOptions.noImageModels')}</p>
            ) : null}
            {imageModels.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`fc-gen-model-item${value.model_id === m.id ? ' selected' : ''}`}
                onClick={() => {
                  onChange({ ...value, model_id: m.id })
                  setOpen(null)
                }}
              >
                <strong>{m.label}</strong>
                <span>{m.description || 'TokenFree'}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {open === 'output' ? (
        <div className="fc-gen-opt-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.outputAria')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.ratio')}</div>
          <div className="fc-gen-chip-row">
            {GENERATION_ASPECT_RATIO_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`fc-gen-chip${value.aspect_ratio === opt.id ? ' selected' : ''}`}
                onClick={() =>
                  onChange({ ...value, aspect_ratio: opt.id as GenerationAspectRatioId })
                }
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="fc-gen-opt-panel-title" style={{ marginTop: 10 }}>
            {t('dramaCanvas.genOptions.resolution')}
          </div>
          <div className="fc-gen-chip-row">
            {GENERATION_RESOLUTION_OPTIONS.map((res) => (
              <button
                key={res}
                type="button"
                className={`fc-gen-chip${value.resolution === res ? ' selected' : ''}`}
                onClick={() => {
                  onChange({ ...value, resolution: res as GenerationResolution })
                  setOpen(null)
                }}
              >
                {res}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export type { ImageStyleId }
