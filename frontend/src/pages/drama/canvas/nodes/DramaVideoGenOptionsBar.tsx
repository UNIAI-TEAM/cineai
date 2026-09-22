/** 画布视频节点：风格 / Seedance 模型 / 时长 / 比例清晰度 */
import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { BarChart3, ChevronDown, RectangleVertical, Smile, Timer } from 'lucide-react'
import {
  getImageStyleLabel,
  IMAGE_STYLE_OPTIONS,
} from '../../../../lib/dramaImageStyles'
import { DramaImageStylePreviewImg } from '../../../../components/drama/DramaImageStylePreviewImg'
import {
  clampVideoDuration,
  formatVideoOutputLabel,
  VIDEO_ASPECT_RATIO_OPTIONS,
  VIDEO_DURATION_MAX,
  VIDEO_DURATION_MIN,
  VIDEO_DURATION_PRESETS,
  VIDEO_RESOLUTION_OPTIONS,
  type VideoAspectRatio,
  type VideoGenerationOptions,
  type VideoResolution,
} from '../../../../lib/dramaVideoGenerationOptions'
import {
  catalogModelLabel,
  catalogVideoModels,
  useMediaModelsCatalog,
} from '../../../../hooks/useMediaModelsCatalog'
import { useI18n } from '../../../../i18n/context'
import './dramaImageGenOptions.css'

type DramaVideoGenOptionsBarProps = {
  value: VideoGenerationOptions
  onChange: (next: VideoGenerationOptions) => void
  disabled?: boolean
}

type OpenPanel = 'style' | 'model' | 'duration' | 'output' | null

/** 渲染视频生成选项条 */
export function DramaVideoGenOptionsBar({
  value,
  onChange,
  disabled = false,
}: DramaVideoGenOptionsBarProps) {
  const { t } = useI18n()
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState<OpenPanel>(null)
  const catalog = useMediaModelsCatalog()
  const videoModels = catalogVideoModels(catalog)

  useEffect(() => {
    // 目录到达后，把旧 Kie/方舟 id 换成后台默认视频模型
    if (!catalog || disabled) return
    const ids = videoModels.map((m) => m.id)
    if (!ids.length) return
    if (value.model_id && ids.includes(value.model_id)) return
    const next = catalog.defaults.video_model || ids[0]
    if (next && next !== value.model_id) onChange({ ...value, model_id: next })
  }, [catalog, disabled])

  useEffect(() => {
    if (!open) return
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
  const modelLabel = catalogModelLabel(value.model_id, videoModels, t('dramaCanvas.options.videoModel'))
  const outputLabel = formatVideoOutputLabel(value.aspect_ratio, value.resolution)

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
          className={`fc-gen-opt-btn${open === 'duration' ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => setOpen((c) => (c === 'duration' ? null : 'duration'))}
        >
          <Timer size={14} strokeWidth={1.8} />
          <span className="fc-gen-opt-label">{value.duration_sec}s</span>
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
        <div className="fc-gen-opt-panel fc-gen-style-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.videoStyle')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.videoStyle')}</div>
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
        <div className="fc-gen-opt-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.videoModelAria')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.model')}</div>
          <div className="fc-gen-model-list">
            {videoModels.length === 0 ? (
              <p className="fc-gen-model-empty">{t('dramaCanvas.genOptions.noVideoModels')}</p>
            ) : null}
            {videoModels.map((m) => (
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

      {open === 'duration' ? (
        <div className="fc-gen-opt-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.durationAria')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.duration')}</div>
          <div className="fc-gen-chip-row">
            {VIDEO_DURATION_PRESETS.map((sec) => (
              <button
                key={sec}
                type="button"
                className={`fc-gen-chip${value.duration_sec === sec ? ' selected' : ''}`}
                onClick={() => {
                  onChange({ ...value, duration_sec: sec })
                  setOpen(null)
                }}
              >
                {sec}s
              </button>
            ))}
          </div>
          <label className="fc-gen-duration-custom">
            {t('dramaCanvas.genOptions.customDuration', {
              min: VIDEO_DURATION_MIN,
              max: VIDEO_DURATION_MAX,
            })}
            <input
              type="number"
              min={VIDEO_DURATION_MIN}
              max={VIDEO_DURATION_MAX}
              value={value.duration_sec}
              disabled={disabled}
              onChange={(e) =>
                onChange({ ...value, duration_sec: clampVideoDuration(Number(e.target.value)) })
              }
            />
          </label>
        </div>
      ) : null}

      {open === 'output' ? (
        <div className="fc-gen-opt-panel" role="dialog" aria-label={t('dramaCanvas.genOptions.videoOutputAria')}>
          <div className="fc-gen-opt-panel-title">{t('dramaCanvas.genOptions.ratio')}</div>
          <div className="fc-gen-chip-row">
            {VIDEO_ASPECT_RATIO_OPTIONS.map((ratio) => (
              <button
                key={ratio}
                type="button"
                className={`fc-gen-chip${value.aspect_ratio === ratio ? ' selected' : ''}`}
                onClick={() => onChange({ ...value, aspect_ratio: ratio as VideoAspectRatio })}
              >
                {ratio}
              </button>
            ))}
          </div>
          <div className="fc-gen-opt-panel-title" style={{ marginTop: 10 }}>
            {t('dramaCanvas.genOptions.resolution')}
          </div>
          <div className="fc-gen-chip-row">
            {VIDEO_RESOLUTION_OPTIONS.map((res) => (
              <button
                key={res}
                type="button"
                className={`fc-gen-chip${value.resolution === res ? ' selected' : ''}`}
                onClick={() => {
                  onChange({ ...value, resolution: res as VideoResolution })
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
