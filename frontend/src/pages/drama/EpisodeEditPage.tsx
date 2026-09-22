/** 分集编辑：复刻原项目四栏布局（资产 / 脚本 / 预览 / 故事板） */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  dramaApi,
  resolveDramaMediaUrl,
  type DramaAsset,
  type DramaEpisode,
  type DramaFragment,
} from '../../api/drama'
import { type ImageStyleId } from '../../lib/dramaImageStyles'
import {
  RATIO_OPTIONS,
  buildFragmentRefStripItems,
  collectFragmentAssetIds,
  extractAssetIds,
  filterEpisodeAssets,
  formatFragLabel,
  fragmentQueueBadgeLabel,
  isFragmentGenerationBusy,
  normalizeAssetTab,
  readFragmentGenerationStatus,
  readFragmentVideoVersions,
  resolveFragmentDurationSec,
  type AssetScope,
  type AssetTab,
} from './dramaEpisodeEditUtils'
import {
  enqueueEpisodeVideoJobs,
  ensureEpisodeVideoStatusPoll,
  FRAGMENT_VIDEO_SUBTYPE,
  subscribeEpisodeGenerateStatus,
  syncEpisodeVideoJobs,
  useDramaGenQueue,
  videoJobId,
  type DramaGenJob,
} from '../../lib/dramaGenQueue'
import {
  collectDramaGenerateGateIssues,
  formatDramaGateMessage,
} from '../../lib/dramaEpisodeScriptValidate'
import { DRAMA_VOICE_BINDING_ENABLED } from '../../lib/dramaVoiceBinding'
import BillingErrorNotice from '../../components/billing/BillingErrorNotice'
import { dialog } from '../../lib/dialog'
import {
  formatProjectOutputLabel,
  readEpisodeAspectRatio,
  readEpisodeResolution,
} from '../../lib/dramaProjectOutputSettings'
import { DramaFragmentClipSpec } from '../../components/drama/DramaFragmentClipSpec'
import { FragmentPlanSkillModal } from '../../components/drama/FragmentPlanSkillModal'
import { DramaGenTaskDetail } from '../../components/drama/DramaGenTaskDetail'
import { CircleAlert } from 'lucide-react'
import { useDramaImageGenQueue } from '../../hooks/useDramaImageGenQueue'
import { useMediaModelsCatalog } from '../../hooks/useMediaModelsCatalog'
import { enqueueDramaImageGen } from '../../lib/dramaImageGenQueue'
import { formatDramaGenError } from '../../lib/dramaGenError'
import { defaultOptionsForAssetKind } from '../../lib/dramaGenerationOptions'
import { dramaAssetImageGenButtonLabel } from '../../lib/dramaAssetImage'
import { readVisualPrompt } from '../../lib/dramaVisualPrompt'
import { generateAndBindCharacterVoice } from '../../lib/characterVoiceGenerate'
import { getImageStyleId } from './dramaWorkspaceUtils'
import { EpisodeEditAssetPanel } from './EpisodeEditAssetPanel'
import { EpisodeEditHeaderControls } from './EpisodeEditHeaderControls'
import { EpisodeEditPromptEditor } from './EpisodeEditPromptEditor'
import { EpisodeEditReferenceStrip } from './EpisodeEditReferenceStrip'
import { EpisodeEditSidePane } from './EpisodeEditSidePane'
import {
  GlobalAssetPickerModal,
  importGlobalAssetToProject,
} from './GlobalAssetPickerModal'
import {
  applySubtitleModeToFragments,
  subtitleModeUsesModelOutput,
  type DramaSubtitleMode,
} from '../../lib/dramaSubtitleBoard'
import {
  applyCharacterIntroModeToFragments,
  characterIntroModeEnabled,
  type DramaCharacterIntroMode,
} from '../../lib/dramaCharacterIntro'
import {
  readEffectiveCharacterIntroMode,
  readEffectiveSubtitleMode,
} from '../../lib/dramaProjectGlobalSettings'
import {
  CharacterVoiceBindModal,
  readAssetVoiceBinding,
} from './CharacterVoiceBindModal'
import { DramaAssetDetailModal } from './DramaAssetDetailModal'
import { buildEpisodeDirItems, DramaEpisodeDir } from './DramaEpisodeDir'
import RequireAuth from './RequireAuth'
import { useI18n } from '../../i18n/context'
import { translate } from '../../i18n/translate'
import './drama.css'

export default function EpisodeEditPage() {
  return (
    <RequireAuth>
      <EpisodeEditInner />
    </RequireAuth>
  )
}

function readFragmentPlanStatus(ep: DramaEpisode | null): string {
  // 优先读取统一任务中心中的分镜规划任务；旧 params 状态作为兜底
  const active = (ep?.active_tasks || []).find((task) => task.task_type === 'fragment_plan')
  if (
    active &&
    !active.cancel_requested &&
    ['pending', 'leased', 'running', 'awaiting_poll', 'awaiting_review'].includes(active.status)
  ) {
    return 'generating'
  }
  const st = ep?.params?.fragment_plan_status
  return typeof st === 'string' ? st : ''
}

// 统一解析项目参数里的布尔值，兼容历史字符串/数字写法。
function coerceProjectBool(value: unknown, defaultValue: boolean): boolean {
  if (value == null) return defaultValue
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (['1', 'true', 'yes', 'on'].includes(normalized)) return true
    if (['0', 'false', 'no', 'off', ''].includes(normalized)) return false
  }
  return Boolean(value)
}

// 分集编辑页主体
function EpisodeEditInner() {
  const { projectId, episodeId } = useParams()
  const pid = Number(projectId)
  const eid = Number(episodeId)
  const navigate = useNavigate()
  const { t, m, locale } = useI18n()
  /*
   * episode 分集
   * fragments 分镜
   * assets 资产
   * selectedIndex 当前分镜
   * assetScope / assetTab 侧栏筛选
   * editing 是否编辑模式
   * videoStyleId / modelId / aspectRatio 生成参数（UI）
   * busy / status / error 状态
   */
  const [episode, setEpisode] = useState<DramaEpisode | null>(null)
  const [episodeList, setEpisodeList] = useState<DramaEpisode[]>([])
  const [fragments, setFragments] = useState<DramaFragment[]>([])
  const [assets, setAssets] = useState<DramaAsset[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [assetScope, setAssetScope] = useState<AssetScope>('episode')
  const [assetTab, setAssetTab] = useState<AssetTab | null>('character')
  const [editing, setEditing] = useState(false)
  const [videoStyleId, setVideoStyleId] = useState<ImageStyleId | ''>('')
  const [modelId, setModelId] = useState('')
  const mediaCatalog = useMediaModelsCatalog()
  const [aspectRatio, setAspectRatio] = useState<(typeof RATIO_OPTIONS)[number]>('9:16')
  // subtitleMode 本集字幕方式：模型自出 / 后期拼接（默认后期）
  const [subtitleMode, setSubtitleMode] = useState<DramaSubtitleMode>('post')
  // characterIntroMode 本集人物介绍叠字：模型叠字 / 关闭（默认关闭）
  const [characterIntroMode, setCharacterIntroMode] = useState<DramaCharacterIntroMode>('off')
  // linkLastFrame 是否用上一镜尾帧作本镜首帧（写入 project.params，默认开启）
  const [linkLastFrame, setLinkLastFrame] = useState(true)
  // projectParams 项目 params 缓存（镜间衔接 + 分集输出规格回退）
  const [projectParams, setProjectParams] = useState<Record<string, unknown>>({})
  // episodeParams 分集 params 缓存（画幅 / 清晰度写入此处）
  const [episodeParams, setEpisodeParams] = useState<Record<string, unknown>>({})
  // planModalOpen AI 重新分镜确认（含 Skill 勾选）
  const [planModalOpen, setPlanModalOpen] = useState(false)
  const [previewVersionId, setPreviewVersionId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  // planning AI 分镜进行中（不用已翻译的 status 文案判断，切换语言后仍正确）
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState('')
  const [characterVoiceBusyIds, setCharacterVoiceBusyIds] = useState<Set<number>>(() => new Set())
  /*
   * detailAsset 左侧资产详情（编辑/重新生成/上传）
   * voiceBindAsset 音色绑定弹窗目标
   * imageGenQueue 全局生图队列快照
   */
  const [detailAsset, setDetailAsset] = useState<DramaAsset | null>(null)
  const [voiceBindAsset, setVoiceBindAsset] = useState<DramaAsset | null>(null)
  /** failReasonJob 底部分镜感叹号打开的失败原因 */
  const [failReasonJob, setFailReasonJob] = useState<DramaGenJob | null>(null)
  // assetCreateBusy / libraryPickerOpen 侧栏新建与导入
  const [assetCreateBusy, setAssetCreateBusy] = useState(false)
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false)
  const imageGenQueue = useDramaImageGenQueue()
  const dramaGenQueue = useDramaGenQueue()
  const applyStatusRef = useRef<(st: Awaited<ReturnType<typeof dramaApi.generateStatus>>) => Awaited<
    ReturnType<typeof dramaApi.generateStatus>
  >>(() => ({ episode_id: 0, done: 0, failed: 0, running: 0, total: 0, tasks: [], fragments: [] }))
  const reloadRef = useRef<() => Promise<void>>(async () => {})
  const projectParamsRef = useRef<Record<string, unknown>>({})
  const episodeParamsRef = useRef<Record<string, unknown>>({})

  useEffect(() => {
    // 目录到达后，把旧 Kie/方舟 id 换成后台默认视频模型
    if (!mediaCatalog) return
    const ids = mediaCatalog.video_models.map((m) => m.id)
    if (!ids.length) return
    setModelId((prev) => (ids.includes(prev) ? prev : mediaCatalog.defaults.video_model || ids[0]))
  }, [mediaCatalog])

  const selected = fragments[selectedIndex] || null
  const selectedDuration = selected?.duration_sec ?? 8
  // generatingIds 当前分集排队/生成中的分镜 id
  const generatingIds = useMemo(() => {
    const ids = new Set<number>()
    for (const task of episode?.active_tasks || []) {
      if (
        typeof task.episode_id === 'number' &&
        task.episode_id > 0 &&
        task.episode_id !== eid
      ) {
        continue
      }
      if (
        task.task_type === 'fragment_video' &&
        typeof task.fragment_id === 'number' &&
        !task.cancel_requested &&
        ['pending', 'leased', 'running', 'awaiting_poll', 'awaiting_review'].includes(task.status)
      ) {
        // 成片已 done：忽略残留活跃任务，避免徽标长期「生成中」
        const frag = fragments.find((f) => f.id === task.fragment_id)
        if (frag && readFragmentGenerationStatus(frag).status === 'done') continue
        if (!frag) continue
        ids.add(task.fragment_id)
      }
    }
    for (const frag of fragments) {
      if (!frag.id) continue
      const st = readFragmentGenerationStatus(frag).status
      if (st === 'done') continue
      if (isFragmentGenerationBusy(st)) ids.add(frag.id)
    }
    return ids
  }, [eid, fragments, episode?.active_tasks])
  // anyFragmentGenerating 本集是否有分镜在排队/生成（不锁编辑，仅锁批量生成）
  const anyFragmentGenerating = generatingIds.size > 0
  // selectedIsGenerating 当前选中镜是否正在生成
  const selectedIsGenerating = Boolean(selected?.id && generatingIds.has(selected.id))
  // selectedHasVideo 当前镜是否已有成片（用于「重新生成」文案）
  const selectedHasVideo = Boolean(selected?.video)
  // selectedVersions 当前镜历史成片
  const selectedVersions = useMemo(() => readFragmentVideoVersions(selected), [selected])
  // previewVersion 当前选中待预览的历史成片
  const previewVersion = useMemo(
    () => selectedVersions.find((ver) => ver.id === previewVersionId) ?? null,
    [previewVersionId, selectedVersions],
  )
  const previewVideoUrl = previewVersion ? resolveDramaMediaUrl(previewVersion.video) : null
  const previewPosterUrl = previewVersion?.cover ? resolveDramaMediaUrl(previewVersion.cover) : null
  // generateAllLocked 仅提交入队时锁定，生成过程不阻塞编辑
  const generateAllLocked = busy
  // planFragmentsLocked 仅本集有视频生成或 AI 分镜进行中时锁定
  const planFragmentsLocked =
    busy || anyFragmentGenerating || readFragmentPlanStatus(episode) === 'generating'
  const selectedRefIds = useMemo(
    () => new Set(collectFragmentAssetIds(selected)),
    [selected],
  )
  const selectedRefItems = useMemo(
    () =>
      buildFragmentRefStripItems(selected, assets, resolveDramaMediaUrl, (asset) => {
        const voice = readAssetVoiceBinding(asset)
        return voice ? { label: voice.label, url: voice.url } : null
      }),
    // locale：片段标签 / 资产兜底名按界面语言生成，切换语言时需重算
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, assets, locale],
  )
  // selectedGateIssues 当前镜脚本/资产门禁（编辑区即时提示）
  const selectedGateIssues = useMemo(() => {
    const { blocking, warnings } = collectDramaGenerateGateIssues(selected, assets)
    return [...blocking, ...warnings]
  }, [selected, assets])

  // prevLastFrameUrl 上一镜已落盘尾帧（衔接触发条件；兼容 generation / 历史版本字段）
  const prevLastFrameUrl = useMemo(() => {
    if (selectedIndex <= 0) return ''
    const prev = fragments[selectedIndex - 1]
    const params = prev?.params
    if (!params || typeof params !== 'object') return ''
    const rec = params as Record<string, unknown>
    const fromTop = rec.lastFrameUrl
    if (typeof fromTop === 'string' && fromTop.trim()) return fromTop.trim()
    const gen = rec.generation
    if (gen && typeof gen === 'object') {
      const fromGen = (gen as Record<string, unknown>).lastFrameUrl
      if (typeof fromGen === 'string' && fromGen.trim()) return fromGen.trim()
    }
    const versions = readFragmentVideoVersions(prev)
    for (const ver of versions) {
      if (ver.lastFrameUrl && ver.lastFrameUrl.trim()) return ver.lastFrameUrl.trim()
    }
    return ''
  }, [fragments, selectedIndex])

  // 开启尾帧衔接时：仅上一镜从未生成过才禁止；上一镜在生成/排队时本镜可入队等待
  const continuityBlockedReason = useMemo(() => {
    if (!linkLastFrame || selectedIndex <= 0) return ''
    const prev = fragments[selectedIndex - 1]
    if (!prev) return t('dramaEpisode.page.continuityNoPrev')
    if (prev.id && generatingIds.has(prev.id)) {
      return ''
    }
    const prevDone =
      Boolean((prev.video || '').trim()) ||
      readFragmentGenerationStatus(prev).status === 'done' ||
      Boolean(prevLastFrameUrl)
    if (!prevDone) {
      return t('dramaEpisode.page.continuityNeedPrev')
    }
    return ''
  }, [linkLastFrame, selectedIndex, fragments, generatingIds, prevLastFrameUrl, t])

  const continuityQueueHint = useMemo(() => {
    if (!linkLastFrame || selectedIndex <= 0) return ''
    const prev = fragments[selectedIndex - 1]
    if (!prev?.id || !generatingIds.has(prev.id)) return ''
    return t('dramaEpisode.page.continuityPrevRunning')
  }, [linkLastFrame, selectedIndex, fragments, generatingIds, t])

  // selectedGenerateLocked 仅锁当前镜的「生成」按钮（含尾帧衔接门禁）
  const selectedGenerateLocked = busy || selectedIsGenerating || Boolean(continuityBlockedReason)

  // 持久化镜间衔接开关到项目 params，并让后端重排未开始任务
  async function handleLinkLastFrameChange(enabled: boolean) {
    const prevEnabled = linkLastFrame
    const prevParams = projectParams
    const nextParams = { ...projectParams, linkLastFrame: enabled }
    setLinkLastFrame(enabled)
    setProjectParams(nextParams)
    try {
      const updated = await dramaApi.updateProject(pid, { params: nextParams })
      const updatedParams =
        updated.params && typeof updated.params === 'object'
          ? (updated.params as Record<string, unknown>)
          : (nextParams as Record<string, unknown>)
      setProjectParams(updatedParams)
      setLinkLastFrame(coerceProjectBool(updatedParams.linkLastFrame ?? updatedParams.link_last_frame, enabled))
      // 刷新本集任务态，让底部分镜条立刻反映串行/并行调整
      try {
        const ep = await dramaApi.getEpisode(eid)
        setEpisode(ep)
        if (Array.isArray(ep.fragments)) setFragments(ep.fragments)
      } catch {
        /* ignore refresh errors */
      }
      setStatus(
        enabled
          ? t('dramaEpisode.page.linkOn')
          : t('dramaEpisode.page.linkOff'),
      )
    } catch (err) {
      setLinkLastFrame(prevEnabled)
      setProjectParams(prevParams)
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.linkSaveFailed'))
    }
  }

  // 持久化本集画幅 / 清晰度到 episode.params；已有成片时提示重新生成
  async function handleEpisodeOutputChange(nextParams: Record<string, unknown>) {
    const prevRatio = readEpisodeAspectRatio(episodeParams, projectParams)
    const prevRes = readEpisodeResolution(episodeParams, projectParams)
    const nextRatio = readEpisodeAspectRatio(nextParams, projectParams)
    const nextRes = readEpisodeResolution(nextParams, projectParams)
    if (prevRatio === nextRatio && prevRes === nextRes) return

    const prevLabel = formatProjectOutputLabel(prevRatio, prevRes)
    const nextLabel = formatProjectOutputLabel(nextRatio, nextRes)
    const generatedCount = fragments.filter((frag) => Boolean(frag.video)).length
    const ok = await dialog.confirm({
      title: t('dramaEpisode.page.outputTitle'),
      message:
        generatedCount > 0
          ? t('dramaEpisode.page.outputMsgRegen', { prev: prevLabel, next: nextLabel, count: generatedCount })
          : t('dramaEpisode.page.outputMsg', { prev: prevLabel, next: nextLabel }),
      confirmText: generatedCount > 0 ? t('dramaEpisode.page.outputConfirmRegen') : t('common.save'),
      cancelText: t('common.cancel'),
      tone: generatedCount > 0 ? 'danger' : 'default',
    })
    if (!ok) return

    const prevParams = episodeParams
    setEpisodeParams(nextParams)
    episodeParamsRef.current = nextParams
    setAspectRatio(nextRatio)
    try {
      const updated = await dramaApi.updateEpisode(eid, { params: nextParams })
      const updatedParams =
        updated.params && typeof updated.params === 'object' && !Array.isArray(updated.params)
          ? (updated.params as Record<string, unknown>)
          : nextParams
      setEpisode(updated)
      setEpisodeParams(updatedParams)
      episodeParamsRef.current = updatedParams
      setAspectRatio(readEpisodeAspectRatio(updatedParams, projectParams))
      setStatus(
        generatedCount > 0
          ? t('dramaEpisode.page.outputUpdatedRegen', { label: nextLabel })
          : t('dramaEpisode.page.outputUpdated', { label: nextLabel }),
      )
      setError('')
      if (generatedCount > 0) {
        await generateAll({ forceRegen: true, skipConfirm: true })
      }
    } catch (err) {
      setEpisodeParams(prevParams)
      episodeParamsRef.current = prevParams
      setAspectRatio(readEpisodeAspectRatio(prevParams, projectParams))
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.outputSaveFailed'))
      throw err
    }
  }

  // 持久化本集字幕方式，并动态改写当前分镜里的字幕提示词
  async function handleEpisodeSubtitleChange(mode: DramaSubtitleMode) {
    if (mode === subtitleMode) return
    const prevParams = episodeParams
    const prevFragments = fragments
    const nextParams = {
      ...episodeParams,
      subtitleMode: mode,
      subtitleEnabled: subtitleModeUsesModelOutput(mode),
    }
    const nextFragments = applySubtitleModeToFragments(fragments, mode)
    setSubtitleMode(mode)
    setEpisodeParams(nextParams)
    episodeParamsRef.current = nextParams
    setFragments(nextFragments)
    try {
      const updated = await dramaApi.updateEpisode(eid, { params: nextParams })
      const updatedParams =
        updated.params && typeof updated.params === 'object' && !Array.isArray(updated.params)
          ? (updated.params as Record<string, unknown>)
          : nextParams
      setEpisode(updated)
      setEpisodeParams(updatedParams)
      episodeParamsRef.current = updatedParams
      setSubtitleMode(readEffectiveSubtitleMode(updatedParams, projectParamsRef.current))
      const contentChanged = nextFragments.some(
        (frag, index) => frag.content !== prevFragments[index]?.content,
      )
      if (contentChanged) {
        const ep = await dramaApi.saveFragments(
          eid,
          nextFragments.map((f, i) => {
            const prevFragParams =
              f.params && typeof f.params === 'object' && !Array.isArray(f.params)
                ? (f.params as Record<string, unknown>)
                : {}
            return {
              id: typeof f.id === 'number' && f.id > 0 ? f.id : undefined,
              sort_order: i,
              content: f.content,
              cover: f.cover,
              video: f.video,
              duration_sec: resolveFragmentDurationSec(f.content, f.duration_sec),
              params: { ...prevFragParams, user_edited: true },
              asset_ids: f.asset_ids || [],
            }
          }),
        )
        setEpisode(ep)
        setFragments(ep.fragments || nextFragments)
      }
      setStatus(
        mode === 'model'
          ? t('dramaEpisode.page.subtitleToModel')
          : t('dramaEpisode.page.subtitleToPost'),
      )
      setError('')
    } catch (err) {
      setSubtitleMode(readEffectiveSubtitleMode(prevParams, projectParamsRef.current))
      setEpisodeParams(prevParams)
      episodeParamsRef.current = prevParams
      setFragments(prevFragments)
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.subtitleSaveFailed'))
    }
  }

  // 持久化本集人物介绍叠字开关，并动态去掉当前分镜里的介绍行
  async function handleEpisodeCharacterIntroChange(mode: DramaCharacterIntroMode) {
    if (mode === characterIntroMode) return
    const prevParams = episodeParams
    const prevFragments = fragments
    const nextParams = {
      ...episodeParams,
      characterIntroMode: mode,
      characterIntroEnabled: characterIntroModeEnabled(mode),
    }
    const nextFragments = applyCharacterIntroModeToFragments(fragments, mode)
    setCharacterIntroMode(mode)
    setEpisodeParams(nextParams)
    episodeParamsRef.current = nextParams
    setFragments(nextFragments)
    try {
      const updated = await dramaApi.updateEpisode(eid, { params: nextParams })
      const updatedParams =
        updated.params && typeof updated.params === 'object' && !Array.isArray(updated.params)
          ? (updated.params as Record<string, unknown>)
          : nextParams
      setEpisode(updated)
      setEpisodeParams(updatedParams)
      episodeParamsRef.current = updatedParams
      setCharacterIntroMode(readEffectiveCharacterIntroMode(updatedParams, projectParamsRef.current))
      const contentChanged = nextFragments.some(
        (frag, index) => frag.content !== prevFragments[index]?.content,
      )
      if (contentChanged) {
        const ep = await dramaApi.saveFragments(
          eid,
          nextFragments.map((f, i) => {
            const prevFragParams =
              f.params && typeof f.params === 'object' && !Array.isArray(f.params)
                ? (f.params as Record<string, unknown>)
                : {}
            return {
              id: typeof f.id === 'number' && f.id > 0 ? f.id : undefined,
              sort_order: i,
              content: f.content,
              cover: f.cover,
              video: f.video,
              duration_sec: resolveFragmentDurationSec(f.content, f.duration_sec),
              params: { ...prevFragParams, user_edited: true },
              asset_ids: f.asset_ids || [],
            }
          }),
        )
        setEpisode(ep)
        setFragments(ep.fragments || nextFragments)
      }
      setStatus(
        mode === 'model'
          ? t('dramaEpisode.page.introOn')
          : t('dramaEpisode.page.introOff'),
      )
      setError('')
    } catch (err) {
      setCharacterIntroMode(readEffectiveCharacterIntroMode(prevParams, projectParamsRef.current))
      setEpisodeParams(prevParams)
      episodeParamsRef.current = prevParams
      setFragments(prevFragments)
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.introSaveFailed'))
    }
  }

  const referencedIds = useMemo(() => {
    const set = new Set<number>()
    for (const f of fragments) {
      for (const id of extractAssetIds(f.content || '')) set.add(id)
      for (const id of f.asset_ids || []) set.add(id)
    }
    return set
  }, [fragments])

  const filteredAssets = useMemo(
    () => filterEpisodeAssets(assets, assetScope, assetTab, referencedIds),
    [assets, assetScope, assetTab, referencedIds],
  )

  // 应用后端生成进度并同步分镜状态 + 全局队列
  function applyGenerateStatus(st: Awaited<ReturnType<typeof dramaApi.generateStatus>>) {
    setStatus(
      t('dramaEpisode.page.genProgress', { done: st.done, total: st.total, running: st.running, failed: st.failed }),
    )
    const byId = new Map(st.fragments.map((f) => [f.fragment_id, f.status]))
    setFragments((prev) => {
      const next = prev.map((f) => {
        if (!f.id) return f
        const genStatus = byId.get(f.id)
        if (!genStatus) return f
        const item = st.fragments.find((x) => x.fragment_id === f.id) as
          | {
              fragment_id: number
              status: string
              video?: string
              cover?: string
              message?: string
              phase?: string
              error?: string
            }
          | undefined
        return {
          ...f,
          video: item?.video || f.video,
          cover: item?.cover || f.cover,
          params: {
            ...(f.params || {}),
            generation: {
              status: genStatus,
              video: item?.video,
              cover: item?.cover,
              message: item?.message,
              phase: item?.phase,
              error: item?.error,
            },
          },
        }
      })
      syncEpisodeVideoJobs({
        projectId: pid,
        episodeId: eid,
        episodeName: episode?.name,
        fragments: next.map((f) => ({
          id: f.id,
          sort_order: f.sort_order,
          content: f.content,
        })),
        statusItems: st.fragments.map((f) => {
          const row = f as {
            fragment_id: number
            status: string
            message?: string
            phase?: string
            error?: string
            video?: string
            cover?: string
          }
          return {
            fragment_id: row.fragment_id,
            status: row.status,
            message: row.message,
            phase: row.phase,
            error: row.error,
            video: row.video,
            cover: row.cover,
          }
        }),
        taskItems: st.tasks,
      })
      return next
    })
    return st
  }

  applyStatusRef.current = applyGenerateStatus

  // 进页检查是否有进行中的生成任务或 AI 分镜
  async function resumeGenerateIfNeeded() {
    try {
      const ep = await dramaApi.getEpisode(eid)
      if (readFragmentPlanStatus(ep) === 'generating') {
        setBusy(true)
        setPlanning(true)
        setStatus(t('dramaEpisode.page.planning'))
        try {
          const started = Date.now()
          while (Date.now() - started < 10 * 60 * 1000) {
            await new Promise((r) => setTimeout(r, 2500))
            const cur = await dramaApi.getEpisode(eid)
            const st = readFragmentPlanStatus(cur)
            if (st === 'completed') {
              setEpisode(cur)
              setFragments(cur.fragments || [])
              setSelectedIndex(0)
              setStatus(t('dramaEpisode.page.planDone', { count: (cur.fragments || []).length }))
              setBusy(false)
              return
            }
            if (st === 'failed') {
              setError(String(cur.params?.fragment_plan_error || t('dramaEpisode.page.planFailed')))
              setBusy(false)
              return
            }
          }
          setBusy(false)
          return
        } finally {
          setPlanning(false)
        }
      }
      const st = applyGenerateStatus(await dramaApi.generateStatus(eid))
      if (st.running > 0) ensureEpisodeVideoStatusPoll()
    } catch {
      /* ignore */
    }
  }

  // 打开全屏分镜故事板画布
  function openEpisodeStoryboard() {
    navigate(`/drama/projects/${pid}/episodes/${eid}/canvas`)
  }

  // 重新加载分集
  async function reload() {
    const ep = await dramaApi.getEpisode(eid)
    setEpisode(ep)
    const epParams =
      ep.params && typeof ep.params === 'object' && !Array.isArray(ep.params)
        ? (ep.params as Record<string, unknown>)
        : {}
    setEpisodeParams(epParams)
    episodeParamsRef.current = epParams
    setSubtitleMode(readEffectiveSubtitleMode(epParams, projectParamsRef.current))
    setCharacterIntroMode(readEffectiveCharacterIntroMode(epParams, projectParamsRef.current))
    setAspectRatio(readEpisodeAspectRatio(epParams, projectParamsRef.current))
    setFragments(ep.fragments || [])
    if ((ep.fragments || []).length === 0) {
      setFragments([
        {
          id: 0,
          episode_id: eid,
          sort_order: 0,
          content: '',
          cover: '',
          video: '',
          duration_sec: 8,
          asset_ids: [],
        },
      ])
    }
    await resumeGenerateIfNeeded()
  }

  reloadRef.current = reload

  // 复用全局 generate_status 轮询，避免与 dramaGenQueue 重复请求
  useEffect(() => {
    return subscribeEpisodeGenerateStatus(async (episodeId, st) => {
      if (episodeId !== eid) return
      const result = applyStatusRef.current(st)
      if (result.running === 0) {
        await reloadRef.current()
      }
    })
  }, [eid])

  // 切换分镜时退出历史版本预览
  useEffect(() => {
    setPreviewVersionId(null)
  }, [selectedIndex, selected?.id])

  useEffect(() => {
    if (!eid || !pid) return
    setBusy(false)
    setStatus('')
    setError('')
    reload().catch((err) => setError(err instanceof Error ? err.message : translate('common.loadFailed')))
    dramaApi
      .listAssets(pid)
      .then(setAssets)
      .catch(() => setAssets([]))
    dramaApi
      .listEpisodes(pid)
      .then((rows) => setEpisodeList(rows))
      .catch(() => setEpisodeList([]))
    // 加载项目默认画面风格 / 镜间衔接等到顶栏
    dramaApi
      .getProject(pid)
      .then((project) => {
        const styleId = getImageStyleId(project.script, project)
        if (styleId) setVideoStyleId(styleId as ImageStyleId)
        const params =
          project.params && typeof project.params === 'object' && !Array.isArray(project.params)
            ? (project.params as Record<string, unknown>)
            : {}
        setProjectParams(params)
        projectParamsRef.current = params
        const linkRaw = params.linkLastFrame ?? params.link_last_frame
        setLinkLastFrame(coerceProjectBool(linkRaw, true))
        setSubtitleMode(readEffectiveSubtitleMode(episodeParamsRef.current, params))
        setCharacterIntroMode(readEffectiveCharacterIntroMode(episodeParamsRef.current, params))
        setAspectRatio(readEpisodeAspectRatio(episodeParamsRef.current, params))
      })
      .catch(() => {
        /* ignore */
      })
  }, [eid, pid])

  // 更新当前分镜
  function updateSelected(patch: Partial<DramaFragment>) {
    setFragments((prev) =>
      prev.map((f, i) => (i === selectedIndex ? { ...f, ...patch } : f)),
    )
  }

  // 插入空白分镜
  function insertFrag(at: number) {
    setFragments((prev) => {
      const next = [...prev]
      next.splice(at, 0, {
        id: 0,
        episode_id: eid,
        sort_order: at,
        content: '',
        cover: '',
        video: '',
        duration_sec: 8,
        asset_ids: [],
      })
      return next
    })
    setSelectedIndex(at)
    setEditing(true)
  }

  // 复制分镜
  function duplicateFrag(index: number) {
    const source = fragments[index]
    if (!source) return
    setFragments((prev) => {
      const next = [...prev]
      next.splice(index + 1, 0, {
        ...source,
        id: 0,
        sort_order: index + 1,
      })
      return next
    })
    setSelectedIndex(index + 1)
  }

  // 删除分镜
  function deleteFrag(index: number) {
    if (fragments.length <= 1) return
    setFragments((prev) => prev.filter((_, i) => i !== index))
    setSelectedIndex((cur) => {
      if (cur === index) return Math.max(0, index - 1)
      if (cur > index) return cur - 1
      return cur
    })
  }

  // 保存全部分镜（带 id 更新，避免每次重建 id 打断在途生成；标记 user_edited 防自动重切覆盖）
  async function save() {
    setBusy(true)
    setError('')
    try {
      const ep = await dramaApi.saveFragments(
        eid,
        fragments.map((f, i) => {
          const prevParams =
            f.params && typeof f.params === 'object' && !Array.isArray(f.params)
              ? (f.params as Record<string, unknown>)
              : {}
          return {
            id: typeof f.id === 'number' && f.id > 0 ? f.id : undefined,
            sort_order: i,
            content: f.content,
            cover: f.cover,
            video: f.video,
            duration_sec: resolveFragmentDurationSec(f.content, f.duration_sec),
            params: { ...prevParams, user_edited: true },
            asset_ids: f.asset_ids || [],
          }
        }),
      )
      setEpisode(ep)
      setFragments(ep.fragments || [])
      setStatus(t('common.saved'))
      setEditing(false)
      return ep
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.saveFailed'))
      throw err
    } finally {
      setBusy(false)
    }
  }

  // 判断「一键生成」时是否可安全跳过：仅跳过未改动且已有成片的旧分镜
  function shouldSkipGenerateAllFragment(frag: DramaFragment): boolean {
    if (!frag.video || !frag.id) return false
    const prev = (episode?.fragments || []).find((item) => item.id === frag.id)
    if (!prev?.video) return false
    const sameContent = (prev.content || '') === (frag.content || '')
    const sameCover = (prev.cover || '') === (frag.cover || '')
    const sameDuration =
      resolveFragmentDurationSec(prev.content || '', prev.duration_sec) ===
      resolveFragmentDurationSec(frag.content || '', frag.duration_sec)
    const prevAssetIds = [...(prev.asset_ids || [])].sort((a, b) => a - b)
    const nextAssetIds = [...(frag.asset_ids || [])].sort((a, b) => a - b)
    const sameAssets =
      prevAssetIds.length === nextAssetIds.length &&
      prevAssetIds.every((id, index) => id === nextAssetIds[index])
    return sameContent && sameCover && sameDuration && sameAssets
  }

  // 仅生成当前选中分镜（保存按 id 更新，生成前仍用保存后返回的 id）
  async function generateSelected() {
    if (!selected) {
      setError(t('dramaEpisode.page.selectFragmentFirst'))
      return
    }
    if (selectedGenerateLocked) {
      if (continuityBlockedReason) {
        setError(continuityBlockedReason)
        await dialog.alert({
          title: t('dramaEpisode.page.cannotGenerate'),
          message: t('dramaEpisode.page.continuityBlockedMsg', { reason: continuityBlockedReason }),
        })
      } else if (selectedIsGenerating) {
        setError(t('dramaEpisode.page.selectedGenerating'))
      } else {
        setError(t('dramaEpisode.page.waitCurrentOp'))
      }
      return
    }

    const { blocking, warnings } = collectDramaGenerateGateIssues(selected, assets)
    if (blocking.length > 0) {
      setError(blocking.map((i) => i.message).join(t('dramaEpisode.page.issueSep')))
      await dialog.alert({
        title: t('dramaEpisode.page.cannotGenerate'),
        message: formatDramaGateMessage(blocking, warnings, t('dramaEpisode.page.fixScriptFirst')),
      })
      return
    }

    const fragLabel = formatFragLabel(selectedIndex, selectedDuration)
    const isRegen = Boolean(selected.video)
    const ok = await dialog.confirm({
      title: isRegen ? t('dramaEpisode.page.regenTitle') : t('dramaEpisode.page.genTitle'),
      message: formatDramaGateMessage(
        [],
        warnings,
        isRegen
          ? t('dramaEpisode.page.regenMsg', { label: fragLabel })
          : linkLastFrame
            ? continuityQueueHint
              ? t('dramaEpisode.page.genQueueMsg', { label: fragLabel, hint: continuityQueueHint })
              : t('dramaEpisode.page.genLinkedMsg', { label: fragLabel })
            : t('dramaEpisode.page.genIndependentMsg', { label: fragLabel }),
      ),
      confirmText: warnings.length > 0 ? t('dramaEpisode.page.genAnyway') : isRegen ? t('dramaEpisode.page.regenerate') : t('dramaEpisode.page.startGenerate'),
    })
    if (!ok) return
    setBusy(true)
    setError('')
    setStatus(isRegen ? t('dramaEpisode.page.savingRegen') : t('dramaEpisode.page.savingGen'))
    try {
      const ep = await save()
      setBusy(true)
      const frag = (ep.fragments || [])[selectedIndex]
      if (!frag?.id) {
        throw new Error(t('dramaEpisode.page.fragmentMissingAfterSave'))
      }
      await dramaApi.generateEpisode(eid, [frag.id], modelId)
      // 乐观写入排队态，避免旧 video 把状态盖成已完成
      setFragments((prev) =>
        prev.map((f) =>
          f.id === frag.id
            ? {
                ...f,
                params: {
                  ...(f.params || {}),
                  generation: { status: 'queued', message: '已入队' },
                },
              }
            : f,
        ),
      )
      enqueueEpisodeVideoJobs({
        projectId: pid,
        episodeId: eid,
        episodeName: ep.name || episode?.name,
        fragments: (ep.fragments || []).map((f, i) => ({
          id: f.id,
          sort_order: f.sort_order ?? i,
        })),
        fragmentIds: [frag.id],
      })
      setBusy(false)
      setStatus(
        isRegen
          ? t('dramaEpisode.page.requeued', { label: fragLabel })
          : t('dramaEpisode.page.queued', { label: fragLabel }),
      )
      ensureEpisodeVideoStatusPoll()
    } catch (err) {
      setBusy(false)
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.generateFailed'))
    }
  }

  // 切换历史成片为当前预览视频
  async function activateVideoVersion(versionId: string) {
    if (!selected?.id || selectedIsGenerating) return
    const ok = await dialog.confirm({
      title: t('dramaEpisode.page.switchVersionTitle'),
      message: t('dramaEpisode.page.switchVersionMsg'),
      confirmText: t('dramaEpisode.page.switchVersionConfirm'),
    })
    if (!ok) return
    setBusy(true)
    setError('')
    try {
      const result = await dramaApi.activateFragmentVideoVersion(selected.id, versionId)
      setFragments((prev) =>
        prev.map((f) =>
          f.id === selected.id
            ? {
                ...f,
                video: result.video,
                cover: result.cover || '',
                params: {
                  ...(f.params || {}),
                  video_versions: result.video_versions,
                  lastFrameUrl: result.lastFrameUrl || undefined,
                  generation: {
                    status: 'done',
                    video: result.video,
                    cover: result.cover,
                    lastFrameUrl: result.lastFrameUrl,
                  },
                },
              }
            : f,
        ),
      )
      setPreviewVersionId(null)
      setStatus(t('dramaEpisode.page.versionSwitched'))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.switchVersionFailed'))
    } finally {
      setBusy(false)
    }
  }

  // 一键生成：入队本集分镜（forceRegen 覆盖已有成片）
  async function generateAll(opts?: { forceRegen?: boolean; skipConfirm?: boolean }) {
    if (fragments.length === 0) {
      setError(t('dramaEpisode.page.noFragments'))
      return
    }
    if (generateAllLocked) {
      setError(t('dramaEpisode.page.submitting'))
      return
    }

    const allBlocking: string[] = []
    const allWarnings: string[] = []
    const doneIndices: number[] = []
    for (let i = 0; i < fragments.length; i++) {
      if (!opts?.forceRegen && shouldSkipGenerateAllFragment(fragments[i])) {
        doneIndices.push(i)
        continue
      }
      const { blocking, warnings } = collectDramaGenerateGateIssues(fragments[i], assets)
      const label = formatFragLabel(i, fragments[i]?.duration_sec)
      for (const issue of blocking) allBlocking.push(t('dramaEpisode.page.issueLine', { label, message: issue.message }))
      for (const issue of warnings) allWarnings.push(t('dramaEpisode.page.issueLine', { label, message: issue.message }))
    }
    const pendingCount = fragments.length - doneIndices.length
    if (pendingCount <= 0) {
      setStatus(t('dramaEpisode.page.allDoneSkipped'))
      return
    }
    if (allBlocking.length > 0) {
      setError(allBlocking[0] || t('dramaEpisode.page.scriptCheckFailed'))
      await dialog.alert({
        title: t('dramaEpisode.page.cannotGenerateAll'),
        message: [t('dramaEpisode.page.fixIssuesFirst'), '', ...allBlocking.slice(0, 8).map((line) => `· ${line}`)].join(
          '\n',
        ),
      })
      return
    }

    if (!opts?.skipConfirm) {
      const ok = await dialog.confirm({
        title: opts?.forceRegen ? t('dramaEpisode.page.regenAllTitle') : t('dramaEpisode.page.genAllTitle'),
        message: formatDramaGateMessage(
          [],
          allWarnings.slice(0, 8).map((message) => ({ level: 'warn' as const, message })),
          opts?.forceRegen
            ? t('dramaEpisode.page.regenAllMsg', { count: pendingCount })
            : linkLastFrame
              ? t('dramaEpisode.page.genAllLinkedMsg', { count: pendingCount, done: doneIndices.length })
              : t('dramaEpisode.page.genAllParallelMsg', { count: pendingCount, done: doneIndices.length }),
        ),
        confirmText:
          allWarnings.length > 0
            ? t('dramaEpisode.page.genAllAnyway')
            : opts?.forceRegen
              ? t('dramaEpisode.page.regenAll')
              : t('dramaEpisode.page.genAll'),
        tone: 'danger',
      })
      if (!ok) return
    }
    setBusy(true)
    setError('')
    setStatus(t('dramaEpisode.page.savingGenAll', { count: pendingCount }))
    try {
      const ep = await save()
      setBusy(true)
      const ids = (ep.fragments || [])
        .filter((_, index) => !doneIndices.includes(index))
        .map((f) => f.id)
        .filter((id): id is number => typeof id === 'number' && id > 0)
      if (ids.length === 0) {
        setStatus(t('dramaEpisode.page.allDoneAfterSave'))
        setBusy(false)
        return
      }
      const genResult = await dramaApi.generateEpisode(eid, ids, modelId)
      const queuedIds =
        Array.isArray(genResult.fragment_ids) && genResult.fragment_ids.length > 0
          ? genResult.fragment_ids
          : ids
      enqueueEpisodeVideoJobs({
        projectId: pid,
        episodeId: eid,
        episodeName: ep.name || episode?.name,
        fragments: (ep.fragments || []).map((f, i) => ({
          id: f.id,
          sort_order: f.sort_order ?? i,
        })),
        fragmentIds: queuedIds,
      })
      const deferred = Number(genResult.deferred_count || 0)
      const limit = Number(genResult.user_job_limit || 0)
      if (deferred > 0 && limit > 0) {
        setStatus(
          t('dramaEpisode.page.queuedWithLimit', { queued: queuedIds.length, limit, deferred }),
        )
      } else {
        setStatus(t('dramaEpisode.page.queuedGenerating', { queued: queuedIds.length }))
      }
      setBusy(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.genAllFailed'))
      setBusy(false)
    }
  }

  // 返回剧情大纲
  function handleBack() {
    navigate(`/drama/projects/${pid}`, { state: { activeStep: 'outline' } })
  }

  // 左侧目录切换分集
  function handleSelectEpisode(nextId: number) {
    if (nextId === eid) return
    navigate(`/drama/projects/${pid}/episodes/${nextId}`)
  }

  // 单集 LLM 重新分镜：确认并勾选 Skill 后入队
  function planFragmentsWithLlm() {
    if (planFragmentsLocked) {
      setError(t('dramaEpisode.page.planLockedByVideo'))
      return
    }
    setPlanModalOpen(true)
  }

  // 入队后轮询至完成（字幕方式沿用顶栏当前设置）
  async function startPlanFragments(skillIds: number[]) {
    setPlanModalOpen(false)
    setBusy(true)
    setError('')
    setPlanning(true)
    setStatus(t('dramaEpisode.page.planning'))
    try {
      await dramaApi.planEpisodeFragments(eid, {
        force: true,
        fallback_rules: true,
        skill_ids: skillIds,
        subtitle_enabled: subtitleModeUsesModelOutput(subtitleMode),
      })
      const started = Date.now()
      while (Date.now() - started < 10 * 60 * 1000) {
        await new Promise((r) => setTimeout(r, 2500))
        const ep = await dramaApi.getEpisode(eid)
        const st = readFragmentPlanStatus(ep)
        if (st === 'completed') {
          setEpisode(ep)
          const nextParams = (ep.params as Record<string, unknown>) || {}
          setEpisodeParams(nextParams)
          episodeParamsRef.current = nextParams
          setFragments(ep.fragments || [])
          setSelectedIndex(0)
          setEditing(false)
          const mode = String(ep.params?.fragment_plan_mode || 'llm')
          const count = Number(ep.params?.fragment_plan_count) || (ep.fragments || []).length
          setStatus(
            mode === 'rules_fallback'
              ? t('dramaEpisode.page.planDoneFallback', { count })
              : t('dramaEpisode.page.planDone', { count }),
          )
          setBusy(false)
          return
        }
        if (st === 'failed') {
          const msg = String(ep.params?.fragment_plan_error || t('dramaEpisode.page.planFailed'))
          setError(msg)
          setBusy(false)
          return
        }
        setStatus(t('dramaEpisode.page.planning'))
      }
      throw new Error(t('dramaEpisode.page.planTimeout'))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.planFailed'))
      setBusy(false)
    } finally {
      setPlanning(false)
    }
  }

  // 点击资产插入 @ 引用
  function mentionAsset(asset: DramaAsset) {
    if (!selected) return
    const mention = `@asset:${asset.id}`
    const raw = selected.content || ''
    const already = new RegExp(`@asset:${asset.id}(?!\\d)`).test(raw)
    const content = already ? raw : raw ? `${raw.trimEnd()}\n${mention}` : mention
    const ids = Array.from(new Set([...(selected.asset_ids || []), asset.id]))
    updateSelected({ content, asset_ids: ids })
    setEditing(true)
  }

  // 解析侧栏当前要新建的资产类型（未选分类时默认角色）
  function resolveCreateAssetTab(): AssetTab {
    return assetTab || 'character'
  }

  // 新建后挂到当前分镜并打开详情，便于本集列表立刻可见
  function adoptCreatedAsset(created: DramaAsset, kind: AssetTab) {
    setAssets((prev) => (prev.some((a) => a.id === created.id) ? prev : [...prev, created]))
    setAssetTab(kind)
    mentionAsset(created)
    if ((created.type || '').toLowerCase() !== 'voice') {
      setDetailAsset(created)
    }
  }

  // 自定义新建角色 / 场景 / 道具
  async function handleCreateSideAsset() {
    const kind = resolveCreateAssetTab()
    const label = m.dramaEpisode.assetKindsInline[kind]
    const name = await dialog.prompt({
      title: t('dramaEpisode.page.createAssetTitle', { kind: label }),
      message: t('dramaEpisode.page.createAssetMsg', { kind: label }),
      placeholder: m.dramaEpisode.page.createAssetPlaceholder[kind],
      confirmText: t('dramaEpisode.page.create'),
    })
    if (!name?.trim()) return
    setAssetCreateBusy(true)
    setError('')
    try {
      const created = await dramaApi.createAsset({
        project_id: pid,
        type: kind,
        asset_type: 'image',
        name: name.trim(),
        params: { kind },
      })
      adoptCreatedAsset(created, kind)
      setStatus(t('dramaEpisode.page.assetCreated', { kind: label, name: created.name || '' }))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.createAssetFailed', { kind: label }))
    } finally {
      setAssetCreateBusy(false)
    }
  }

  // 从全局资产库导入到本项目并挂到当前分镜
  async function handleImportSideAsset(source: DramaAsset) {
    const kind = normalizeAssetTab(source.type) || resolveCreateAssetTab()
    setAssetCreateBusy(true)
    setError('')
    try {
      const created = await importGlobalAssetToProject(pid, source)
      adoptCreatedAsset(created, kind)
      setLibraryPickerOpen(false)
      setStatus(t('dramaEpisode.page.assetImported', { name: created.name || '' }))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.importAssetFailed'))
      throw err
    } finally {
      setAssetCreateBusy(false)
    }
  }

  // 仅取消当前分镜对该资产的关联（不删除项目资产）
  function unlinkSelectedAsset(assetId: number) {
    if (!selected) return
    const content = (selected.content || '')
      .replace(new RegExp(`\\s*@asset:${assetId}(?!\\d)`, 'g'), ' ')
      .replace(/[ \t]{2,}/g, ' ')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    const asset_ids = (selected.asset_ids || []).filter((id) => id !== assetId)
    updateSelected({ content, asset_ids })
    setEditing(true)
    const name = assets.find((a) => a.id === assetId)?.name
    setStatus(
      name
        ? t('dramaEpisode.page.unlinkedNamed', { name })
        : t('dramaEpisode.page.unlinked'),
    )
  }

  // 从关联条跳到对应分类并打开资产详情
  function focusLinkedAsset(assetId: number) {
    const asset = assets.find((a) => a.id === assetId)
    if (!asset) return
    const tab = normalizeAssetTab(asset.type)
    if (tab) setAssetTab(tab)
    setAssetScope('series')
    if ((asset.type || '').toLowerCase() !== 'voice') {
      setDetailAsset(asset)
    }
  }

  // 更新资产（音色绑定 / 上传 / 生图后刷新列表与详情）
  function handleCharacterUpdated(updated: DramaAsset) {
    setAssets((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
    setDetailAsset((prev) => (prev?.id === updated.id ? updated : prev))
  }

  // 当前排队/生成中的资产生图 id
  const imageBusyIds = useMemo(() => {
    const ids = new Set<number>()
    for (const job of imageGenQueue) {
      if (job.status === 'queued' || job.status === 'running') ids.add(job.assetId)
    }
    return ids
  }, [imageGenQueue])

  // 详情弹窗生图按钮文案
  function assetImageGenLabel(asset: DramaAsset): string {
    const job = imageGenQueue.find(
      (j) =>
        j.assetId === asset.id && (j.status === 'queued' || j.status === 'running'),
    )
    let queueLabel: string | null = null
    if (job) {
      if (job.status === 'running') queueLabel = t('dramaEpisode.page.imageGenerating')
      else {
        const queuedOnly = imageGenQueue.filter(
          (j) => j.status === 'queued' || j.status === 'running',
        )
        const pos = queuedOnly.findIndex((j) => j.id === job.id) + 1
        queueLabel = pos > 1 ? t('dramaEpisode.page.imageQueuePos', { pos }) : t('dramaEpisode.page.imageQueued')
      }
    }
    return dramaAssetImageGenButtonLabel(asset, queueLabel)
  }

  // 将资产生图加入全局队列
  function enqueueAssetImage(asset: DramaAsset) {
    if (imageBusyIds.has(asset.id)) return
    const options = {
      ...defaultOptionsForAssetKind(asset.type),
      image_style_id: videoStyleId || undefined,
    }
    void enqueueDramaImageGen({
      projectId: pid,
      assetId: asset.id,
      assetName: asset.name || undefined,
      assetType: asset.type,
      prompt: readVisualPrompt(asset),
      options,
      onAssetUpdate: handleCharacterUpdated,
    })
      .then((updated) => handleCharacterUpdated(updated))
      .catch((err) => setError(formatDramaGenError(err).message || t('dramaEpisode.page.imageGenFailed')))
  }

  // 打开分镜失败原因（优先队列任务，否则用分镜 params.generation.error）
  function openFragmentFailReason(frag: DramaFragment, index: number) {
    if (!frag.id) return
    const fromQueue = dramaGenQueue.find(
      (j) => j.id === videoJobId(frag.id!) || (j.kind === 'video' && j.targetId === frag.id),
    )
    const gen = readFragmentGenerationStatus(frag)
    const title = `${episode?.name || t('dramaEpisode.thisEpisode')} · ${formatFragLabel(index, frag.duration_sec)}`
    setFailReasonJob({
      id: fromQueue?.id || videoJobId(frag.id),
      kind: 'video',
      projectId: pid,
      targetId: frag.id,
      episodeId: eid || undefined,
      taskId: fromQueue?.taskId,
      title: fromQueue?.title || title,
      subtype: FRAGMENT_VIDEO_SUBTYPE,
      status: 'failed',
      error: fromQueue?.error || gen.error || t('dramaEpisode.page.generateFailed'),
      createdAt: fromQueue?.createdAt || Date.now(),
    })
  }

  // 一键 AI 生成角色音色并绑定（各角色独立 busy，互不阻塞）
  async function handleGenerateCharacterVoice(asset: DramaAsset) {
    if (characterVoiceBusyIds.has(asset.id)) return
    setCharacterVoiceBusyIds((prev) => new Set(prev).add(asset.id))
    setError('')
    try {
      const { character, voice } = await generateAndBindCharacterVoice(pid, asset)
      handleCharacterUpdated(character)
      setAssets((prev) => (prev.some((a) => a.id === voice.id) ? prev : [...prev, voice]))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('dramaEpisode.page.voiceGenFailed'))
    } finally {
      setCharacterVoiceBusyIds((prev) => {
        const next = new Set(prev)
        next.delete(asset.id)
        return next
      })
    }
  }

  if (!episode) {
    return (
      <div className="drama-ep-fullscreen drama-ep-center">
        {error || t('common.loading')}
      </div>
    )
  }

  // 当前预览/选中分镜 id（与底部分镜条、脚本编辑联动）
  const playingFragmentId = selected?.id ?? null

  // 切换预览分镜时同步底部分镜选中态
  function handlePlayingFragmentChange(fragmentId: number) {
    const index = fragments.findIndex((f) => f.id === fragmentId)
    if (index >= 0) {
      setSelectedIndex(index)
    }
  }

  return (
    <div className="drama-ep-fullscreen">
      <header className="drama-ep-header">
        <div className="drama-ep-header-left">
          <button type="button" className="drama-ep-icon-btn" aria-label={t('dramaEpisode.page.back')} onClick={handleBack}>
            ‹
          </button>
          <h1>{episode.name}</h1>
        </div>
        <div className="drama-ep-header-controls">
          <EpisodeEditHeaderControls
            styleId={videoStyleId}
            modelId={modelId}
            episodeParams={episodeParams}
            projectParams={projectParams}
            linkLastFrame={linkLastFrame}
            subtitleMode={subtitleMode}
            characterIntroMode={characterIntroMode}
            onStyleChange={setVideoStyleId}
            onModelChange={setModelId}
            onEpisodeOutputChange={handleEpisodeOutputChange}
            onLinkLastFrameChange={(enabled) => void handleLinkLastFrameChange(enabled)}
            onSubtitleModeChange={(mode) => void handleEpisodeSubtitleChange(mode)}
            onCharacterIntroModeChange={(mode) => void handleEpisodeCharacterIntroChange(mode)}
            disabled={busy}
            globalSettingsReadOnly
          />
          <button
            type="button"
            className="drama-ep-btn-ghost"
            disabled={planFragmentsLocked}
            onClick={() => void planFragmentsWithLlm()}
          >
            {busy && planning ?t('dramaEpisode.page.planningShort') : t('dramaEpisode.page.replan')}
          </button>
          {/* 一键生成：暂时隐藏，恢复时去掉 false && */}
          {false && (
            <button
              type="button"
              className="drama-ep-btn-dark drama-ep-header-gen-all"
              disabled={generateAllLocked || fragments.length === 0}
              onClick={() => void generateAll()}
            >
              {busy ? t('dramaEpisode.page.enqueuing') : t('dramaEpisode.page.genAll')}
            </button>
          )}
        </div>
      </header>

      {(status || error) && (
        <div className="drama-ep-banner">
          {error ? <BillingErrorNotice message={error} className="drama-ep-banner-error" inline /> : null}
          {!error && status ? <span>{status}</span> : null}
        </div>
      )}

      <div className="drama-ep-body">
        <DramaEpisodeDir
          items={buildEpisodeDirItems(episodeList.length ? episodeList : episode ? [episode] : [])}
          activeId={eid}
          onSelect={handleSelectEpisode}
        />
        <div className="drama-ep-workspace">
        <EpisodeEditAssetPanel
          scope={assetScope}
          tab={assetTab}
          assets={filteredAssets}
          activeIds={selectedRefIds}
          imageBusyIds={imageBusyIds}
          createBusy={assetCreateBusy}
          onScopeChange={setAssetScope}
          onTabChange={setAssetTab}
          onOpenCanvas={openEpisodeStoryboard}
          onOpenAsset={setDetailAsset}
          onMention={mentionAsset}
          onUnlinkAsset={unlinkSelectedAsset}
          onGenerateVoice={
            DRAMA_VOICE_BINDING_ENABLED
              ? (asset) => void handleGenerateCharacterVoice(asset)
              : undefined
          }
          voiceBusyIds={characterVoiceBusyIds}
          onVoiceError={(message) => setError(message)}
          onCreateAsset={() => void handleCreateSideAsset()}
          onImportAsset={() => setLibraryPickerOpen(true)}
        />

        <section className="drama-ep-editor">
          <div className="drama-ep-editor-head">
            <div>
              <strong>{formatFragLabel(selectedIndex, selectedDuration)}</strong>
              <p>
                {t('dramaEpisode.page.editorHint')}{' '}
                {formatProjectOutputLabel(
                  readEpisodeAspectRatio(episodeParams, projectParams),
                  readEpisodeResolution(episodeParams, projectParams),
                )}
              </p>
            </div>
            <label className="drama-ep-duration">
              {t('dramaEpisode.page.duration')}
              <input
                type="number"
                min={4}
                max={15}
                value={selectedDuration}
                disabled={!editing && !selected}
                onChange={(e) =>
                  updateSelected({ duration_sec: Number(e.target.value) || 8 })
                }
              />
              s
            </label>
          </div>

          <EpisodeEditReferenceStrip items={selectedRefItems} onSelect={focusLinkedAsset} />

          <div className={`drama-ep-editor-box ${editing ? 'editing' : ''}`}>
            <EpisodeEditPromptEditor
              content={selected?.content || ''}
              assets={assets}
              referencedIds={referencedIds}
              editing={editing}
              onOpenAsset={focusLinkedAsset}
              onContentChange={(nextContent) => {
                const fromContent = extractAssetIds(nextContent)
                const prevContentIds = extractAssetIds(selected?.content || '')
                const removed = prevContentIds.filter((id) => !fromContent.includes(id))
                /* 正文删掉的引用同步移出 asset_ids；仅存在于 asset_ids 的额外关联保留 */
                const prevContentIdSet = new Set(prevContentIds)
                const keptExtra = (selected?.asset_ids || []).filter(
                  (id) => !prevContentIdSet.has(id) || fromContent.includes(id),
                )
                updateSelected({
                  content: nextContent,
                  asset_ids: Array.from(new Set([...keptExtra, ...fromContent])),
                })
                if (removed.length > 0) {
                  setStatus(t('dramaEpisode.page.unlinkedKept'))
                }
              }}
            />

          {selectedGateIssues.length > 0 ? (
            <ul className="drama-ep-script-issues" aria-live="polite">
              {selectedGateIssues.map((issue) => (
                <li
                  key={`${issue.level}:${issue.message}`}
                  className={
                    issue.level === 'error'
                      ? 'drama-ep-script-issue is-error'
                      : 'drama-ep-script-issue is-warn'
                  }
                >
                  {issue.message}
                </li>
              ))}
            </ul>
          ) : null}

          {linkLastFrame && selectedIndex > 0 ? (
            <p
              className={`drama-ep-continuity-hint${
                !continuityBlockedReason ? ' is-ready' : ' is-wait'
              }`}
            >
              {continuityBlockedReason
                ? t('dramaEpisode.page.continuityBlockedHint', { reason: continuityBlockedReason })
                : continuityQueueHint
                  ? continuityQueueHint
                  : prevLastFrameUrl
                    ? t('dramaEpisode.page.continuityUsePrevFrame')
                    : t('dramaEpisode.page.continuityExtractPrev')}
            </p>
          ) : !linkLastFrame ? (
            <p className="drama-ep-continuity-hint">
              {t('dramaEpisode.page.continuityOff')}
            </p>
          ) : null}

          <div className="drama-ep-editor-actions">
            {editing ? (
              <>
                <button
                  type="button"
                  className="drama-ep-btn-ghost"
                  disabled={busy}
                  onClick={() => {
                    setEditing(false)
                    void reload()
                  }}
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="button"
                  className="drama-ep-btn-dark"
                  disabled={busy}
                  onClick={() => void save()}
                >
                  {busy ? t('common.saving') : t('common.save')}
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="drama-ep-btn-ghost"
                  disabled={!selected || selectedIsGenerating || busy}
                  onClick={() => setEditing(true)}
                >
                  {t('dramaEpisode.page.edit')}
                </button>
                <button
                  type="button"
                  className="drama-ep-btn-dark"
                  disabled={selectedGenerateLocked || !selected}
                  title={
                    continuityBlockedReason ||
                    continuityQueueHint ||
                    (selectedIsGenerating ? t('dramaEpisode.page.selectedGenerating') : undefined)
                  }
                  onClick={() => void generateSelected()}
                >
                  {selectedIsGenerating
                    ? t('dramaEpisode.page.generating')
                    : busy
                      ? t('dramaEpisode.page.processing')
                      : continuityQueueHint
                        ? t('dramaEpisode.page.queueGenerate')
                        : continuityBlockedReason
                          ? t('dramaEpisode.page.waitPrev')
                          : selectedHasVideo
                          ? t('dramaEpisode.page.regenerate')
                          : t('dramaEpisode.page.generate')}
                </button>
              </>
            )}
          </div>
          </div>

          {selectedVersions.length > 0 && selected?.id ? (
            <div className="drama-ep-versions">
              <span className="drama-ep-versions-label">{t('dramaEpisode.page.versions')}</span>
              <div className="drama-ep-versions-list">
                {selectedHasVideo && selected.video ? (
                  <button
                    type="button"
                    className={`drama-ep-version is-active${!previewVersionId ? ' is-current' : ''}`}
                    disabled={busy || selectedIsGenerating}
                    title={t('dramaEpisode.page.currentVideo')}
                    onClick={() => setPreviewVersionId(null)}
                  >
                    {selected.cover ? (
                      <img src={resolveDramaMediaUrl(selected.cover)} alt="" />
                    ) : (
                      <video src={resolveDramaMediaUrl(selected.video)} muted />
                    )}
                    <em>{t('dramaEpisode.page.current')}</em>
                  </button>
                ) : null}
                {selectedVersions.map((ver, index) => {
                  const cover = ver.cover ? resolveDramaMediaUrl(ver.cover) : ''
                  const video = resolveDramaMediaUrl(ver.video)
                  const versionNo = selectedVersions.length - index
                  return (
                    <button
                      key={ver.id}
                      type="button"
                      className={`drama-ep-version${previewVersionId === ver.id ? ' is-previewing' : ''}`}
                      disabled={busy || selectedIsGenerating}
                      title={t('dramaEpisode.page.versionTitle')}
                      onClick={() => setPreviewVersionId(ver.id)}
                    >
                      {cover ? <img src={cover} alt="" /> : <video src={video} muted />}
                      <em>v{versionNo}</em>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}
        </section>

        <EpisodeEditSidePane
          fragments={fragments}
          playingFragmentId={playingFragmentId}
          onPlayingFragmentChange={handlePlayingFragmentChange}
          aspectRatio={aspectRatio}
          episodeId={episode?.id}
          episodeName={episode?.name || t('dramaEpisode.thisEpisode')}
          subtitleMode={subtitleMode}
          onOpenStoryboard={openEpisodeStoryboard}
          previewVideoUrl={previewVideoUrl}
          previewPosterUrl={previewPosterUrl}
          previewLabel={
            previewVersion
              ? `v${
                  selectedVersions.length -
                  selectedVersions.findIndex((ver) => ver.id === previewVersion.id)
                }`
              : ''
          }
          onClearPreview={() => setPreviewVersionId(null)}
          onActivatePreview={
            previewVersionId
              ? () => {
                  void activateVideoVersion(previewVersionId)
                }
              : undefined
          }
        />
        </div>
      </div>

      <footer className="drama-ep-storyboard">
        <div className="drama-ep-storyboard-row">
          <button
            type="button"
            className="drama-ep-insert"
            aria-label={t('dramaEpisode.page.insertAtStart')}
            onClick={() => insertFrag(0)}
          >
            +
          </button>
          {fragments.map((frag, index) => {
            const genInfo = readFragmentGenerationStatus(frag)
            const fragStatus = genInfo.status
            const activeVideoTask = (episode?.active_tasks || []).find(
              (task) =>
                task.task_type === 'fragment_video' &&
                task.fragment_id === frag.id &&
                !task.cancel_requested &&
                ['pending', 'leased', 'running', 'awaiting_poll', 'awaiting_review'].includes(
                  task.status,
                ),
            )
            // 终态优先；仅在进行中时才用平台任务态覆盖（避免 done 仍被僵尸任务刷成生成中）
            const displayStatus =
              fragStatus === 'done' ||
              fragStatus === 'failed' ||
              fragStatus === 'cancelled'
                ? fragStatus
                : activeVideoTask
                  ? activeVideoTask.status === 'pending' || activeVideoTask.status === 'leased'
                    ? 'queued'
                    : 'running'
                  : fragStatus
            const fragBusy =
              Boolean(frag.id && generatingIds.has(frag.id)) &&
              displayStatus !== 'done' &&
              displayStatus !== 'failed' &&
              displayStatus !== 'cancelled'
            const badge = fragmentQueueBadgeLabel(displayStatus)
            const clipVideo = frag.video ? resolveDramaMediaUrl(frag.video) : ''
            const clipCover = frag.cover ? resolveDramaMediaUrl(frag.cover) : ''
            const showFailHint = displayStatus === 'failed' && !fragBusy
            const fragParams =
              frag.params && typeof frag.params === 'object' && !Array.isArray(frag.params)
                ? (frag.params as Record<string, unknown>)
                : {}
            return (
            <div key={`${frag.id}-${index}`} className="drama-ep-clip-wrap">
              <div
                className={`drama-ep-clip-shell ${selectedIndex === index ? 'active' : ''}${
                  fragBusy ? ' is-generating' : ''
                }${displayStatus === 'queued' ? ' is-queued' : ''}${
                  displayStatus === 'failed' ? ' is-failed' : ''
                }`}
              >
                <button
                  type="button"
                  className="drama-ep-clip"
                  onClick={() => setSelectedIndex(index)}
                >
                  {clipCover ? (
                    <img src={clipCover} alt="" />
                  ) : clipVideo ? (
                    <video src={clipVideo} muted />
                  ) : (
                    <span className="drama-ep-clip-empty">
                      {fragBusy ? '…' : showFailHint ? (
                        <CircleAlert size={22} strokeWidth={2} aria-hidden />
                      ) : (
                        '+'
                      )}
                    </span>
                  )}
                  {badge ? <span className="drama-ep-clip-badge">{badge}</span> : null}
                  <em>
                    {formatFragLabel(index, frag.duration_sec)}
                    <DramaFragmentClipSpec
                      fragmentParams={fragParams}
                      episodeParams={episodeParams}
                      projectParams={projectParams}
                      videoUrl={clipVideo}
                    />
                  </em>
                </button>
                {showFailHint ? (
                  <button
                    type="button"
                    className="drama-ep-clip-fail-btn"
                    title={t('dramaEpisode.page.viewFailReason')}
                    aria-label={t('dramaEpisode.page.viewFailReasonOf', { n: index + 1 })}
                    onClick={() => openFragmentFailReason(frag, index)}
                  >
                    <CircleAlert size={14} strokeWidth={2.25} aria-hidden />
                  </button>
                ) : null}
              </div>
              <div className="drama-ep-clip-ops">
                <button type="button" aria-label={t('dramaEpisode.page.insert')} onClick={() => insertFrag(index + 1)} disabled={busy}>
                  +
                </button>
                <button type="button" aria-label={t('common.copy')} onClick={() => duplicateFrag(index)} disabled={busy}>
                  ⧉
                </button>
                <button
                  type="button"
                  aria-label={t('common.delete')}
                  disabled={busy || fragments.length <= 1}
                  onClick={() => deleteFrag(index)}
                >
                  ⌫
                </button>
              </div>
            </div>
            )
          })}
        </div>
      </footer>

      <FragmentPlanSkillModal
        open={planModalOpen}
        message={t('dramaEpisode.page.planModalMsg')}
        onCancel={() => setPlanModalOpen(false)}
        onConfirm={(skillIds) => void startPlanFragments(skillIds)}
      />

      {detailAsset && (detailAsset.type || '').toLowerCase() !== 'voice' ? (
        <DramaAssetDetailModal
          asset={detailAsset}
          open
          busy={imageBusyIds.has(detailAsset.id)}
          genLabel={assetImageGenLabel(detailAsset)}
          onClose={() => setDetailAsset(null)}
          onUpdated={handleCharacterUpdated}
          onGenerate={(a) => enqueueAssetImage(a)}
          onBindVoice={DRAMA_VOICE_BINDING_ENABLED ? (a) => setVoiceBindAsset(a) : undefined}
          onError={(message) => setError(message)}
        />
      ) : null}

      {DRAMA_VOICE_BINDING_ENABLED && voiceBindAsset ? (
        <CharacterVoiceBindModal
          asset={voiceBindAsset}
          projectId={pid}
          open
          onClose={() => setVoiceBindAsset(null)}
          onBound={(updated) => {
            handleCharacterUpdated(updated)
            setVoiceBindAsset(null)
          }}
          onError={(message) => setError(message)}
        />
      ) : null}

      <GlobalAssetPickerModal
        open={libraryPickerOpen}
        onClose={() => setLibraryPickerOpen(false)}
        projectId={pid}
        defaultTab={resolveCreateAssetTab()}
        allowedTypes={
          resolveCreateAssetTab() === 'prop'
            ? ['prop', 'material', 'none']
            : [resolveCreateAssetTab()]
        }
        title={t('dramaEpisode.page.importTitle', { kind: m.dramaEpisode.assetKindsInline[resolveCreateAssetTab()] })}
        confirmLabel={t('dramaEpisode.page.importConfirm')}
        onPick={handleImportSideAsset}
      />

      {failReasonJob ? (
        <div className="drama-ep-fail-reason-pop">
          <DramaGenTaskDetail job={failReasonJob} onClose={() => setFailReasonJob(null)} />
        </div>
      ) : null}
    </div>
  )
}
