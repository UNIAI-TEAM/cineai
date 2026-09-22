/** 分集编辑：输入 @ 时弹出的资产 / 时长 / 运镜选择层 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Aperture, Clapperboard, LayoutGrid, Search, Timer, User } from 'lucide-react'
import { resolveDramaMediaUrl, type DramaAsset } from '../../api/drama'
import {
  DRAMA_CAMERA_LEXICON,
  dramaCameraUsageTips,
  filterDramaCameraLexicon,
  type DramaCameraLexiconItem,
} from '../../lib/dramaCameraLexicon'
import {
  DURATION_PRESET_OPTIONS,
  FRAGMENT_CONTENT_DURATION_MAX,
  type MentionCaretRect,
} from '../../lib/dramaEpisodePromptEditor'
import type { AssetScope } from './dramaEpisodeEditUtils'
import { useI18n } from '../../i18n/context'

type Props = {
  open: boolean
  query: string
  scope: AssetScope
  assets: DramaAsset[]
  referencedIds: Set<number>
  anchorRect: MentionCaretRect | null
  activeIndex: number
  contentDurationTotal: number
  onScopeChange: (scope: AssetScope) => void
  onActiveIndexChange: (index: number) => void
  onItemsCountChange: (count: number) => void
  onSelectAsset: (asset: DramaAsset) => void
  onSelectDuration: (seconds: number) => void
  onSelectCameraPhrase: (insert: string) => void
  onClose: () => void
}

type TabKey = 'assets' | 'tools'
type ToolsView = 'list' | 'duration' | 'camera'


// 渲染 @ 引用弹层
export function EpisodeEditMentionPopover({
  open,
  query,
  scope,
  assets,
  referencedIds,
  anchorRect,
  activeIndex,
  contentDurationTotal,
  onScopeChange,
  onActiveIndexChange,
  onItemsCountChange,
  onSelectAsset,
  onSelectDuration,
  onSelectCameraPhrase,
  onClose,
}: Props) {
  const { t, m } = useI18n()
  // typeLabels 资产类型展示名（按界面语言）
  const typeLabels = m.dramaEpisode.assetTypes as Record<string, string>
  const panelRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const [tab, setTab] = useState<TabKey>('assets')
  const [toolsView, setToolsView] = useState<ToolsView>('list')
  const [customDuration, setCustomDuration] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const effectiveQuery = useMemo(() => {
    const typed = searchQuery.trim() || query.trim()
    return typed.toLowerCase()
  }, [query, searchQuery])

  const filteredAssets = useMemo(() => {
    let list = assets
    if (scope === 'episode') {
      list = list.filter((a) => referencedIds.has(a.id))
      // 本集无引用时回退全剧，避免空列表无法插入
      if (list.length === 0) list = assets
    }
    if (!effectiveQuery) return list
    return list.filter((a) => {
      const name = (a.name || '').toLowerCase()
      const typeKey = a.asset_type || a.type
      const typeLabel = (typeLabels[typeKey] || typeKey || '').toLowerCase()
      return (
        name.includes(effectiveQuery) ||
        typeLabel.includes(effectiveQuery) ||
        String(a.id).includes(effectiveQuery)
      )
    })
  }, [assets, effectiveQuery, referencedIds, scope, typeLabels])

  const filteredCamera = useMemo(
    () => filterDramaCameraLexicon(DRAMA_CAMERA_LEXICON, toolsView === 'camera' ? query : ''),
    [query, toolsView],
  )

  const shotItems = useMemo(
    () => filteredCamera.filter((i) => i.group === 'shot'),
    [filteredCamera],
  )
  const moveItems = useMemo(
    () => filteredCamera.filter((i) => i.group === 'move'),
    [filteredCamera],
  )

  useEffect(() => {
    onItemsCountChange(tab === 'assets' ? filteredAssets.length : 0)
  }, [filteredAssets.length, onItemsCountChange, tab])

  useEffect(() => {
    if (!open) {
      setTab('assets')
      setToolsView('list')
      setCustomDuration('')
      setSearchQuery('')
    }
  }, [open])

  useEffect(() => {
    if (!open || tab !== 'assets') return
    const timer = window.setTimeout(() => searchRef.current?.focus(), 0)
    return () => window.clearTimeout(timer)
  }, [open, tab])

  useEffect(() => {
    onActiveIndexChange(0)
  }, [effectiveQuery, onActiveIndexChange, scope, tab])

  useEffect(() => {
    if (!open || tab !== 'assets') return
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Enter' || filteredAssets.length === 0) return
      const target = e.target as HTMLElement
      if (!target.closest('.drama-ep-mention-pop-search')) return
      e.preventDefault()
      onSelectAsset(filteredAssets[Math.min(activeIndex, filteredAssets.length - 1)])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [activeIndex, filteredAssets, onSelectAsset, open, tab])

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      const target = e.target as Node | null
      if (panelRef.current && target && !panelRef.current.contains(target)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, onClose])

  if (!open || !anchorRect) return null

  const top = Math.min(anchorRect.bottom + 8, window.innerHeight - 420)
  const left = Math.min(Math.max(12, anchorRect.left), window.innerWidth - 360)

  const remaining = Math.max(0, FRAGMENT_CONTENT_DURATION_MAX - contentDurationTotal)

  // 渲染一组运镜/景别按钮
  function renderCameraGroup(title: string, items: DramaCameraLexiconItem[]) {
    if (items.length === 0) return null
    return (
      <div className="drama-ep-mention-pop-camera-group">
        <p className="drama-ep-mention-pop-camera-heading">{title}</p>
        <div className="drama-ep-mention-pop-camera-grid">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              title={item.hint}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onSelectCameraPhrase(item.insert)}
            >
              <strong>{item.label}</strong>
              <em>{item.hint}</em>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return createPortal(
    <div
      ref={panelRef}
      className="drama-ep-mention-pop"
      style={{ top, left }}
      role="listbox"
      aria-label={t('dramaEpisode.mention.ariaLabel')}
    >
      <div className="drama-ep-mention-pop-tabs">
        <button
          type="button"
          className={tab === 'assets' ? 'is-active' : ''}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setTab('assets')}
        >
          <LayoutGrid size={14} />
          {t('dramaEpisode.mention.assets')}
        </button>
        <button
          type="button"
          className={tab === 'tools' ? 'is-active' : ''}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setTab('tools')
            setToolsView('list')
          }}
        >
          <Timer size={14} />
          {t('dramaEpisode.mention.tools')}
        </button>
      </div>

      {tab === 'assets' ? (
        <>
          <div className="drama-ep-mention-pop-scopes">
            <button
              type="button"
              className={scope === 'episode' ? 'is-active' : ''}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onScopeChange('episode')}
            >
              {t('dramaEpisode.mention.scopeEpisode')}
            </button>
            <button
              type="button"
              className={scope === 'series' ? 'is-active' : ''}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onScopeChange('series')}
            >
              {t('dramaEpisode.mention.scopeSeries')}
            </button>
          </div>
          <label className="drama-ep-mention-pop-search">
            <Search size={14} strokeWidth={2} aria-hidden />
            <input
              ref={searchRef}
              type="search"
              value={searchQuery}
              placeholder={t('dramaEpisode.mention.searchPlaceholder')}
              onChange={(e) => setSearchQuery(e.target.value)}
              onMouseDown={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  onActiveIndexChange(Math.min(activeIndex + 1, Math.max(filteredAssets.length - 1, 0)))
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  onActiveIndexChange(Math.max(activeIndex - 1, 0))
                } else if (e.key === 'Escape') {
                  e.preventDefault()
                  onClose()
                }
              }}
            />
          </label>
          <div className="drama-ep-mention-pop-list">
            {filteredAssets.length === 0 ? (
              <p className="drama-ep-mention-pop-empty">{t('dramaEpisode.mention.noAssets')}</p>
            ) : (
              filteredAssets.map((asset, index) => {
                const preview = resolveDramaMediaUrl(asset.cover || asset.url)
                const typeKey = asset.asset_type || asset.type
                return (
                  <button
                    key={asset.id}
                    type="button"
                    className={`drama-ep-mention-pop-item${index === activeIndex ? ' is-active' : ''}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => onActiveIndexChange(index)}
                    onClick={() => onSelectAsset(asset)}
                  >
                    <span className="drama-ep-mention-pop-thumb">
                      {preview ? (
                        <img src={preview} alt="" />
                      ) : (
                        <User size={16} strokeWidth={1.6} />
                      )}
                    </span>
                    <span className="drama-ep-mention-pop-meta">
                      <strong>{asset.name || t('dramaEpisode.assetFallback', { id: asset.id })}</strong>
                      <em>{typeLabels[typeKey] || typeKey}</em>
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </>
      ) : toolsView === 'list' ? (
        <div className="drama-ep-mention-pop-tools">
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setToolsView('duration')}
          >
            <Clapperboard size={16} />
            <span>
              <strong>{t('dramaEpisode.mention.insertDuration')}</strong>
              <em>{t('dramaEpisode.mention.remaining', { sec: remaining })}</em>
            </span>
          </button>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setToolsView('camera')}
          >
            <Aperture size={16} />
            <span>
              <strong>{t('dramaEpisode.mention.cameraTitle')}</strong>
              <em>{t('dramaEpisode.mention.cameraHint')}</em>
            </span>
          </button>
        </div>
      ) : toolsView === 'duration' ? (
        <div className="drama-ep-mention-pop-duration">
          <button
            type="button"
            className="drama-ep-mention-pop-back"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setToolsView('list')}
          >
            {t('dramaEpisode.mention.back')}
          </button>
          <div className="drama-ep-mention-pop-duration-presets">
            {DURATION_PRESET_OPTIONS.map((sec) => {
              const disabled = sec > remaining
              return (
                <button
                  key={sec}
                  type="button"
                  disabled={disabled}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => onSelectDuration(sec)}
                >
                  {sec}s
                </button>
              )
            })}
          </div>
          <div className="drama-ep-mention-pop-duration-custom">
            <input
              type="number"
              min={1}
              max={remaining || FRAGMENT_CONTENT_DURATION_MAX}
              placeholder={t('dramaEpisode.mention.customSeconds')}
              value={customDuration}
              onChange={(e) => setCustomDuration(e.target.value)}
              onMouseDown={(e) => e.stopPropagation()}
            />
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                const sec = Number(customDuration)
                if (!Number.isFinite(sec) || sec <= 0 || sec > remaining) return
                onSelectDuration(sec)
              }}
            >
              {t('dramaEpisode.mention.insert')}
            </button>
          </div>
        </div>
      ) : (
        <div className="drama-ep-mention-pop-camera">
          <button
            type="button"
            className="drama-ep-mention-pop-back"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setToolsView('list')}
          >
            {t('dramaEpisode.mention.back')}
          </button>
          {filteredCamera.length === 0 ? (
            <p className="drama-ep-mention-pop-empty">{t('dramaEpisode.mention.noCamera')}</p>
          ) : (
            <>
              {renderCameraGroup(t('dramaEpisode.mention.groupShot'), shotItems)}
              {renderCameraGroup(t('dramaEpisode.mention.groupMove'), moveItems)}
            </>
          )}
          <ul className="drama-ep-mention-pop-camera-tips">
            {dramaCameraUsageTips().map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </div>
      )}
    </div>,
    document.body,
  )
}
