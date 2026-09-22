/** 全局资产库选择弹窗：跨项目挑选图片资产（导入或应用到节点） */
import { useEffect, useMemo, useState } from 'react'
import { dramaApi, resolveDramaMediaUrl, type DramaAsset } from '../../api/drama'
import { displayDramaAssetName, filterDramaLibraryAssets, isDramaLibraryAsset } from '../../lib/dramaLibraryAssets'
import { DRAMA_VOICE_BINDING_ENABLED } from '../../lib/dramaVoiceBinding'
import BillingErrorNotice from '../../components/billing/BillingErrorNotice'
import Modal from '../../components/ui/Modal'
import { useI18n } from '../../i18n/context'
import { translate } from '../../i18n/translate'
import { getActiveLocale } from '../../i18n/detect'
import { messages } from '../../i18n/messages'
import './drama.css'

export type GlobalAssetTabKey = 'character' | 'scene' | 'prop' | 'voice' | 'all'

type Props = {
  open: boolean
  onClose: () => void
  /** 当前项目 ID，用于标注来源与可选排除本项 */
  projectId: number
  /** 默认 Tab；canvas 场景可传 all */
  defaultTab?: GlobalAssetTabKey
  /** 限定可选资产 type 列表；不传则按 Tab 筛选 */
  allowedTypes?: string[]
  /** 标题 */
  title?: string
  /** 确认按钮文案 */
  confirmLabel?: string
  onPick: (asset: DramaAsset) => void | Promise<void>
}

// 分类 Tab（文案在渲染时按 key 取 dramaAssets.kinds）
const TABS: GlobalAssetTabKey[] = [
  'character',
  'scene',
  'prop',
  ...(DRAMA_VOICE_BINDING_ENABLED ? ['voice' as const] : []),
]

// 资产是否匹配 Tab
function matchAssetTab(asset: DramaAsset, tab: GlobalAssetTabKey): boolean {
  if (!isDramaLibraryAsset(asset)) return false
  if (tab === 'all') return true
  const t = (asset.type || '').toLowerCase()
  if (tab === 'voice') return t === 'voice'
  return t === tab
}

// asset visible in picker (voice always; image needs cover/url)
function hasMedia(asset: DramaAsset): boolean {
  if ((asset.type || '').toLowerCase() === 'voice') return true
  return Boolean(asset.url || asset.cover)
}

// 渲染全局资产库选择弹窗（使用全局 Modal）
export function GlobalAssetPickerModal({
  open,
  onClose,
  projectId,
  defaultTab = 'character',
  allowedTypes,
  title,
  confirmLabel,
  onPick,
}: Props) {
  const { t, m } = useI18n()
  /*
   * allAssets 用户全部项目资产
   * tab 当前分类
   * query 搜索词
   * selectedId 选中资产
   * loading 加载中
   * busy 提交中
   * error 错误文案
   */
  const [allAssets, setAllAssets] = useState<DramaAsset[]>([])
  const [tab, setTab] = useState<GlobalAssetTabKey>(
    defaultTab === 'voice' && !DRAMA_VOICE_BINDING_ENABLED ? 'character' : defaultTab,
  )
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setTab(
      defaultTab === 'voice' && !DRAMA_VOICE_BINDING_ENABLED ? 'character' : defaultTab,
    )
    setQuery('')
    setSelectedId(null)
    setError('')
    setLoading(true)
    dramaApi
      .listAssets(undefined, { libraryOnly: true })
      .then((rows) => setAllAssets(filterDramaLibraryAssets(rows)))
      .catch((err) => setError(err instanceof Error ? err.message : translate('dramaAssets.picker.loadFailed')))
      .finally(() => setLoading(false))
  }, [open, defaultTab])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allAssets.filter((asset) => {
      if (!hasMedia(asset)) return false
      if (allowedTypes?.length) {
        const t = (asset.type || '').toLowerCase()
        if (!allowedTypes.includes(t)) {
          return false
        }
      } else if (!matchAssetTab(asset, tab)) {
        return false
      }
      if (!q) return true
      // 同时匹配原名与界面显示名（如「新角色」→ Nhân vật mới）
      const name = `${asset.name || ''} ${displayDramaAssetName(asset.name)}`.toLowerCase()
      return name.includes(q) || String(asset.project_id).includes(q)
    })
  }, [allAssets, allowedTypes, query, tab])

  // 确认选用资产
  async function handleConfirm() {
    const picked = allAssets.find((a) => a.id === selectedId)
    if (!picked || busy) return
    setBusy(true)
    setError('')
    try {
      await onPick(picked)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaAssets.picker.applyFailed'))
    } finally {
      setBusy(false)
    }
  }

  const showTabs = !allowedTypes?.length && defaultTab !== 'all'

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title || t('dramaAssets.picker.title')}
      size="lg"
      dismissible={!busy}
      className="drama-global-picker-modal"
      footer={
        <>
          <button type="button" className="pf-btn" onClick={onClose} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="pf-btn pf-btn-lime"
            disabled={!selectedId || busy}
            onClick={() => void handleConfirm()}
          >
            {busy ? t('dramaAssets.picker.processing') : confirmLabel || t('dramaAssets.picker.confirm')}
          </button>
        </>
      }
    >
      <p className="drama-muted drama-global-picker-lead">
        {t('dramaAssets.picker.lead')}
      </p>

      {showTabs ? (
        <div className="drama-asset-tabs drama-global-picker-tabs">
          {TABS.map((key) => (
            <button
              key={key}
              type="button"
              className={tab === key ? 'active' : ''}
              onClick={() => {
                setTab(key)
                setSelectedId(null)
              }}
            >
              {m.dramaAssets.kinds[key]}
            </button>
          ))}
        </div>
      ) : null}

      <input
        className="pf-dialog-input drama-global-picker-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('dramaAssets.picker.searchPlaceholder')}
      />

      {error ? <BillingErrorNotice message={error} className="drama-error" /> : null}
      {loading ? <p className="drama-muted">{t('dramaAssets.picker.loading')}</p> : null}

      <div className="drama-global-picker-grid">
        {filtered.map((asset) => {
          const isVoice = (asset.type || '').toLowerCase() === 'voice'
          const src = isVoice ? '' : resolveDramaMediaUrl(asset.cover || asset.url)
          const audioSrc = isVoice ? resolveDramaMediaUrl(asset.url) : ''
          const selected = selectedId === asset.id
          const fromCurrent = asset.project_id === projectId
          return (
            <button
              key={asset.id}
              type="button"
              className={`drama-global-picker-card${selected ? ' is-selected' : ''}`}
              onClick={() => setSelectedId(asset.id)}
            >
              {isVoice ? (
                <div className="drama-voice-card-icon drama-global-picker-voice">VO</div>
              ) : src ? (
                <img src={src} alt={asset.name || ''} />
              ) : null}
              <div className="drama-global-picker-card-meta">
                <strong>{displayDramaAssetName(asset.name)}</strong>
                <span>
                  {fromCurrent
                    ? t('dramaAssets.picker.currentProject')
                    : t('dramaAssets.common.projectNo', { id: asset.project_id })}
                  {isVoice && audioSrc
                    ? ` · ${t('dramaAssets.common.synthesized')}`
                    : isVoice
                      ? ` · ${t('dramaAssets.common.notSynthesized')}`
                      : ''}
                </span>
              </div>
              {selected ? <span className="drama-global-picker-check">✓</span> : null}
            </button>
          )
        })}
      </div>
      {!loading && filtered.length === 0 ? (
        <p className="drama-muted">{t('dramaAssets.picker.empty')}</p>
      ) : null}
    </Modal>
  )
}

// 将外部资产复制到当前项目（导入）
export async function importGlobalAssetToProject(
  projectId: number,
  source: DramaAsset,
): Promise<DramaAsset> {
  if (!source.url && !source.cover) {
    throw new Error(messages[getActiveLocale()].dramaAssets.picker.noImage)
  }
  const params = {
    ...(source.params || {}),
    importedFromAssetId: source.id,
    importedFromProjectId: source.project_id,
  }
  return dramaApi.createAsset({
    project_id: projectId,
    type: source.type || 'none',
    asset_type: source.asset_type || 'image',
    name: source.name || '未命名',
    cover: source.cover || source.url,
    url: source.url || source.cover,
    params,
  })
}

// 画布 kind → 资产 type 筛选
export function canvasKindToLibraryTypes(kind: string): string[] {
  if (kind === 'character') return ['character']
  if (kind === 'scene') return ['scene']
  return ['prop', 'image']
}
