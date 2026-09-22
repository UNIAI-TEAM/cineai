/** 画布顶栏：返回、标题、已保存指示、设置占位 */
import { useState } from 'react'
import { ChevronLeft, Maximize2, Settings } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useCanvasStore } from './CanvasStore'
import { useI18n } from '../../../i18n/context'

type Props = {
  variant?: 'fullscreen' | 'embedded'
}

/** 渲染画布页顶部工具栏 */
export function CanvasTopBar({ variant = 'fullscreen' }: Props) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { saveStatusVisible, projectId, freeCanvasMode } = useCanvasStore()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const embedded = variant === 'embedded'

  return (
    <>
      <div className="fc-overlay fc-topbar">
        <div className="fc-topbar-left">
          {embedded ? null : (
            <button
              type="button"
              className="fc-icon-btn"
              aria-label={t('dramaCanvas.topBar.back')}
              title={t('dramaCanvas.topBar.back')}
              onClick={() => {
                if (freeCanvasMode) {
                  navigate('/drama')
                  return
                }
                if (window.history.length > 1) navigate(-1)
                else navigate(`/drama/projects/${projectId}`)
              }}
            >
              <ChevronLeft size={20} strokeWidth={1.8} />
            </button>
          )}
          <span className="fc-topbar-title">
            {embedded
              ? t('dramaCanvas.topBar.titleEmbedded')
              : freeCanvasMode
                ? t('dramaCanvas.topBar.titleFree')
                : t('dramaCanvas.topBar.titleLibrary')}
          </span>
          {saveStatusVisible ? (
            <span className="fc-save-pill">
              <span className="fc-save-dot" />
              {t('dramaCanvas.topBar.saved')}
            </span>
          ) : null}
        </div>

        <div className="fc-topbar-right">
          {embedded ? (
            <button
              type="button"
              className="fc-icon-btn"
              aria-label={t('dramaCanvas.topBar.fullscreen')}
              title={t('dramaCanvas.topBar.fullscreen')}
              onClick={() => navigate(`/drama/projects/${projectId}/canvas`)}
            >
              <Maximize2 size={18} strokeWidth={1.8} />
            </button>
          ) : null}
          <button
            type="button"
            className="fc-icon-btn"
            aria-label={t('dramaCanvas.topBar.settings')}
            title={t('dramaCanvas.topBar.settings')}
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen((v) => !v)}
          >
            <Settings size={18} strokeWidth={1.8} />
          </button>
        </div>
      </div>

      {settingsOpen ? (
        <div className="fc-settings-pop" role="dialog" aria-label={t('dramaCanvas.topBar.settingsTitle')}>
          <strong>{t('dramaCanvas.topBar.settingsTitle')}</strong>
          {freeCanvasMode
            ? t('dramaCanvas.topBar.settingsFreeHint')
            : t('dramaCanvas.topBar.settingsLibraryHint')}
          <div style={{ marginTop: 10 }}>
            <button
              type="button"
              className="fc-icon-btn is-sm"
              style={{ width: 'auto', padding: '0 12px', borderRadius: 10 }}
              onClick={() => setSettingsOpen(false)}
            >
              {t('dramaCanvas.topBar.close')}
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
