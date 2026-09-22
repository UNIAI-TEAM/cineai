/** 剧情大纲：左栏分集目录 + 右栏本集创意/摘要/剧本（对齐截图样式） */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  FileText,
  Lightbulb,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Maximize2,
  Pencil,
} from 'lucide-react'
import { dramaApi, resolveDramaMediaUrl, type DramaEpisode, type DramaEpisodeBody, type DramaProject, type DramaScript } from '../../api/drama'
import { FragmentPlanSkillModal } from '../../components/drama/FragmentPlanSkillModal'
import { useI18n, type TFunction } from '../../i18n/context'
import { dialog } from '../../lib/dialog'
import {
  buildEpisodeContentUpdate,
  buildOutlineDirectory,
  episodeBodyCharLen,
  isSubstantialEpisodeBody,
  isSubstantialEpisodeCreative,
  mergeDirectoryEpisodeBodies,
  MIN_EPISODE_BODY_CHARS,
  MIN_EPISODE_CREATIVE_CHARS,
  parseEpisodeBodies,
} from './dramaWorkspaceUtils'
import { sumFragmentContentDuration } from './dramaEpisodeEditUtils'
import { OutlineScriptParseModal, OutlineScriptPreview } from './outlineScriptPreview'

type SectionKey = 'creative' | 'summary' | 'body'

/** 分集目录用的镜头合计文案 */
function formatOutlineShotDuration(sec: number, t: TFunction): string {
  if (sec <= 0) return '—'
  if (sec < 60) return `${sec}s`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return s ? t('dramaProject.durMinSec', { m, s }) : t('dramaProject.durMin', { m })
}

type OutlineEpisodePanelProps = {
  projectId: number
  script: DramaScript | null
  episodeCount: number
  summaryReady: boolean
  episodeGenerating: boolean
  imageStyleLabel?: string
  storyType?: string
  onScriptChange: (script: DramaScript) => void
  onProjectChange: (project: DramaProject) => void
  onError: (msg: string) => void
  onOpenEpisodes: () => void
  children?: (parts: { directory: ReactNode; bodies: ReactNode }) => ReactNode
}

type SectionCardProps = {
  sectionKey: SectionKey
  icon: ReactNode
  title: string
  subtitle: string
  text: string
  editing: boolean
  draft: string
  open: boolean
  busy: boolean
  /** 禁用「生成」按钮；其他集生成中时仍可编辑本集 */
  generateBusy?: boolean
  placeholder: string
  regenerateLabel: string
  onToggle: () => void
  onEdit: () => void
  onCancel: () => void
  onSave: () => void
  onDraftChange: (v: string) => void
  onRegenerate: () => void
  onCopy: () => void
  /** 剧本区：解析预览 + 分段编辑 */
  scriptPreview?: ReactNode
}

// 分区卡片：图标标题 + 编辑/生成/复制/折叠
function SectionCard({
  sectionKey,
  icon,
  title,
  subtitle,
  text,
  editing,
  draft,
  open,
  busy,
  generateBusy,
  placeholder,
  regenerateLabel,
  onToggle,
  onEdit,
  onCancel,
  onSave,
  onDraftChange,
  onRegenerate,
  onCopy,
  scriptPreview,
}: SectionCardProps) {
  const { t } = useI18n()
  const genBusy = generateBusy ?? busy
  return (
    <article className={`drama-outline-section${open ? ' is-open' : ''}`}>
      <header className="drama-outline-section-head">
        <div className="drama-outline-section-title">
          <span className={`drama-outline-section-icon is-${sectionKey}`} aria-hidden>
            {icon}
          </span>
          <div>
            <strong>{title}</strong>
            <p>{subtitle}</p>
          </div>
        </div>
        <div className="drama-outline-section-actions">
          <button type="button" className="drama-outline-text-btn" disabled={busy} onClick={onEdit}>
            <Pencil size={14} strokeWidth={2} />
            {t('dramaProject.edit')}
          </button>
          <button type="button" className="drama-outline-text-btn" disabled={genBusy} onClick={onRegenerate}>
            <RefreshCw size={14} strokeWidth={2} />
            {regenerateLabel}
          </button>
          <button type="button" className="drama-outline-text-btn" onClick={onCopy}>
            <Copy size={14} strokeWidth={2} />
            {t('common.copy')}
          </button>
          <button
            type="button"
            className="drama-outline-text-btn drama-outline-text-btn-icon"
            onClick={onToggle}
            aria-label={
              sectionKey === 'body'
                ? t('dramaProject.panel.popupParse')
                : open
                  ? t('dramaProject.collapse')
                  : t('dramaProject.expand')
            }
          >
            {sectionKey === 'body' ? (
              <Maximize2 size={14} strokeWidth={2} />
            ) : open ? (
              <ChevronUp size={14} strokeWidth={2} />
            ) : (
              <ChevronDown size={14} strokeWidth={2} />
            )}
            {sectionKey === 'body'
              ? t('dramaProject.panel.parsePreview')
              : open
                ? t('dramaProject.collapse')
                : t('dramaProject.expand')}
          </button>
        </div>
      </header>
      {open ? (
        <div className="drama-outline-section-body">
          {editing ? (
            <>
              <textarea
                className="drama-ep-section-textarea"
                value={draft}
                onChange={(e) => onDraftChange(e.target.value)}
                rows={sectionKey === 'body' ? 14 : 8}
                placeholder={placeholder}
                disabled={busy}
              />
              <div className="drama-ep-section-edit-actions">
                <button type="button" className="drama-btn-ghost" disabled={busy} onClick={onCancel}>
                  {t('common.cancel')}
                </button>
                <button type="button" className="drama-btn-primary" disabled={busy} onClick={onSave}>
                  {t('common.save')}
                </button>
              </div>
            </>
          ) : scriptPreview ? (
            scriptPreview
          ) : (
            <p className="drama-pre drama-outline-section-text">{text.trim() || placeholder}</p>
          )}
        </div>
      ) : null}
    </article>
  )
}
// 分集目录 + 本集三卡片
export function OutlineEpisodePanel({
  projectId,
  script,
  episodeCount,
  summaryReady,
  episodeGenerating,
  imageStyleLabel,
  storyType,
  onScriptChange,
  onProjectChange,
  onError,
  onOpenEpisodes,
  children,
}: OutlineEpisodePanelProps) {
  const navigate = useNavigate()
  const { t } = useI18n()
  const [activeEpisodeNumber, setActiveEpisodeNumber] = useState(1)
  const [openSections, setOpenSections] = useState<Set<SectionKey>>(
    () => new Set(['creative', 'summary', 'body']),
  )
  const [editingSection, setEditingSection] = useState<SectionKey | null>(null)
  const [sectionDraft, setSectionDraft] = useState('')
  const [titleDraft, setTitleDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [adding, setAdding] = useState(false)
  const [generatingMode, setGeneratingMode] = useState<string | null>(null)
  const [generatingEpisodeNumber, setGeneratingEpisodeNumber] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [enterSkillOpen, setEnterSkillOpen] = useState(false)
  const [localError, setLocalError] = useState('')
  const [localNotice, setLocalNotice] = useState('')
  const [scriptModalOpen, setScriptModalOpen] = useState(false)
  const [episodeCovers, setEpisodeCovers] = useState<Record<number, string>>({})
  const [episodeShotStats, setEpisodeShotStats] = useState<
    Record<number, { fragmentCount: number; totalSec: number }>
  >({})

  const episodeBodies = parseEpisodeBodies(script)
  const directoryEpisodes = buildOutlineDirectory(episodeBodies, episodeCount)
  const displayEpisodes = mergeDirectoryEpisodeBodies(directoryEpisodes, episodeBodies)
  const selected =
    displayEpisodes.find((ep) => ep.episodeNumber === activeEpisodeNumber) || displayEpisodes[0] || null

  useEffect(() => {
    if (!selected) return
    if (!displayEpisodes.some((ep) => ep.episodeNumber === activeEpisodeNumber) && displayEpisodes[0]) {
      setActiveEpisodeNumber(displayEpisodes[0].episodeNumber || 1)
    }
  }, [displayEpisodes, activeEpisodeNumber, selected])

  useEffect(() => {
    setEditingSection(null)
    setSectionDraft('')
    setTitleDraft(selected?.title || '')
    setLocalError('')
    setLocalNotice('')
    setScriptModalOpen(false)
  }, [selected?.episodeNumber])

  // 拉取已切分分集，用首镜封面/成片作目录缩略图
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        let rows: DramaEpisode[] = await dramaApi.listEpisodes(projectId)
        if (!rows.length) {
          try {
            rows = await dramaApi.seedEpisodes(projectId, false)
          } catch {
            rows = []
          }
        }
        if (cancelled) return
        const map: Record<number, string> = {}
        const shotMap: Record<number, { fragmentCount: number; totalSec: number }> = {}
        for (const ep of rows) {
          const epNo = Number(ep.params?.episodeNumber) || 0
          if (!epNo) continue
          const frags = [...(ep.fragments || [])].sort(
            (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0),
          )
          if (frags.length > 0) {
            const totalSec = frags.reduce((sum, f) => {
              const stored = Number(f.duration_sec)
              if (Number.isFinite(stored) && stored > 0) return sum + Math.round(stored)
              return sum + sumFragmentContentDuration(f.content || '')
            }, 0)
            shotMap[epNo] = { fragmentCount: frags.length, totalSec }
          }
          const first = frags.find((f) => (f.cover || '').trim() || (f.video || '').trim())
          if (!first) continue
          const raw = (first.cover || first.video || '').trim()
          if (raw) map[epNo] = resolveDramaMediaUrl(raw)
        }
        setEpisodeCovers(map)
        setEpisodeShotStats(shotMap)
      } catch {
        if (!cancelled) {
          setEpisodeCovers({})
          setEpisodeShotStats({})
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, script?.id, episodeCount])

  const selectedGenerating =
    Boolean(generatingMode) && generatingEpisodeNumber === (selected?.episodeNumber ?? null)
  const anyEpisodeGenerating = Boolean(generatingMode)
  const canAdd =
    summaryReady &&
    !episodeGenerating &&
    !adding &&
    !anyEpisodeGenerating &&
    !confirming &&
    directoryEpisodes.length < 120

  // 仅锁正在生成的那一集；其他集可浏览/编辑（单集任务全局串行，故禁止并行再点生成）
  const busy = episodeGenerating || selectedGenerating || confirming || saving || adding
  const generateBusy = episodeGenerating || anyEpisodeGenerating || confirming || saving || adding

  async function pollOptimize(tokenEpisode: number) {
    const started = Date.now()
    let lastErr: Error | null = null
    while (Date.now() - started < 8 * 60 * 1000) {
      await new Promise((r) => setTimeout(r, 2000))
      try {
        const cur = await dramaApi.getScript(projectId)
        onScriptChange(cur)
        lastErr = null
        const st = String((cur.params || {}).episode_optimize_status || '')
        const num = Number((cur.params || {}).episode_optimize_number || 0)
        if (num === tokenEpisode && st === 'completed') return cur
        if (num === tokenEpisode && st === 'failed') {
          throw new Error(String((cur.params || {}).episode_optimize_error || t('dramaProject.generateFailed')))
        }
        if (st !== 'generating') return cur
      } catch (err) {
        // 瞬时网络失败不中断轮询，避免 Failed to fetch 把界面卡在「生成中」
        lastErr = err instanceof Error ? err : new Error(t('dramaProject.panel.pollFailed'))
      }
    }
    throw lastErr || new Error(t('dramaProject.panel.genTimeout'))
  }

  async function saveBodies(nextBodies: DramaEpisodeBody[]) {
    const updated = await dramaApi.updateScript(projectId, {
      episode_content: buildEpisodeContentUpdate(script, nextBodies),
    })
    onScriptChange(updated)
    return updated
  }

  async function handleAddEpisode() {
    if (!canAdd) return
    setAdding(true)
    setLocalError('')
    try {
      const res = await dramaApi.addEpisode({ project_id: projectId })
      onScriptChange(res.script)
      const p = await dramaApi.getProject(projectId)
      onProjectChange(p)
      setActiveEpisodeNumber(res.episode_number)
      setEditingSection('creative')
      setSectionDraft('')
      onOpenEpisodes()
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.panel.addFailed')
      setLocalError(msg)
      onError(msg)
    } finally {
      setAdding(false)
    }
  }

  async function handleSaveSection(section: SectionKey) {
    if (!selected?.episodeNumber) return
    setSaving(true)
    setLocalError('')
    try {
      const num = selected.episodeNumber
      const next = displayEpisodes.map((ep) => {
        if (ep.episodeNumber !== num) return ep
        if (section === 'creative') return { ...ep, creative: sectionDraft, title: titleDraft || ep.title }
        if (section === 'summary') return { ...ep, summary: sectionDraft, title: titleDraft || ep.title }
        return { ...ep, body: sectionDraft, title: titleDraft || ep.title }
      })
      await saveBodies(next)
      setEditingSection(null)
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.saveFailed')
      setLocalError(msg)
      onError(msg)
    } finally {
      setSaving(false)
    }
  }

  async function handleGenerate(mode: 'summary' | 'body' | 'full' | 'brief') {
    if (!selected?.episodeNumber) return
    const creative = editingSection === 'creative' ? sectionDraft : selected.creative || ''
    if ((mode === 'summary' || mode === 'full') && !isSubstantialEpisodeCreative(creative)) {
      setLocalError(t('dramaProject.panel.creativeMin', { n: MIN_EPISODE_CREATIVE_CHARS }))
      return
    }
    if (mode === 'brief' && !isSubstantialEpisodeBody(selected.body)) {
      setLocalError(t('dramaProject.panel.bodyMinForBrief', { n: MIN_EPISODE_BODY_CHARS }))
      return
    }
    if (mode === 'full') {
      const ok = await dialog.confirm({
        title: t('dramaProject.panel.regenFull'),
        message: t('dramaProject.panel.regenFullMsg'),
        confirmText: t('dramaProject.regenerate'),
        tone: 'danger',
      })
      if (!ok) return
    }
    const targetEpisode = selected.episodeNumber
    setGeneratingMode(mode)
    setGeneratingEpisodeNumber(targetEpisode)
    setLocalError('')
    setLocalNotice('')
    try {
      if (editingSection === 'creative' || titleDraft !== selected.title) {
        const next = displayEpisodes.map((ep) =>
          ep.episodeNumber === targetEpisode
            ? {
                ...ep,
                creative: editingSection === 'creative' ? sectionDraft : ep.creative,
                title: titleDraft || ep.title,
              }
            : ep,
        )
        await saveBodies(next)
        setEditingSection(null)
      }
      await dramaApi.episodeScript({
        project_id: projectId,
        episode_number: targetEpisode,
        generate_mode: mode,
        creative: creative || undefined,
        title: titleDraft || selected.title,
      })
      const cur = await pollOptimize(targetEpisode)
      const created = Number((cur.params || {}).episode_optimize_assets_created || 0)
      if ((mode === 'body' || mode === 'full') && created > 0) {
        setLocalNotice(t('dramaProject.panel.assetsCreated', { n: created }))
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.generateFailed')
      setLocalError(msg)
      onError(msg)
    } finally {
      setGeneratingMode(null)
      setGeneratingEpisodeNumber(null)
    }
  }

  async function handleConfirmEnter() {
    if (!selected?.episodeNumber) return
    if (!isSubstantialEpisodeBody(selected.body)) {
      setLocalError(t('dramaProject.panel.bodyMinForEnter', { n: MIN_EPISODE_BODY_CHARS }))
      return
    }
    setLocalError('')
    setConfirming(true)
    try {
      // 本集已有分镜：直接进入，不再弹 Skill / 重切
      const rows = await dramaApi.listEpisodes(projectId)
      const existing = rows.find(
        (ep) => Number(ep.params?.episodeNumber) === Number(selected.episodeNumber),
      )
      if (existing && (existing.fragments || []).length > 0) {
        navigate(`/drama/projects/${projectId}/episodes/${existing.id}`)
        return
      }
      setEnterSkillOpen(true)
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.enterFailed')
      setLocalError(msg)
      onError(msg)
    } finally {
      setConfirming(false)
    }
  }

  // 首次进入：确认剧本 + 按所选 Skill 做 AI 分镜
  async function startEnterWithSkills(skillIds: number[]) {
    if (!selected?.episodeNumber) return
    setEnterSkillOpen(false)
    setConfirming(true)
    setLocalError('')
    try {
      const res = await dramaApi.confirmEpisodeFromScript({
        project_id: projectId,
        episode_number: selected.episodeNumber,
      })
      const episodeId = res.episode.id
      try {
        await dramaApi.planEpisodeFragments(episodeId, {
          force: true,
          fallback_rules: true,
          skill_ids: skillIds,
        })
      } catch (planErr) {
        onError(planErr instanceof Error ? planErr.message : t('dramaProject.panel.planQueueFailed'))
      }
      navigate(`/drama/projects/${projectId}/episodes/${episodeId}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.enterFailed')
      setLocalError(msg)
      onError(msg)
    } finally {
      setConfirming(false)
    }
  }

  async function handleSaveScenes(nextBody: string) {
    if (!selected?.episodeNumber) return
    setSaving(true)
    setLocalError('')
    try {
      const num = selected.episodeNumber
      const next = displayEpisodes.map((ep) =>
        ep.episodeNumber === num ? { ...ep, body: nextBody, title: titleDraft || ep.title } : ep,
      )
      await saveBodies(next)
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('dramaProject.saveFailed')
      setLocalError(msg)
      onError(msg)
      throw err
    } finally {
      setSaving(false)
    }
  }

  function toggleSection(key: SectionKey) {
    if (key === 'body') {
      setScriptModalOpen(true)
      setOpenSections((prev) => new Set(prev).add('body'))
      return
    }
    setOpenSections((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function startEdit(section: SectionKey) {
    if (!selected) return
    setEditingSection(section)
    setSectionDraft(
      section === 'creative'
        ? selected.creative || ''
        : section === 'summary'
          ? selected.summary || ''
          : selected.body || '',
    )
    setOpenSections((prev) => new Set(prev).add(section))
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text || '')
    } catch {
      setLocalError(t('dramaProject.copyFailed'))
    }
  }

  const metaTags = useMemo(() => {
    const tags: string[] = []
    if (storyType) tags.push(storyType)
    if (selected?.origin === 'manual') tags.push(t('dramaProject.panel.tagManual'))
    else if (selected?.body) tags.push(t('dramaProject.panel.tagAuto'))
    return tags
  }, [storyType, selected, t])

  const bodyReady = isSubstantialEpisodeBody(selected?.body)
  const charHint = selected
    ? [
        selected.creative
          ? t('dramaProject.panel.charCreative', { n: episodeBodyCharLen(selected.creative) })
          : null,
        selected.summary
          ? t('dramaProject.panel.charSummary', { n: episodeBodyCharLen(selected.summary) })
          : null,
        selected.body
          ? t('dramaProject.panel.charBody', { n: episodeBodyCharLen(selected.body) })
          : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : ''

  const directory = (
    <aside className="drama-outline-sidebar">
      <div className="drama-outline-sidebar-head">
        <div>
          <h3>{t('dramaProject.episodeDir')}</h3>
          <p>{t('dramaProject.episodeTotal', { n: directoryEpisodes.length })}</p>
        </div>
        {summaryReady ? (
          <button
            type="button"
            className="drama-outline-add-btn"
            disabled={!canAdd}
            onClick={() => void handleAddEpisode()}
          >
            <Plus size={14} strokeWidth={2.5} />
            {adding ? t('dramaProject.panel.adding') : t('dramaProject.panel.add')}
          </button>
        ) : null}
      </div>
      <ul className="drama-outline-ep-list">
        {directoryEpisodes.map((ep) => {
          const body = displayEpisodes.find((x) => x.episodeNumber === ep.episodeNumber)
          const ready = isSubstantialEpisodeBody(body?.body)
          const active = activeEpisodeNumber === ep.episodeNumber
          const shot = episodeShotStats[ep.episodeNumber || 0]
          const statusLabel = shot && shot.fragmentCount > 0 && shot.totalSec > 0
            ? t('dramaProject.panel.shotMeta', {
                n: shot.fragmentCount,
                dur: formatOutlineShotDuration(shot.totalSec, t),
              })
            : ready
              ? t('dramaProject.panel.bodyReady')
              : body?.creative
                ? t('dramaProject.panel.needBody')
                : t('dramaProject.panel.needCreative')
          return (
            <li key={ep.episodeNumber}>
              <button
                type="button"
                className={`drama-outline-ep-card${active ? ' is-active' : ''}`}
                onClick={() => {
                  onOpenEpisodes()
                  setActiveEpisodeNumber(ep.episodeNumber)
                }}
              >
                <span className="drama-outline-ep-thumb" aria-hidden>
                  {(() => {
                    const cover = episodeCovers[ep.episodeNumber || 0]
                    if (!cover) return ep.episodeNumber
                    if (/\.(mp4|webm|mov)(\?|$)/i.test(cover)) {
                      return <video src={cover} muted playsInline preload="metadata" />
                    }
                    return <img src={cover} alt="" />
                  })()}
                </span>
                <span className="drama-outline-ep-meta">
                  <strong>{t('dramaProject.episodeNo', { n: ep.episodeNumber })}</strong>
                  <small>{ep.title || t('dramaProject.untitled')}</small>
                  <em className={shot && shot.fragmentCount > 0 ? 'is-shot' : undefined}>
                    {statusLabel}
                  </em>
                </span>
                <span className="drama-outline-ep-more" aria-hidden>
                  <MoreHorizontal size={16} />
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </aside>
  )

  const bodies = !selected ? (
    <div className="drama-outline-detail-empty">
      <p>
        {summaryReady ? t('dramaProject.panel.emptyReady') : t('dramaProject.panel.emptyNeedSummary')}
      </p>
    </div>
  ) : (
    <section className="drama-outline-detail">
      <header className="drama-outline-detail-head">
        <div className="drama-outline-detail-title">
          {editingSection ? (
            <input
              className="drama-title-input"
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              placeholder={t('dramaProject.panel.titlePlaceholder')}
            />
          ) : (
            <h2>
              {selected.title
                ? t('dramaProject.panel.headingWithTitle', {
                    n: selected.episodeNumber ?? '',
                    title: selected.title,
                  })
                : t('dramaProject.episodeNo', { n: selected.episodeNumber ?? '' })}
            </h2>
          )}
          {imageStyleLabel ? <span className="drama-outline-style-badge">{imageStyleLabel}</span> : null}
          <div className="drama-outline-detail-meta">
            {charHint ? <span>{charHint}</span> : <span>{t('dramaProject.panel.noContent')}</span>}
            {metaTags.map((tag) => (
              <span key={tag} className="drama-outline-tag">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="drama-outline-detail-actions">
          <span className={`drama-outline-saved${bodyReady ? ' is-ready' : ''}`}>
            <Check size={14} strokeWidth={2.5} />
            {bodyReady
              ? t('dramaProject.panel.readyForStoryboard')
              : saving
                ? t('dramaProject.panel.savingShort')
                : t('dramaProject.panel.synced')}
          </span>
          {bodyReady &&
          (!isSubstantialEpisodeCreative(selected.creative) ||
            episodeBodyCharLen(selected.summary) < 40) ? (
            <button
              type="button"
              className="drama-btn-ghost"
              disabled={generateBusy}
              onClick={() => void handleGenerate('brief')}
            >
              {selectedGenerating && generatingMode === 'brief'
                ? t('dramaProject.panel.filling')
                : t('dramaProject.panel.fillBrief')}
            </button>
          ) : null}
          <button
            type="button"
            className="drama-outline-regen-btn"
            disabled={generateBusy || !isSubstantialEpisodeCreative(selected.creative)}
            onClick={() => void handleGenerate('full')}
          >
            <RefreshCw size={15} strokeWidth={2.25} />
            {selectedGenerating && generatingMode === 'full'
              ? t('dramaProject.generating')
              : t('dramaProject.panel.regenFull')}
          </button>
          <button
            type="button"
            className="drama-btn-ghost"
            disabled={busy || !bodyReady}
            onClick={() => void handleConfirmEnter()}
          >
            {confirming ? t('dramaProject.entering') : t('dramaProject.enter')}
          </button>
        </div>
      </header>

      {localError ? <p className="drama-error">{localError}</p> : null}
      {localNotice ? <p className="drama-outline-notice">{localNotice}</p> : null}
      {episodeGenerating ? <p className="drama-loader">{t('dramaProject.panel.allGenerating')}</p> : null}
      {selectedGenerating ? (
        <p className="drama-loader">
          {t('dramaProject.panel.thisGenerating', {
            mode: t(`dramaProject.panel.modes.${generatingMode}`),
          })}
        </p>
      ) : anyEpisodeGenerating && generatingEpisodeNumber ? (
        <p className="drama-loader">
          {t('dramaProject.panel.otherGenerating', { n: generatingEpisodeNumber })}
        </p>
      ) : null}

      <div className="drama-outline-sections">
        <SectionCard
          sectionKey="creative"
          icon={<Lightbulb size={18} strokeWidth={1.9} />}
          title={t('dramaProject.panel.creativeTitle')}
          subtitle={t('dramaProject.panel.creativeSub')}
          text={selected.creative || ''}
          editing={editingSection === 'creative'}
          draft={sectionDraft}
          open={openSections.has('creative')}
          busy={busy}
          generateBusy={generateBusy}
          placeholder={t('dramaProject.panel.creativePlaceholder', { n: MIN_EPISODE_CREATIVE_CHARS })}
          regenerateLabel={
            selectedGenerating && generatingMode === 'brief'
              ? t('dramaProject.panel.filling')
              : selectedGenerating && generatingMode === 'summary'
                ? t('dramaProject.generating')
                : isSubstantialEpisodeCreative(selected.creative)
                  ? t('dramaProject.panel.genSummary')
                  : t('dramaProject.panel.fillBrief')
          }
          onToggle={() => toggleSection('creative')}
          onEdit={() => startEdit('creative')}
          onCancel={() => setEditingSection(null)}
          onSave={() => void handleSaveSection('creative')}
          onDraftChange={setSectionDraft}
          onRegenerate={() =>
            void handleGenerate(
              isSubstantialEpisodeCreative(selected.creative) ? 'summary' : 'brief',
            )
          }
          onCopy={() => void copyText(selected.creative || '')}
        />
        <SectionCard
          sectionKey="summary"
          icon={<BookOpen size={18} strokeWidth={1.9} />}
          title={t('dramaProject.panel.summaryTitle')}
          subtitle={t('dramaProject.panel.summarySub')}
          text={selected.summary || ''}
          editing={editingSection === 'summary'}
          draft={sectionDraft}
          open={openSections.has('summary')}
          busy={busy}
          generateBusy={generateBusy}
          placeholder={t('dramaProject.panel.summaryPlaceholder')}
          regenerateLabel={
            selectedGenerating && generatingMode === 'brief'
              ? t('dramaProject.panel.filling')
              : selectedGenerating && generatingMode === 'summary'
                ? t('dramaProject.generating')
                : isSubstantialEpisodeCreative(selected.creative)
                  ? t('dramaProject.regenerate')
                  : t('dramaProject.panel.fillBrief')
          }
          onToggle={() => toggleSection('summary')}
          onEdit={() => startEdit('summary')}
          onCancel={() => setEditingSection(null)}
          onSave={() => void handleSaveSection('summary')}
          onDraftChange={setSectionDraft}
          onRegenerate={() =>
            void handleGenerate(
              isSubstantialEpisodeCreative(selected.creative) ? 'summary' : 'brief',
            )
          }
          onCopy={() => void copyText(selected.summary || '')}
        />
        <SectionCard
          sectionKey="body"
          icon={<FileText size={18} strokeWidth={1.9} />}
          title={t('dramaProject.panel.bodyTitle')}
          subtitle={t('dramaProject.panel.bodySub')}
          text={selected.body || ''}
          editing={editingSection === 'body'}
          draft={sectionDraft}
          open={openSections.has('body')}
          busy={busy}
          generateBusy={generateBusy}
          placeholder={t('dramaProject.panel.bodyPlaceholder', { n: MIN_EPISODE_BODY_CHARS })}
          regenerateLabel={
            selectedGenerating && generatingMode === 'body'
              ? t('dramaProject.generating')
              : t('dramaProject.panel.genBody')
          }
          onToggle={() => toggleSection('body')}
          onEdit={() => startEdit('body')}
          onCancel={() => setEditingSection(null)}
          onSave={() => void handleSaveSection('body')}
          onDraftChange={setSectionDraft}
          onRegenerate={() => void handleGenerate('body')}
          onCopy={() => void copyText(selected.body || '')}
          scriptPreview={
            <OutlineScriptPreview
              text={selected.body || ''}
              empty={t('dramaProject.panel.bodyPlaceholder', { n: MIN_EPISODE_BODY_CHARS })}
              busy={busy}
              shotStats={episodeShotStats[selected.episodeNumber || 0] || null}
              onSaveScenes={handleSaveScenes}
            />
          }
        />
      </div>
      <OutlineScriptParseModal
        open={scriptModalOpen}
        onClose={() => setScriptModalOpen(false)}
        title={t('dramaProject.panel.parseTitle', { n: selected.episodeNumber ?? '' })}
        text={selected.body || ''}
      />
    </section>
  )

  if (children) {
    return (
      <>
        {children({ directory, bodies })}
        <FragmentPlanSkillModal
          open={enterSkillOpen}
          title={t('dramaProject.enter')}
          message={t('dramaProject.panel.enterMsg')}
          confirmText={confirming ? t('dramaProject.entering') : t('dramaProject.startPlan')}
          onCancel={() => {
            if (!confirming) setEnterSkillOpen(false)
          }}
          onConfirm={(skillIds) => void startEnterWithSkills(skillIds)}
        />
      </>
    )
  }
  return (
    <div className="drama-outline drama-outline-v2">
      {directory}
      <div className="drama-outline-main">{bodies}</div>
      <FragmentPlanSkillModal
        open={enterSkillOpen}
        title={t('dramaProject.enter')}
        message={t('dramaProject.panel.enterMsg')}
        confirmText={confirming ? t('dramaProject.entering') : t('dramaProject.startPlan')}
        onCancel={() => {
          if (!confirming) setEnterSkillOpen(false)
        }}
        onConfirm={(skillIds) => void startEnterWithSkills(skillIds)}
      />
    </div>
  )
}
