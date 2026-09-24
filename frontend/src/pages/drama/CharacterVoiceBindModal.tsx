/** 角色音色绑定：从漫剧 voice 资产选择，写入 params 供 Seedance reference_audio 使用 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { dramaApi, resolveDramaMediaUrl, type CatalogVoice, type DramaAsset } from '../../api/drama'
import Modal from '../../components/ui/Modal'
import { useI18n } from '../../i18n/context'
import { translate } from '../../i18n/translate'
import { displayDramaAssetName } from '../../lib/dramaLibraryAssets'
import { buildBoundParams, readAssetVoiceBinding, readVoicePrompt } from '../../lib/dramaVoiceBinding'
import { speakerForPrompt } from '../../lib/voiceLang'
import { useVoiceCatalog } from './useVoiceCatalog'
import { VoiceCatalogPicker } from './VoiceCatalogPicker'

type Props = {
  asset: DramaAsset
  projectId: number
  open: boolean
  onClose: () => void
  onBound: (asset: DramaAsset) => void
  onError: (message: string) => void
}

// 读取 voice 资产已保存的 speaker
function readVoiceSpeaker(asset: DramaAsset): string {
  const params = (asset.params || {}) as Record<string, unknown>
  return typeof params.speaker === 'string' ? params.speaker.trim() : ''
}

// 渲染角色音色绑定弹窗
export function CharacterVoiceBindModal({
  asset,
  projectId,
  open,
  onClose,
  onBound,
  onError,
}: Props) {
  /*
   * voiceAssets 项目内 voice 资产
   * selectedId 选中音色
   * newPrompt 新建音色描述
   * newName 新建音色名称
   * busy 提交中
   * synthBusy 合成中
   * promptBusy AI 生成提示词中
   */
  const [voiceAssets, setVoiceAssets] = useState<DramaAsset[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [newPrompt, setNewPrompt] = useState('')
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)
  const [synthBusy, setSynthBusy] = useState(false)
  const [promptBusy, setPromptBusy] = useState(false)
  const [suggestedSpeaker, setSuggestedSpeaker] = useState('')
  // suggestedPrompt 推荐 speaker 时对应的描述；描述被改动后推荐作废（见 speakerForPrompt）
  const [suggestedPrompt, setSuggestedPrompt] = useState('')
  const [mode, setMode] = useState<'catalog' | 'pick' | 'create'>('catalog')
  const promptRequestedRef = useRef(false)
  const { t } = useI18n()

  const bound = useMemo(() => readAssetVoiceBinding(asset), [asset])
  const selectedVoice = voiceAssets.find((v) => v.id === selectedId) || null
  const previewUrl = selectedVoice?.url ? resolveDramaMediaUrl(selectedVoice.url) : ''
  // 当前描述仍是 AI 推荐原文时才沿用推荐 speaker
  const activeSpeaker = speakerForPrompt(newPrompt, suggestedPrompt, suggestedSpeaker)

  // Tab "Chọn giọng": tải danh mục theo dự án + xử lý chọn nhanh một giọng, gắn ngay cho nhân vật
  const { catalog, catalogLang, catalogError, pickingSpeaker, handlePickCatalog } = useVoiceCatalog({
    open,
    projectId,
    asset,
    onBound,
    onClose,
    onError,
    addVoiceAsset: (voice) => setVoiceAssets((prev) => [...prev, voice]),
  })

  // 根据角色设定 AI 生成音色描述
  const fetchVoicePrompt = useCallback(
    async (force = false) => {
      if (promptBusy) return
      if (!force && newPrompt.trim()) return
      setPromptBusy(true)
      try {
        const result = await dramaApi.suggestVoicePrompt({
          project_id: projectId,
          asset_id: asset.id,
        })
        setNewPrompt(result.voice_prompt || '')
        setSuggestedPrompt(result.voice_prompt || '')
        setSuggestedSpeaker(result.speaker || '')
      } catch (err) {
        onError(err instanceof Error ? err.message : t('dramaAssets.voiceBind.suggestFailed'))
      } finally {
        setPromptBusy(false)
      }
    },
    [asset.id, newPrompt, onError, projectId, promptBusy, t],
  )

  useEffect(() => {
    if (!open) {
      promptRequestedRef.current = false
      return
    }
    setSelectedId(bound?.sourceAssetId ?? null)
    setNewPrompt('')
    setSuggestedPrompt('')
    setSuggestedSpeaker('')
    setNewName(
      translate('dramaAssets.voiceBind.defaultName', {
        name: asset.name || translate('dramaAssets.voiceBind.characterFallback'),
      }),
    )
    setMode('catalog')
    promptRequestedRef.current = false

    dramaApi
      .listAssets(projectId)
      .then((list) => {
        const voices = list.filter((a) => (a.type || '').toLowerCase() === 'voice')
        setVoiceAssets(voices)
        if (!bound?.sourceAssetId && voices[0]) {
          setSelectedId(voices[0].id)
        }
      })
      .catch((err) => onError(err instanceof Error ? err.message : translate('dramaAssets.common.loadVoicesFailed')))
  }, [open, asset, projectId, bound?.sourceAssetId, onError])

  // 进入「新建并合成」时自动 AI 生成音色描述
  useEffect(() => {
    if (!open || mode !== 'create' || promptRequestedRef.current) return
    promptRequestedRef.current = true
    void fetchVoicePrompt(true)
  }, [open, mode, fetchVoicePrompt])

  if (!open) return null

  // 按提示词新建并合成 voice 资产
  async function handleCreateAndSynth() {
    const prompt = newPrompt.trim()
    if (!prompt || synthBusy) return
    setSynthBusy(true)
    try {
      const result = await dramaApi.generateVoice({
        project_id: projectId,
        name: newName.trim() || undefined,
        voice_prompt: prompt,
        speaker: activeSpeaker || undefined,
        character_asset_id: asset.id,
      })
      const created = result.asset
      if (!created) throw new Error(t('dramaAssets.voiceBind.synthFailed'))
      setVoiceAssets((prev) => [...prev, created])
      setSelectedId(created.id)
      setMode('pick')
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.voiceSynthFailed'))
    } finally {
      setSynthBusy(false)
    }
  }

  // 对已有 voice 资产重新合成
  async function handleResynth(voice: DramaAsset) {
    const prompt = readVoicePrompt(voice)
    if (!prompt || synthBusy) return
    setSynthBusy(true)
    try {
      const result = await dramaApi.generateVoice({
        project_id: projectId,
        asset_id: voice.id,
        voice_prompt: prompt,
        speaker: readVoiceSpeaker(voice) || speakerForPrompt(prompt, suggestedPrompt, suggestedSpeaker) || undefined,
        character_asset_id: asset.id,
      })
      if (result.asset) {
        setVoiceAssets((prev) => prev.map((v) => (v.id === voice.id ? result.asset! : v)))
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.voiceBind.resynthFailed'))
    } finally {
      setSynthBusy(false)
    }
  }

  // 确认绑定到角色
  async function handleConfirm() {
    if (!selectedVoice?.url || busy) {
      onError(t('dramaAssets.voiceBind.selectRequired'))
      return
    }
    setBusy(true)
    try {
      const updated = await dramaApi.updateAsset(asset.id, {
        params: buildBoundParams(asset, selectedVoice),
      })
      onBound(updated)
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.bindFailed'))
    } finally {
      setBusy(false)
    }
  }

  // 解除绑定
  async function handleUnbind() {
    if (busy) return
    setBusy(true)
    try {
      const prev = (asset.params || {}) as Record<string, unknown>
      const nextParams = { ...prev }
      delete nextParams.voiceAudio
      if (nextParams.canvas && typeof nextParams.canvas === 'object') {
        const canvas = { ...(nextParams.canvas as Record<string, unknown>) }
        delete canvas.voiceAudio
        nextParams.canvas = canvas
      }
      const updated = await dramaApi.updateAsset(asset.id, { params: nextParams })
      onBound(updated)
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.unbindFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('dramaAssets.voiceBind.title')}
      size="lg"
      dismissible={!busy && !pickingSpeaker}
      className="drama-voice-bind-modal"
      footer={
        <>
          <button type="button" className="pf-btn" onClick={onClose} disabled={busy}>
            {t('common.cancel')}
          </button>
          {bound ? (
            <button type="button" className="pf-btn" onClick={() => void handleUnbind()} disabled={busy}>
              {t('dramaAssets.common.unbind')}
            </button>
          ) : null}
          {mode === 'pick' ? (
            <button
              type="button"
              className="pf-btn pf-btn-lime"
              onClick={() => void handleConfirm()}
              disabled={!selectedVoice?.url || busy}
            >
              {busy ? t('dramaAssets.common.binding') : t('dramaAssets.common.confirmBind')}
            </button>
          ) : null}
        </>
      }
    >
      <p className="drama-muted">
        {t('dramaAssets.voiceBind.intro', {
          name: asset.name || t('dramaAssets.voiceBind.characterFallback'),
        })}
      </p>

      <div className="drama-voice-mode-tabs">
        <button
          type="button"
          className={mode === 'catalog' ? 'active' : ''}
          onClick={() => setMode('catalog')}
        >
          {t('dramaAssets.voiceBind.catalogTab')}
        </button>
        <button
          type="button"
          className={mode === 'pick' ? 'active' : ''}
          onClick={() => setMode('pick')}
        >
          {t('dramaAssets.common.pickExisting')}
        </button>
        <button
          type="button"
          className={mode === 'create' ? 'active' : ''}
          onClick={() => {
            setMode('create')
            if (!newPrompt.trim() && !promptBusy) {
              promptRequestedRef.current = false
            }
          }}
        >
          {t('dramaAssets.voiceBind.createAndSynth')}
        </button>
      </div>

      {mode === 'catalog' ? (
        catalogError ? (
          <p className="drama-muted">{catalogError}</p>
        ) : catalog === null ? (
          <p className="drama-muted">{t('dramaAssets.voiceBind.catalogLoading')}</p>
        ) : catalog.length === 0 ? (
          <p className="drama-muted">{t('dramaAssets.voiceBind.catalogEmpty')}</p>
        ) : (
          <VoiceCatalogPicker
            voices={catalog}
            lang={catalogLang}
            busySpeaker={pickingSpeaker}
            onPick={(v: CatalogVoice) => void handlePickCatalog(v)}
          />
        )
      ) : mode === 'pick' ? (
        <div className="drama-voice-list">
          {voiceAssets.length === 0 ? (
            <p className="drama-muted">{t('dramaAssets.voiceBind.emptyPick')}</p>
          ) : (
            voiceAssets.map((voice) => {
              const hasAudio = Boolean(voice.url)
              return (
                <label key={voice.id} className="drama-voice-option">
                  <input
                    type="radio"
                    name="drama-voice-asset"
                    checked={selectedId === voice.id}
                    onChange={() => setSelectedId(voice.id)}
                  />
                  <span>
                    {voice.name ? displayDramaAssetName(voice.name) : t('dramaAssets.common.voiceNumbered', { id: voice.id })}
                    <small>
                      {hasAudio
                        ? t('dramaAssets.common.synthesized')
                        : t('dramaAssets.common.notSynthesized')}
                    </small>
                  </span>
                  {hasAudio ? (
                    <button
                      type="button"
                      className="pf-btn pf-btn-sm"
                      disabled={synthBusy}
                      onClick={(e) => {
                        e.preventDefault()
                        void handleResynth(voice)
                      }}
                    >
                      {t('dramaAssets.voiceBind.resynth')}
                    </button>
                  ) : null}
                </label>
              )
            })
          )}
        </div>
      ) : (
        <div className="drama-voice-create-form">
          <label className="drama-field">
            <span>{t('dramaAssets.voiceBind.nameLabel')}</span>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={t('dramaAssets.voiceBind.namePlaceholder')}
            />
          </label>
          <label className="drama-field">
            <span className="drama-voice-prompt-label">
              {t('dramaAssets.voiceBind.promptLabel')}
              <button
                type="button"
                className="pf-btn pf-btn-sm"
                disabled={promptBusy || synthBusy}
                onClick={() => void fetchVoicePrompt(true)}
              >
                {promptBusy ? t('dramaAssets.voiceBind.aiGenerating') : t('dramaAssets.voiceBind.aiRegenerate')}
              </button>
            </span>
            <textarea
              rows={4}
              value={promptBusy && !newPrompt ? t('dramaAssets.voiceBind.promptLoading') : newPrompt}
              readOnly={promptBusy && !newPrompt}
              onChange={(e) => setNewPrompt(e.target.value)}
              placeholder={t('dramaAssets.voiceBind.promptPlaceholder')}
            />
          </label>
          {activeSpeaker ? (
            <p className="drama-muted" style={{ margin: 0, fontSize: 12 }}>
              {t('dramaAssets.voiceBind.speakerLabel')}
              <code>{activeSpeaker}</code>
              {t('dramaAssets.voiceBind.speakerHint')}
            </p>
          ) : null}
          <button
            type="button"
            className="pf-btn pf-btn-lime"
            disabled={!newPrompt.trim() || synthBusy || promptBusy}
            onClick={() => void handleCreateAndSynth()}
          >
            {synthBusy ? t('dramaAssets.common.synthesizing') : t('dramaAssets.voiceBind.synthButton')}
          </button>
        </div>
      )}

      {previewUrl ? (
        <audio className="drama-voice-audio" controls src={previewUrl} />
      ) : null}
    </Modal>
  )
}
