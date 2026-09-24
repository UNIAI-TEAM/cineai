/** 资产详情操作框：预览图、上传/生图提示词编辑、生成/音色、形象历史版本 */
import { useEffect, useRef, useState } from 'react'
import { dramaApi, resolveDramaAssetPreviewUrl, type DramaAsset } from '../../api/drama'
import Modal from '../../components/ui/Modal'
import { readVisualPrompt } from '../../lib/dramaVisualPrompt'
import { dramaAssetHasImage } from '../../lib/dramaAssetImage'
import {
  formatAssetImageVersionLabel,
  readAssetImageVersions,
  resolveAssetImageVersionUrl,
} from '../../lib/dramaAssetImageVersions'
import { readAssetVoiceBinding } from './CharacterVoiceBindModal'
import { DramaImageLightbox } from './DramaImageLightbox'
import { CharacterAppearanceForm } from './CharacterAppearanceForm'
import {
  appearanceEqual,
  buildAppearanceSave,
  readAppearance,
  readPromptManual,
  type Appearance,
} from '../../lib/dramaAppearance'
import { useI18n } from '../../i18n/context'
import { displayDramaAssetName } from '../../lib/dramaLibraryAssets'

type Props = {
  asset: DramaAsset
  open: boolean
  busy?: boolean
  genLabel?: string
  onClose: () => void
  onUpdated: (asset: DramaAsset) => void
  onGenerate: (asset: DramaAsset) => void
  onBindVoice?: (asset: DramaAsset) => void
  onDelete?: (asset: DramaAsset) => void
  onError: (message: string) => void
}

// 将编辑后的提示词写回 params.visualPrompt
function buildPromptParams(asset: DramaAsset, prompt: string): Record<string, unknown> {
  const prev = (asset.params || {}) as Record<string, unknown>
  const kind = (asset.type || '').toLowerCase()
  const next: Record<string, unknown> = {
    ...prev,
    visualPrompt: prompt.trim(),
  }
  if (kind === 'character' || kind === 'scene') {
    next.visualImage = prompt.trim()
  }
  return next
}

// 渲染资产详情操作弹窗
export function DramaAssetDetailModal({
  asset,
  open,
  busy = false,
  genLabel,
  onClose,
  onUpdated,
  onGenerate,
  onBindVoice,
  onDelete,
  onError,
}: Props) {
  /*
   * promptDraft 提示词草稿
   * appearanceDraft 外形字段草稿
   * extracting AI 拆分中
   * saving 保存中
   * uploading 上传图片中
   * restoringVersionId 正在还原的版本
   * lightboxSrc 放大预览图 URL
   */
  const [promptDraft, setPromptDraft] = useState('')
  const [appearanceDraft, setAppearanceDraft] = useState<Appearance>(() => readAppearance(asset))
  const [extracting, setExtracting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null)
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null)
  const uploadInputRef = useRef<HTMLInputElement>(null)
  const { t, m } = useI18n()
  const kinds = m.dramaAssets.kinds as Record<string, string>
  const typeKey = (asset.type || '').toLowerCase()
  const typeLabel = kinds[typeKey] || asset.type || ''

  const mediaSrc = resolveDramaAssetPreviewUrl(asset)
  const hasImage = dramaAssetHasImage(asset)
  const voice = readAssetVoiceBinding(asset)
  const isCharacter = (asset.type || '').toLowerCase() === 'character'
  const isScene = (asset.type || '').toLowerCase() === 'scene'
  const isProp =
    (asset.type || '').toLowerCase() === 'prop' ||
    (asset.type || '').toLowerCase() === 'material'
  const deleteLabel = isScene
    ? t('dramaAssets.detail.deleteScene')
    : isProp
      ? t('dramaAssets.detail.deleteProp')
      : t('dramaAssets.detail.deleteCharacter')
  const canDelete = Boolean(onDelete) && (isCharacter || isScene || isProp)
  const promptDirty = promptDraft.trim() !== readVisualPrompt(asset).trim()
  const appearanceDirty = isCharacter && !appearanceEqual(appearanceDraft, readAppearance(asset))
  const wasManual = readPromptManual(asset)
  const dirty = promptDirty || appearanceDirty
  const imageVersions = readAssetImageVersions(asset)
  const actionBusy = busy || saving || uploading || Boolean(restoringVersionId)

  useEffect(() => {
    if (!open) return
    setPromptDraft(readVisualPrompt(asset))
    setAppearanceDraft(readAppearance(asset))
    setLightboxSrc(null)
    setRestoringVersionId(null)
  }, [open, asset])

  // Params gửi PATCH khi lưu: nhân vật đi qua buildAppearanceSave, tư liệu khác giữ buildPromptParams cũ
  function buildSaveParams(): Record<string, unknown> {
    if (!isCharacter) return buildPromptParams(asset, promptDraft.trim())
    return (
      buildAppearanceSave({
        appearance: appearanceDraft,
        appearanceDirty,
        promptText: promptDraft,
        promptDirty,
        wasManual,
      }) || {}
    )
  }

  // 保存提示词到资产 params
  async function savePrompt() {
    if (!isCharacter || promptDirty) {
      const text = promptDraft.trim()
      if (!text) {
        onError(t('dramaAssets.detail.promptRequired'))
        return
      }
    }
    setSaving(true)
    try {
      const updated = await dramaApi.updateAsset(asset.id, {
        params: buildSaveParams(),
      })
      onUpdated(updated)
      setPromptDraft(readVisualPrompt(updated))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.detail.savePromptFailed'))
    } finally {
      setSaving(false)
    }
  }

  // 先保存脏提示词再触发生图
  async function handleGenerate() {
    if (dirty) {
      if (!isCharacter || promptDirty) {
        const text = promptDraft.trim()
        if (!text) {
          onError(t('dramaAssets.detail.promptRequired'))
          return
        }
      }
      setSaving(true)
      try {
        const updated = await dramaApi.updateAsset(asset.id, {
          params: buildSaveParams(),
        })
        onUpdated(updated)
        setPromptDraft(readVisualPrompt(updated))
        onGenerate(updated)
      } catch (err) {
        onError(err instanceof Error ? err.message : t('dramaAssets.detail.savePromptFailed'))
      } finally {
        setSaving(false)
      }
      return
    }
    onGenerate(asset)
  }

  // AI tách mô tả hiện có thành 8 trường (chỉ điền form, người dùng xem rồi mới lưu)
  async function handleExtract() {
    setExtracting(true)
    try {
      const result = await dramaApi.extractAppearance(asset.id)
      setAppearanceDraft(readAppearance({ params: { appearance: result.appearance } }))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.appearance.extractFailed'))
    } finally {
      setExtracting(false)
    }
  }

  // Bỏ chế độ chỉnh tay: backend ghép lại prompt từ các trường
  async function handleRecompose() {
    setSaving(true)
    try {
      const updated = await dramaApi.updateAsset(asset.id, {
        params: { appearance: appearanceDraft, promptManual: false },
      })
      onUpdated(updated)
      setPromptDraft(readVisualPrompt(updated))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.detail.savePromptFailed'))
    } finally {
      setSaving(false)
    }
  }

  // 本地上传图片，视为已出图
  async function handleUpload(file: File) {
    setUploading(true)
    try {
      const updated = await dramaApi.uploadAssetMedia(asset.id, file)
      onUpdated(updated)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.uploadFailed'))
    } finally {
      setUploading(false)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
    }
  }

  // 将历史形象还原为当前
  async function handleRestoreVersion(versionId: string) {
    setRestoringVersionId(versionId)
    try {
      const updated = await dramaApi.activateAssetImageVersion(asset.id, versionId)
      onUpdated(updated)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.detail.restoreFailed'))
    } finally {
      setRestoringVersionId(null)
    }
  }

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={asset.name ? displayDramaAssetName(asset.name) : t('dramaAssets.detail.titleFallback')}
        size="lg"
        className="drama-asset-detail-modal"
        dismissible={!lightboxSrc}
        footer={
          <div className="drama-modal-actions">
            <button type="button" className="pf-btn" onClick={onClose}>
              {t('common.close')}
            </button>
            <button
              type="button"
              className="pf-btn"
              disabled={saving || !dirty || actionBusy}
              onClick={() => void savePrompt()}
            >
              {saving ? t('dramaAssets.detail.saving') : t('dramaAssets.detail.savePrompt')}
            </button>
            <button
              type="button"
              className="pf-btn drama-btn-primary"
              disabled={actionBusy || !promptDraft.trim()}
              onClick={() => void handleGenerate()}
            >
              {busy ? t('dramaAssets.common.generating') : genLabel || t('dramaAssets.imageGen.generate')}
            </button>
          </div>
        }
      >
        <div className="drama-asset-detail">
          <button
            type="button"
            className="drama-asset-detail-media"
            disabled={!mediaSrc}
            title={mediaSrc ? t('dramaAssets.common.clickToZoom') : undefined}
            onClick={() => mediaSrc && setLightboxSrc(mediaSrc)}
          >
            {mediaSrc ? (
              <img key={mediaSrc} src={mediaSrc} alt={asset.name || ''} />
            ) : (
              <div className="drama-asset-placeholder">{typeLabel || 'asset'}</div>
            )}
          </button>

          <p className="drama-muted drama-asset-detail-meta">
            {[
              typeLabel,
              hasImage ? t('dramaAssets.detail.hasImage') : t('dramaAssets.detail.noImage'),
              isCharacter && voice ? t('dramaAssets.detail.boundVoice', { label: voice.label }) : '',
              mediaSrc ? t('dramaAssets.detail.zoomHint') : '',
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>

          <div className="drama-asset-detail-extra">
            <input
              ref={uploadInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="sr-only"
              disabled={actionBusy}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void handleUpload(file)
              }}
            />
            <button
              type="button"
              className="pf-btn pf-btn-sm"
              disabled={actionBusy}
              onClick={() => uploadInputRef.current?.click()}
            >
              {uploading
                ? t('dramaAssets.detail.uploading')
                : hasImage
                  ? t('dramaAssets.detail.replaceImage')
                  : t('dramaAssets.detail.uploadImage')}
            </button>
            {isCharacter && onBindVoice ? (
              <button
                type="button"
                className="pf-btn pf-btn-sm"
                onClick={() => onBindVoice(asset)}
              >
                {voice ? t('dramaAssets.detail.changeVoice') : t('dramaAssets.detail.bindVoice')}
              </button>
            ) : null}
            {canDelete ? (
              <button
                type="button"
                className="pf-btn pf-btn-sm drama-btn-danger-text"
                disabled={actionBusy}
                onClick={() => onDelete?.(asset)}
              >
                {deleteLabel}
              </button>
            ) : null}
          </div>

          {imageVersions.length > 0 ? (
            <section className="drama-asset-image-versions" aria-label={t('dramaAssets.detail.versionsAria')}>
              <header className="drama-asset-image-versions-head">
                <strong>{t('dramaAssets.detail.versions')}</strong>
                <span className="drama-muted">
                  {t('dramaAssets.detail.versionCount', { count: imageVersions.length })}
                </span>
              </header>
              <ul className="drama-asset-image-versions-list">
                {imageVersions.map((version) => {
                  const thumb = resolveAssetImageVersionUrl(version)
                  const restoring = restoringVersionId === version.id
                  return (
                    <li key={version.id} className="drama-asset-image-version">
                      <button
                        type="button"
                        className="drama-asset-image-version-thumb"
                        title={t('dramaAssets.common.clickToZoom')}
                        onClick={() => setLightboxSrc(thumb)}
                      >
                        <img src={thumb} alt="" />
                      </button>
                      <div className="drama-asset-image-version-meta">
                        <span>{formatAssetImageVersionLabel(version)}</span>
                        {version.createdAt ? (
                          <small className="drama-muted">
                            {version.createdAt.replace('T', ' ').slice(0, 16)}
                          </small>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        className="pf-btn pf-btn-sm"
                        disabled={actionBusy}
                        onClick={() => void handleRestoreVersion(version.id)}
                      >
                        {restoring ? t('dramaAssets.detail.restoring') : t('dramaAssets.detail.restore')}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </section>
          ) : null}

          {isCharacter ? (
            <CharacterAppearanceForm
              value={appearanceDraft}
              onChange={setAppearanceDraft}
              onExtract={() => void handleExtract()}
              extracting={extracting}
              disabled={actionBusy || saving}
            />
          ) : null}
          {isCharacter && wasManual ? (
            <div className="drama-prompt-manual">
              <span className="pf-badge">{t('dramaAssets.appearance.manualBadge')}</span>
              <span className="drama-muted">{t('dramaAssets.appearance.manualHint')}</span>
              <button type="button" className="pf-btn pf-btn-sm" disabled={saving || actionBusy} onClick={() => void handleRecompose()}>
                {t('dramaAssets.appearance.recompose')}
              </button>
            </div>
          ) : null}

          <label className="drama-field">
            <span>{t('dramaAssets.detail.promptLabel')}</span>
            <textarea
              rows={8}
              value={promptDraft}
              onChange={(e) => setPromptDraft(e.target.value)}
              placeholder={t('dramaAssets.detail.promptPlaceholder')}
            />
          </label>
        </div>
      </Modal>

      {lightboxSrc ? (
        <DramaImageLightbox
          src={lightboxSrc}
          alt={asset.name || t('dramaAssets.common.preview')}
          onClose={() => setLightboxSrc(null)}
        />
      ) : null}
    </>
  )
}
