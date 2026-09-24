/**
 * 旁白音色绑定：从漫剧 voice 资产选择，写入 project.params.narrationVoiceAudio
 * 供 Seedance 生成时作为全局 reference_audio 注入。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AudioLines } from 'lucide-react'
import { dramaApi, resolveDramaMediaUrl, type DramaAsset, type DramaProject } from '../../api/drama'
import Modal from '../../components/ui/Modal'
import type { VoiceBinding } from '../../lib/dramaVoiceBinding'
import { useI18n } from '../../i18n/context'
import { displayDramaAssetName } from '../../lib/dramaLibraryAssets'
import { translate } from '../../i18n/translate'

type Props = {
  project: DramaProject
  open: boolean
  onClose: () => void
  onUpdated: (project: DramaProject) => void
  onError: (message: string) => void
}

function readNarrationVoiceBinding(project: DramaProject): VoiceBinding | null {
  const params = project.params || {}
  const raw = (params as Record<string, unknown>).narrationVoiceAudio
  if (!raw || typeof raw !== 'object') return null
  const data = raw as Record<string, unknown>
  const sourceAssetId = typeof data.sourceAssetId === 'number' ? data.sourceAssetId : null
  const url = typeof data.url === 'string' ? data.url : ''
  const label =
    typeof data.label === 'string' ? displayDramaAssetName(data.label) : translate('dramaAssets.common.narratorVoice')
  if (!sourceAssetId || !url) return null
  return {
    sourceAssetId,
    url,
    label,
    voicePrompt: typeof data.voicePrompt === 'string' ? data.voicePrompt : undefined,
  }
}

export function NarratorVoiceBindModal({ project, open, onClose, onUpdated, onError }: Props) {
  const [voiceAssets, setVoiceAssets] = useState<DramaAsset[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const { t } = useI18n()

  const current = useMemo(() => readNarrationVoiceBinding(project), [project])

  const selectedVoice = useMemo(
    () => voiceAssets.find((v) => v.id === selectedId) || null,
    [voiceAssets, selectedId],
  )
  const previewUrl = selectedVoice?.url ? resolveDramaMediaUrl(selectedVoice.url) : ''

  const boundRef = useRef(false)
  useEffect(() => {
    if (!open) {
      boundRef.current = false
      return
    }
    if (boundRef.current) return
    boundRef.current = true

    setSelectedId(current?.sourceAssetId ?? null)
    dramaApi
      .listAssets(project.id)
      .then((list) => {
        const voices = list.filter((a) => (a.type || '').toLowerCase() === 'voice')
        setVoiceAssets(voices)
      })
      .catch((err) => onError(err instanceof Error ? err.message : t('dramaAssets.common.loadVoicesFailed')))
  }, [current?.sourceAssetId, onError, open, project.id, t])

  const handleConfirm = useCallback(async () => {
    if (!selectedVoice?.url || busy) {
      onError(t('dramaAssets.narrator.selectRequired'))
      return
    }
    setBusy(true)
    try {
      const binding: VoiceBinding = {
        sourceAssetId: selectedVoice.id,
        url: selectedVoice.url,
        // 无名称时按当前界面语言写入默认标签（展示时 displayDramaAssetName 兼容旧的中文值）
        label: selectedVoice.name || t('dramaAssets.common.narratorVoice'),
        // Narrator 端当前不依赖 voicePrompt；但保留字段给后续扩展
        voicePrompt:
          selectedVoice.params && typeof selectedVoice.params === 'object' && typeof (selectedVoice.params as any).voicePrompt === 'string'
            ? (selectedVoice.params as any).voicePrompt
            : undefined,
      }
      const nextParams = {
        ...(project.params || {}),
        narrationVoiceAudio: binding,
      }
      const updated = await dramaApi.updateProject(project.id, { params: nextParams })
      onUpdated(updated)
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.bindFailed'))
    } finally {
      setBusy(false)
    }
  }, [busy, onClose, onError, onUpdated, project.id, project.params, selectedVoice, t])

  const handleUnbind = useCallback(async () => {
    if (busy) return
    setBusy(true)
    try {
      const nextParams = { ...(project.params || {}) }
      delete (nextParams as Record<string, unknown>).narrationVoiceAudio
      const updated = await dramaApi.updateProject(project.id, { params: nextParams })
      onUpdated(updated)
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.unbindFailed'))
    } finally {
      setBusy(false)
    }
  }, [busy, onClose, onError, onUpdated, project.id, project.params, t])

  if (!open) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('dramaAssets.narrator.title')}
      size="lg"
      dismissible={!busy}
      footer={
        <>
          <button type="button" className="pf-btn" onClick={onClose} disabled={busy}>
            {t('common.cancel')}
          </button>
          {current ? (
            <button type="button" className="pf-btn" onClick={() => void handleUnbind()} disabled={busy}>
              {t('dramaAssets.common.unbind')}
            </button>
          ) : null}
          <button
            type="button"
            className="pf-btn pf-btn-lime"
            onClick={() => void handleConfirm()}
            disabled={!selectedVoice?.url || busy}
          >
            {busy ? t('dramaAssets.common.binding') : t('dramaAssets.common.confirmBind')}
          </button>
        </>
      }
    >
      <p className="drama-muted">
        {t('dramaAssets.narrator.introBefore')}
        <strong>reference_audio</strong>
        {t('dramaAssets.narrator.introAfter')}
      </p>

      <div className="drama-voice-mode-tabs" style={{ marginTop: 12 }}>
        <button type="button" className="active">
          {t('dramaAssets.common.pickExisting')}
        </button>
      </div>

      <div className="drama-voice-list" style={{ marginTop: 10 }}>
        {voiceAssets.length === 0 ? (
          <p className="drama-muted">{t('dramaAssets.narrator.empty')}</p>
        ) : (
          voiceAssets.map((voice) => {
            const hasAudio = Boolean(voice.url)
            const selected = selectedId === voice.id
            return (
              <label key={voice.id} className="drama-voice-option" style={{ cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="drama-narrator-voice"
                  checked={selected}
                  onChange={() => setSelectedId(voice.id)}
                />
                <span>
                  {voice.name ? displayDramaAssetName(voice.name) : t('dramaAssets.common.voiceNumbered', { id: voice.id })}{' '}
                  <small>
                    {hasAudio
                      ? t('dramaAssets.common.synthesized')
                      : t('dramaAssets.common.notSynthesized')}
                  </small>
                </span>
              </label>
            )
          })
        )}
      </div>

      {previewUrl ? (
        <div style={{ marginTop: 14, display: 'flex', gap: 12, alignItems: 'center' }}>
          <AudioLines size={16} />
          <audio className="drama-voice-audio" controls src={previewUrl} />
        </div>
      ) : null}
    </Modal>
  )
}

