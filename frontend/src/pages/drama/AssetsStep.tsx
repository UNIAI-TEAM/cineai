/** 资产库步骤：首次无资产时自动 seed，分类 Tab + 生图队列 + 角色音色绑定 */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, Sparkles } from 'lucide-react'
import { dramaApi, resolveDramaAssetPreviewUrl, type DramaAsset, type DramaProject } from '../../api/drama'
import { api, type BillingPreflight } from '../../api'
import { useDramaImageGenQueue } from '../../hooks/useDramaImageGenQueue'
import { enqueueDramaImageGen, resumeDramaImageGensFromAssets } from '../../lib/dramaImageGenQueue'
import {
  defaultOptionsForAssetKind,
  type ImageGenerationOptions,
} from '../../lib/dramaGenerationOptions'
import { getImageStyleId } from './dramaWorkspaceUtils'
import { DramaImageGenOptionsBar } from './canvas/nodes/DramaImageGenOptionsBar'
import {
  CharacterVoiceBindModal,
  readAssetVoiceBinding,
  readVoicePrompt,
} from './CharacterVoiceBindModal'
import { CharacterVoicePreviewButton } from '../../components/drama/CharacterVoicePreviewButton'
import { generateAndBindCharacterVoice } from '../../lib/characterVoiceGenerate'
import { NarratorVoiceBindModal } from './NarratorVoiceBindModal'
import { DramaAssetDetailModal } from './DramaAssetDetailModal'
import { DramaImageLightbox } from './DramaImageLightbox'
import { GlobalAssetPickerModal, importGlobalAssetToProject } from './GlobalAssetPickerModal'
import { DramaVoiceAssetCard } from './DramaVoiceAssetCard'
import Pagination from '../../components/ui/Pagination'
import { dialog } from '../../lib/dialog'
import { localizeStoredError } from '../../lib/apiError'
import { formatFenActive } from '../../currency'
import { handleBillingError, isBillingError } from '../../lib/billingError'
import { alertDramaGenError, formatDramaGenError, isUpstreamAccountError } from '../../lib/dramaGenError'
import { pageCountOf } from '../../lib/pagination'
import { readVisualPrompt } from '../../lib/dramaVisualPrompt'
import { displayDramaAssetName, filterDramaLibraryAssets } from '../../lib/dramaLibraryAssets'
import { DRAMA_VOICE_BINDING_ENABLED } from '../../lib/dramaVoiceBinding'
import { useI18n } from '../../i18n/context'
import { translate } from '../../i18n/translate'
import {
  dramaAssetImageGenButtonLabel,
  dramaAssetNeedsImageGeneration,
} from '../../lib/dramaAssetImage'

type AssetTabKey = 'character' | 'scene' | 'prop' | 'voice'

// 分类 Tab（文案在渲染时按 key 取 dramaAssets.kinds）
const ASSET_TABS: AssetTabKey[] = [
  'character',
  'scene',
  'prop',
  ...(DRAMA_VOICE_BINDING_ENABLED ? ['voice' as const] : []),
]

const PAGE_SIZE_DEFAULT = 12
const PAGE_SIZE_OPTIONS = [12, 24, 36] as const

// 跨 StrictMode 重挂载共享，避免空库并发 seed
const seedingProjectIds = new Set<number>()

type AssetsStepProps = {
  projectId: number
  onError: (m: string) => void
}

// 将接口返回规范为资产数组，避免 undefined.filter 崩溃
function normalizeAssetList(value: unknown): DramaAsset[] {
  return filterDramaLibraryAssets(Array.isArray(value) ? (value as DramaAsset[]) : [])
}

// 判断资产是否尚未出图（无有效封面/主图，上传或 AI 生成均视为已出图）
function needsImageGeneration(asset: DramaAsset): boolean {
  return dramaAssetNeedsImageGeneration(asset)
}

// 把模板中的 {var} 替换为加粗节点（用于带 <strong> 的统计行）
function renderStrongVars(template: string, vars: Record<string, ReactNode>): ReactNode[] {
  return template.split(/(\{\w+\})/).map((part, i) => {
    const key = part.match(/^\{(\w+)\}$/)?.[1]
    if (key && key in vars) return <strong key={i}>{vars[key]}</strong>
    return part
  })
}

// 渲染资产库步骤
export function AssetsStep({ projectId, onError }: AssetsStepProps) {
  /*
   * assets 项目资产
   * tab 当前分类
   * loading 首次加载
   * batchBusy 一键入队中
   * genOptions 生图选项
   * voiceAsset 打开音色弹窗的角色
   * detailAsset 打开详情操作框的资产
   * lightbox 图片放大预览
   * batchVoiceBusy 批量生成音色中
   * page 当前页码
   * pageSize 每页条数
   * genQueue 全局生图队列
   */
  const [assets, setAssets] = useState<DramaAsset[]>([])
  const [tab, setTab] = useState<AssetTabKey>('character')
  const [loading, setLoading] = useState(true)
  const [batchBusy, setBatchBusy] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE_DEFAULT)
  const [genOptions, setGenOptions] = useState<ImageGenerationOptions>(() =>
    defaultOptionsForAssetKind('character'),
  )
  const [voiceAsset, setVoiceAsset] = useState<DramaAsset | null>(null)
  const [detailAsset, setDetailAsset] = useState<DramaAsset | null>(null)
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null)
  const [voiceSynthBusyId, setVoiceSynthBusyId] = useState<number | null>(null)
  const [voicePromptDrafts, setVoicePromptDrafts] = useState<Record<number, string>>({})
  const [pickerOpen, setPickerOpen] = useState(false)
  const [reseedBusy, setReseedBusy] = useState(false)
  const [project, setProject] = useState<DramaProject | null>(null)
  const [selectedCharacterIds, setSelectedCharacterIds] = useState<number[]>([])
  const [characterVoiceBusyIds, setCharacterVoiceBusyIds] = useState<Set<number>>(() => new Set())
  const [batchVoiceBusy, setBatchVoiceBusy] = useState(false)
  const [narratorVoiceOpen, setNarratorVoiceOpen] = useState(false)
  const genQueue = useDramaImageGenQueue()
  const { t, m } = useI18n()
  const kinds = m.dramaAssets.kinds as Record<string, string>
  // 资产 type 展示名（未知 type 原样显示）
  const kindLabel = (type: string | null | undefined) => (type ? kinds[type.toLowerCase()] || type : '')

  useEffect(() => {
    async function enter() {
      setLoading(true)
      try {
        const p = await dramaApi.getProject(projectId).catch(() => null)
        setProject(p)
        const styleId = p ? getImageStyleId(p.script, p) : ''
        setGenOptions((prev) => ({
          ...defaultOptionsForAssetKind(tab),
          image_style_id: styleId || prev.image_style_id,
          model_id: prev.model_id,
          resolution: prev.resolution,
        }))
        let list = normalizeAssetList(
          await dramaApi.listAssets(projectId, { libraryOnly: true }),
        )
        // 仅首次（资产库为空且已有剧本摘要）自动从剧本抽取；之后需手动点「重新抽取资产」
        if (list.length === 0 && p?.script?.summary && !seedingProjectIds.has(projectId)) {
          seedingProjectIds.add(projectId)
          try {
            const seededResult = await dramaApi.seedAssets(projectId)
            list = normalizeAssetList(seededResult?.assets)
          } finally {
            seedingProjectIds.delete(projectId)
          }
        }
        setAssets(list)
        resumeDramaImageGensFromAssets(projectId, list, (next) => {
          setAssets((prev) => (prev ?? []).map((a) => (a.id === next.id ? next : a)))
        })
      } catch (err) {
        onError(err instanceof Error ? err.message : translate('dramaAssets.step.loadFailed'))
        try {
          const list = normalizeAssetList(await dramaApi.listAssets(projectId, { libraryOnly: true }))
          setAssets(list)
          resumeDramaImageGensFromAssets(projectId, list, (next) => {
          setAssets((prev) => (prev ?? []).map((a) => (a.id === next.id ? next : a)))
        })
        } catch {
          /* ignore */
        }
      } finally {
        setLoading(false)
      }
    }
    void enter()
  }, [projectId, onError])

  useEffect(() => {
    setGenOptions((prev) => ({
      ...defaultOptionsForAssetKind(tab),
      image_style_id: prev.image_style_id,
      model_id: prev.model_id,
      resolution: prev.resolution,
    }))
  }, [tab])

  useEffect(() => {
    if (tab !== 'character') {
      setSelectedCharacterIds([])
    }
    setPage(1)
  }, [tab])

  useEffect(() => {
    setPage(1)
  }, [pageSize])

  // 队列完成时把最新封面写回卡片
  useEffect(() => {
    const projectJobs = genQueue.filter((j) => j.projectId === projectId)
    const doneIds = new Set(
      projectJobs.filter((j) => j.status === 'done' || j.status === 'running').map((j) => j.assetId),
    )
    if (doneIds.size === 0) return
    let cancelled = false
    dramaApi
      .listAssets(projectId, { libraryOnly: true })
      .then((list) => {
        if (cancelled) return
        const next = normalizeAssetList(list)
        setAssets(next)
        setDetailAsset((prev) => (prev ? next.find((a) => a.id === prev.id) || prev : null))
      })
      .catch(() => {
        /* ignore */
      })
    return () => {
      cancelled = true
    }
  }, [genQueue, projectId])

  const assetList = assets ?? []
  // 旁白音色展示名：落库的中文默认名（如「旁白音色」）按界面语言显示
  const narrationVoiceRaw =
    project?.params && typeof project.params === 'object'
      ? ((project.params as Record<string, unknown>).narrationVoiceAudio as Record<string, unknown> | undefined)?.label
      : undefined
  const narrationVoiceLabel = narrationVoiceRaw
    ? displayDramaAssetName(String(narrationVoiceRaw))
    : t('dramaAssets.step.notSet')
  const filtered = assetList.filter((a) => {
    const type = (a.type || '').toLowerCase()
    if (tab === 'voice') return type === 'voice'
    return type === tab
  })
  const selectedCharacterAssets = assetList.filter(
    (a) => (a.type || '').toLowerCase() === 'character' && selectedCharacterIds.includes(a.id),
  )
  const busyAssetIds = new Set(
    genQueue
      .filter(
        (j) =>
          j.projectId === projectId && (j.status === 'queued' || j.status === 'running'),
      )
      .map((j) => j.assetId),
  )
  // 未出图：无有效 cover/url，且当前未在队列中
  const pending = filtered.filter((a) => needsImageGeneration(a) && !busyAssetIds.has(a.id))
  const queueBusy = busyAssetIds.size > 0
  const pageCount = pageCountOf(filtered.length, pageSize)
  const safePage = Math.min(page, pageCount)
  const pageItems = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return filtered.slice(start, start + pageSize)
  }, [filtered, safePage, pageSize])

  // 持久化项目画面风格
  async function persistStyle(styleId: string) {
    try {
      await dramaApi.updateScript(projectId, { image_style_id: styleId })
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.saveStyleFailed'))
    }
  }

  // 入队前校验余额（批量/单项共用）；成功时返回预检明细（含单张估算）
  async function ensureImageGenBalance(count: number): Promise<BillingPreflight | null> {
    try {
      return await api.billingPreflight({
        domain: 'drama',
        task_type: 'asset_image',
        count,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err || '')
      if (isBillingError(message)) return null
      if (await handleBillingError(err)) return null
      onError(message || t('dramaAssets.step.balanceCheckFailed'))
      return null
    }
  }

  async function notifyImageGenFailure(err: unknown) {
    const message = err instanceof Error ? err.message : String(err || '')
    if (isBillingError(message)) return
    if (isUpstreamAccountError(message)) {
      await alertDramaGenError(err)
      onError(formatDramaGenError(message).message)
      return
    }
    if (await handleBillingError(err)) return
    const view = formatDramaGenError(message)
    if (view.upstreamAccountBlocked || view.billingBlocked) {
      await alertDramaGenError(err)
    }
    onError(view.message || message || t('dramaAssets.step.imageGenFailed'))
  }

  // 加入全局生图队列（不互相顶掉）
  function enqueueOne(asset: DramaAsset, options = genOptions) {
    if (busyAssetIds.has(asset.id)) return
    void (async () => {
      if (!(await ensureImageGenBalance(1))) return
      try {
        const updated = await enqueueDramaImageGen({
          projectId,
          assetId: asset.id,
          assetName: asset.name || undefined,
          assetType: asset.type,
          prompt: readVisualPrompt(asset),
          options,
          onAssetUpdate: (next) => {
            setAssets((prev) => (prev ?? []).map((a) => (a.id === next.id ? next : a)))
          },
        })
        setAssets((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
      } catch (err) {
        await notifyImageGenFailure(err)
      }
    })()
  }

  // 一键只入队「当前分类下尚未出图」的资产（已有图 / 排队中跳过）
  async function batchGenerate() {
    const targets = filtered.filter(
      (a) => needsImageGeneration(a) && !busyAssetIds.has(a.id),
    )
    if (targets.length === 0) {
      onError(t('dramaAssets.step.noPendingInTab'))
      return
    }
    const pre = await ensureImageGenBalance(targets.length)
    if (!pre) return
    // 金额一律从「分」按当前展示货币格式化
    const unitText = formatFenActive(pre.unit_estimate_fen)
    const totalText = formatFenActive(pre.requested_total_fen)
    const balanceText = formatFenActive(pre.balance_fen)
    const ok = await dialog.confirm({
      title: t('dramaAssets.step.batchTitle'),
      message: t('dramaAssets.step.batchMessage', {
        tab: kinds[tab] || t('dramaAssets.step.categoryFallback'),
        count: targets.length,
        unit: unitText,
        total: totalText,
        balance: balanceText,
      }),
      confirmText: t('dramaAssets.step.startGenerate'),
    })
    if (!ok) return
    setBatchBusy(true)
    const tasks = targets.map((asset) =>
      enqueueDramaImageGen({
        projectId,
        assetId: asset.id,
        assetName: asset.name || undefined,
        assetType: asset.type,
        prompt: readVisualPrompt(asset),
        options: {
          ...genOptions,
          ...defaultOptionsForAssetKind(asset.type),
          image_style_id: genOptions.image_style_id,
          model_id: genOptions.model_id,
          resolution: genOptions.resolution,
        },
        onAssetUpdate: (next) => {
          setAssets((prev) => (prev ?? []).map((a) => (a.id === next.id ? next : a)))
        },
      }).then((updated) => {
        setAssets((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
      }),
    )
    void Promise.allSettled(tasks).then(async (results) => {
      setBatchBusy(false)
      const failed = results.find((r) => r.status === 'rejected')
      if (failed && failed.status === 'rejected') {
        await notifyImageGenFailure(failed.reason)
      }
    })
  }

  // 音色绑定成功后刷新列表项
  function handleVoiceBound(updated: DramaAsset) {
    setAssets((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
  }

  function handleVoiceCreated(voice: DramaAsset) {
    setAssets((prev) => {
      const list = prev ?? []
      if (list.some((a) => a.id === voice.id)) return list
      return [...list, voice]
    })
  }

  // 一键 AI 生成音色并绑定（各角色独立 busy，互不阻塞）
  async function handleGenerateCharacterVoice(asset: DramaAsset) {
    if (characterVoiceBusyIds.has(asset.id) || batchVoiceBusy) return
    setCharacterVoiceBusyIds((prev) => new Set(prev).add(asset.id))
    try {
      const { character, voice } = await generateAndBindCharacterVoice(projectId, asset)
      handleVoiceBound(character)
      handleVoiceCreated(voice)
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.voiceGenFailed'))
    } finally {
      setCharacterVoiceBusyIds((prev) => {
        const next = new Set(prev)
        next.delete(asset.id)
        return next
      })
    }
  }

  // 批量按角色设定生成音色
  async function batchGenerateCharacterVoices() {
    if (batchVoiceBusy || selectedCharacterAssets.length === 0) return
    const ok = await dialog.confirm({
      title: t('dramaAssets.step.batchVoiceTitle'),
      message: t('dramaAssets.step.batchVoiceMessage', { count: selectedCharacterAssets.length }),
      confirmText: t('dramaAssets.step.startGenerate'),
    })
    if (!ok) return
    setBatchVoiceBusy(true)
    let failCount = 0
    for (const asset of selectedCharacterAssets) {
      setCharacterVoiceBusyIds((prev) => new Set(prev).add(asset.id))
      try {
        const { character, voice } = await generateAndBindCharacterVoice(projectId, asset)
        handleVoiceBound(character)
        handleVoiceCreated(voice)
      } catch {
        failCount += 1
      } finally {
        setCharacterVoiceBusyIds((prev) => {
          const next = new Set(prev)
          next.delete(asset.id)
          return next
        })
      }
    }
    setBatchVoiceBusy(false)
    setSelectedCharacterIds([])
    if (failCount > 0) {
      onError(t('dramaAssets.step.batchVoiceFailed', { count: failCount }))
    }
  }

  // 从全局资产库导入到当前项目
  async function handleImportFromLibrary(source: DramaAsset) {
    const dup = assetList.some(
      (a) =>
        (a.name || '').trim() === (source.name || '').trim() &&
        (a.type || '') === (source.type || ''),
    )
    if (dup) {
      const ok = await dialog.confirm({
        title: t('dramaAssets.step.dupTitle'),
        message: t('dramaAssets.step.dupMessage', { name: source.name || '' }),
        confirmText: t('dramaAssets.step.dupConfirm'),
      })
      if (!ok) throw new Error(t('dramaAssets.step.cancelled'))
    }
    const created = await importGlobalAssetToProject(projectId, source)
    setAssets((prev) => [...(prev ?? []), created])
  }

  // 新增音色资产
  async function handleAddVoice() {
    const name = await dialog.prompt({
      title: t('dramaAssets.step.addVoiceTitle'),
      message: t('dramaAssets.step.addVoiceMessage'),
      placeholder: t('dramaAssets.step.addVoicePlaceholder'),
      confirmText: t('dramaAssets.common.create'),
    })
    if (!name?.trim()) return
    try {
      const created = await dramaApi.createAsset({
        project_id: projectId,
        type: 'voice',
        asset_type: 'audio',
        name: name.trim(),
        params: { voicePrompt: '' },
      })
      setAssets((prev) => [...(prev ?? []), created])
      setVoicePromptDrafts((prev) => ({ ...prev, [created.id]: '' }))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.createVoiceFailed'))
    }
  }

  // 保存音色描述到资产 params
  async function persistVoicePrompt(asset: DramaAsset, prompt: string) {
    const nextParams = { ...(asset.params || {}), voicePrompt: prompt.trim() }
    const updated = await dramaApi.updateAsset(asset.id, { params: nextParams })
    setAssets((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
  }

  // 按提示词合成 voice 资产试听
  async function handleSynthVoice(asset: DramaAsset) {
    const prompt = (voicePromptDrafts[asset.id] ?? readVoicePrompt(asset)).trim()
    if (!prompt) {
      onError(t('dramaAssets.step.voicePromptRequired'))
      return
    }
    setVoiceSynthBusyId(asset.id)
    try {
      await persistVoicePrompt(asset, prompt)
      const result = await dramaApi.generateVoice({
        project_id: projectId,
        asset_id: asset.id,
        voice_prompt: prompt,
      })
      setAssets((prev) => (prev ?? []).map((a) => (a.id === asset.id ? result.asset : a)))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.voiceSynthFailed'))
    } finally {
      setVoiceSynthBusyId(null)
    }
  }

  // 删除音色资产
  async function handleDeleteVoice(asset: DramaAsset) {
    const ok = await dialog.confirm({
      title: t('dramaAssets.step.deleteVoiceTitle'),
      message: t('dramaAssets.step.deleteVoiceMessage', {
        name: displayDramaAssetName(asset.name),
      }),
      tone: 'danger',
      confirmText: t('common.delete'),
    })
    if (!ok) return
    try {
      await dramaApi.deleteAsset(asset.id)
      setAssets((prev) => (prev ?? []).filter((a) => a.id !== asset.id))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.deleteFailed'))
    }
  }

  // 新增角色
  async function handleAddCharacter() {
    const name = await dialog.prompt({
      title: t('dramaAssets.step.addCharacterTitle'),
      message: t('dramaAssets.step.addCharacterMessage'),
      placeholder: t('dramaAssets.step.addCharacterPlaceholder'),
      confirmText: t('dramaAssets.common.create'),
    })
    if (!name?.trim()) return
    try {
      const created = await dramaApi.createAsset({
        project_id: projectId,
        type: 'character',
        asset_type: 'image',
        name: name.trim(),
        params: { kind: 'character' },
      })
      setAssets((prev) => [...(prev ?? []), created])
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.createCharacterFailed'))
    }
  }

  // 删除角色
  async function handleDeleteCharacter(asset: DramaAsset) {
    const ok = await dialog.confirm({
      title: t('dramaAssets.step.deleteCharacterTitle'),
      message: t('dramaAssets.step.deleteCharacterMessage', {
        name: displayDramaAssetName(asset.name),
      }),
      tone: 'danger',
      confirmText: t('common.delete'),
    })
    if (!ok) return
    if (busyAssetIds.has(asset.id)) {
      onError(t('dramaAssets.step.characterBusy'))
      return
    }
    try {
      await dramaApi.deleteAsset(asset.id)
      setAssets((prev) => (prev ?? []).filter((a) => a.id !== asset.id))
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.common.deleteFailed'))
    }
  }

  // 抽取结果摘要：新建 / 刷新提示词 / 更新道具
  function reseedSummaryText(created: number, refreshed: number, propsUpdated: number): string {
    const parts = [
      t('dramaAssets.step.reseedCreated', { count: created }),
      t('dramaAssets.step.reseedRefreshed', { count: refreshed }),
    ]
    if (propsUpdated > 0) {
      parts.push(t('dramaAssets.step.reseedProps', { count: propsUpdated }))
    }
    return t('dramaAssets.step.reseedSummary', { parts: parts.join(t('dramaAssets.step.listSep')) })
  }

  // AI 刷新失败的资产列表（最多列 5 项）
  function reseedLlmErrorsText(llmErrors: string[]): string {
    const more =
      llmErrors.length > 5 ? t('dramaAssets.step.reseedMore', { count: llmErrors.length }) : ''
    return t('dramaAssets.step.reseedLlmErrors', { list: llmErrors.slice(0, 5).join('\n') + more })
  }

  // 重新从剧本抽取资产并 AI 刷新全部生图提示词
  async function handleReseedAssets() {
    if (reseedBusy || batchBusy) return
    const ok = await dialog.confirm({
      title: t('dramaAssets.step.reseedTitle'),
      message: t('dramaAssets.step.reseedMessage'),
      confirmText: t('dramaAssets.step.reseedConfirm'),
      tone: 'danger',
    })
    if (!ok) return
    setReseedBusy(true)
    try {
      const result = await dramaApi.seedAssets(projectId, {
        refreshPrompts: true,
        reextractProps: true,
      })
      if (result.status === 'generating') {
        let seedStatus = 'generating'
        for (let i = 0; i < 90; i += 1) {
          await new Promise((r) => window.setTimeout(r, 2000))
          const p = await dramaApi.getProject(projectId)
          seedStatus = String(
            (p.params as Record<string, unknown> | undefined)?.assets_seed_status || '',
          )
          if (seedStatus === 'done' || seedStatus === 'failed') break
        }
        const list = normalizeAssetList(
          await dramaApi.listAssets(projectId, { libraryOnly: true }),
        )
        setAssets(list)
        const p = await dramaApi.getProject(projectId)
        const params = (p.params || {}) as Record<string, unknown>
        const created = Number(params.assets_seed_created ?? 0)
        const refreshed = Number(params.assets_seed_refreshed ?? 0)
        const propsUpdated = Number(params.assets_seed_props_updated ?? 0)
        const llmErrors = Array.isArray(params.assets_seed_llm_errors)
          ? (params.assets_seed_llm_errors as string[])
          : []
        const failed = seedStatus === 'failed'
        let detail = failed
          ? localizeStoredError(
              params.assets_seed_error ? String(params.assets_seed_error) : '',
              typeof params.assets_seed_error_code === 'string' ? params.assets_seed_error_code : undefined,
              params.assets_seed_error_params,
            ) || t('dramaAssets.step.reseedFailedFallback')
          : reseedSummaryText(created, refreshed, propsUpdated)
        if (!failed && created === 0 && refreshed === 0 && llmErrors.length === 0) {
          detail += t('dramaAssets.step.reseedNothing')
        } else if (!failed && llmErrors.length > 0) {
          detail += reseedLlmErrorsText(llmErrors)
        } else if (!failed) {
          detail += t('dramaAssets.step.reseedHint')
        }
        await dialog.alert({
          title:
            failed || llmErrors.length > 0
              ? t('dramaAssets.step.reseedPartialTitle')
              : t('dramaAssets.step.reseedDoneTitle'),
          message: detail,
          tone: failed || llmErrors.length > 0 ? 'danger' : 'success',
        })
        return
      }
      setAssets(normalizeAssetList(result?.assets))
      const created = result.created_count ?? 0
      const refreshed = result.prompts_refreshed ?? 0
      const propsUpdated = result.props_updated ?? 0
      const llmErrors = Array.isArray(result.llm_errors) ? result.llm_errors : []
      let detail = reseedSummaryText(created, refreshed, propsUpdated)
      if (created === 0 && refreshed === 0 && llmErrors.length === 0) {
        detail += t('dramaAssets.step.reseedNothing')
      } else if (llmErrors.length > 0) {
        detail += reseedLlmErrorsText(llmErrors)
      } else {
        detail += t('dramaAssets.step.reseedHint')
      }
      await dialog.alert({
        title:
          llmErrors.length > 0
            ? t('dramaAssets.step.reseedPartialTitle')
            : t('dramaAssets.step.reseedDoneTitle'),
        message: detail,
        tone: llmErrors.length > 0 ? 'danger' : 'success',
      })
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.reseedError'))
    } finally {
      setReseedBusy(false)
    }
  }

  // 卡片按钮文案（已有图时显示「重新生成形象」）
  function genButtonLabel(asset: DramaAsset): string {
    const job = genQueue.find(
      (j) =>
        j.assetId === asset.id && (j.status === 'queued' || j.status === 'running'),
    )
    let queueLabel: string | null = null
    if (job) {
      if (job.status === 'running') queueLabel = t('dramaAssets.common.generating')
      else {
        const queuedOnly = genQueue.filter((j) => j.status === 'queued' || j.status === 'running')
        const pos = queuedOnly.findIndex((j) => j.id === job.id) + 1
        queueLabel =
          pos > 1 ? t('dramaAssets.imageGen.queuedPos', { pos }) : t('dramaAssets.imageGen.queued')
      }
    }
    return dramaAssetImageGenButtonLabel(asset, queueLabel)
  }

  const imageAssetCount = assetList.filter((a) => {
    const type = (a.type || '').toLowerCase()
    return !['voice', 'video', 'audio', 'text'].includes(type)
  }).length

  return (
    <div className="drama-assets-step">
      <header className="drama-assets-hero">
        <div className="drama-step-hero-main">
          <div className="drama-step-hero-icon" aria-hidden>
            <Boxes size={22} strokeWidth={1.75} />
          </div>
          <div>
            <h2>{t('dramaAssets.step.heroTitle')}</h2>
            <p className="drama-step-hero-sub">
              {renderStrongVars(t('dramaAssets.step.heroSub'), {
                total: assetList.length,
                filtered: filtered.length,
                pending: pending.length,
              })}
            </p>
          </div>
        </div>
      </header>

      <div className="drama-assets-tips" role="note">
        <Sparkles size={15} strokeWidth={1.75} aria-hidden />
        <span>{t('dramaAssets.step.tips')}</span>
      </div>

      <div className="drama-assets-toolbar">
        <div className="drama-asset-tabs">
          {ASSET_TABS.map((key) => (
            <button
              key={key}
              type="button"
              className={tab === key ? 'active' : ''}
              onClick={() => setTab(key)}
            >
              {kinds[key]}
            </button>
          ))}
        </div>
        <div className="drama-actions">
          {tab === 'character' ? (
            <button type="button" className="pf-btn" onClick={() => void handleAddCharacter()}>
              {t('dramaAssets.step.addCharacter')}
            </button>
          ) : null}
          {DRAMA_VOICE_BINDING_ENABLED && tab === 'voice' ? (
            <button type="button" className="pf-btn" onClick={() => void handleAddVoice()}>
              {t('dramaAssets.step.addVoice')}
            </button>
          ) : null}
          {DRAMA_VOICE_BINDING_ENABLED && tab !== 'voice' ? (
            <button
              type="button"
              className="pf-btn"
              onClick={() => setNarratorVoiceOpen(true)}
              title={t('dramaAssets.step.narratorHint')}
              disabled={!project}
            >
              {t('dramaAssets.step.narratorButton', { label: narrationVoiceLabel })}
            </button>
          ) : null}
          <button type="button" className="pf-btn" onClick={() => setPickerOpen(true)}>
            {t('dramaAssets.step.pickFromLibrary')}
          </button>
          <Link className="pf-btn" to="/drama/assets">
            {t('dramaAssets.step.browseAll')}
          </Link>
          <button
            type="button"
            className="pf-btn"
            disabled={reseedBusy || batchBusy}
            onClick={() => void handleReseedAssets()}
          >
            {reseedBusy
              ? t('dramaAssets.step.reseeding', { count: Math.max(imageAssetCount, 1) })
              : t('dramaAssets.step.reseedTitle')}
          </button>
          {/* 一键生成未出图：暂时隐藏，恢复时去掉 && false */}
          {tab !== 'voice' && false ? (
            <button
              type="button"
              className="drama-btn-primary"
              disabled={batchBusy || pending.length === 0}
              onClick={() => void batchGenerate()}
              title={
                pending.length > 0
                  ? t('dramaAssets.step.batchHintHas', { count: pending.length })
                  : t('dramaAssets.step.batchHintNone')
              }
            >
              {batchBusy || queueBusy
                ? t('dramaAssets.step.generatingCount', { count: busyAssetIds.size })
                : pending.length > 0
                  ? t('dramaAssets.step.batchButtonCount', { count: pending.length })
                  : t('dramaAssets.step.batchButton')}
            </button>
          ) : null}

          {DRAMA_VOICE_BINDING_ENABLED && tab === 'character' ? (
            <button
              type="button"
              className="pf-btn pf-btn-lime"
              disabled={batchBusy || batchVoiceBusy || selectedCharacterIds.length === 0}
              onClick={() => void batchGenerateCharacterVoices()}
              title={t('dramaAssets.step.batchVoiceHint')}
            >
              {batchVoiceBusy
                ? t('dramaAssets.step.batchVoiceBusy')
                : t('dramaAssets.step.batchVoiceButton', { count: selectedCharacterIds.length })}
            </button>
          ) : null}
          <Link className="pf-btn" to={`/drama/projects/${projectId}/canvas`}>
            {t('dramaAssets.step.openCanvas')}
          </Link>
        </div>
      </div>

      {tab !== 'voice' ? (
        <div className="drama-assets-gen-opts">
          <DramaImageGenOptionsBar
            value={genOptions}
            onChange={setGenOptions}
            disabled={batchBusy}
            onStylePersist={persistStyle}
          />
        </div>
      ) : null}

      {loading ? <p className="drama-muted">{t('dramaAssets.step.loading')}</p> : null}

      {!loading && filtered.length > 0 ? (
        <p className="drama-muted drama-assets-page-meta">
          {t('dramaAssets.step.pageMeta', {
            page: safePage,
            pageCount,
            count: filtered.length,
          })}
        </p>
      ) : null}

      <div className={`drama-asset-grid${tab === 'voice' ? ' is-voice' : ''}`}>
        {pageItems.map((asset) => {
          if (tab === 'voice') {
            const promptValue = voicePromptDrafts[asset.id] ?? readVoicePrompt(asset)
            const synthBusy = voiceSynthBusyId === asset.id
            return (
              <DramaVoiceAssetCard
                key={asset.id}
                asset={asset}
                promptValue={promptValue}
                synthBusy={synthBusy}
                onPromptChange={(value) =>
                  setVoicePromptDrafts((prev) => ({
                    ...prev,
                    [asset.id]: value,
                  }))
                }
                onPromptBlur={() => {
                  const draft = (voicePromptDrafts[asset.id] ?? '').trim()
                  if (draft && draft !== readVoicePrompt(asset)) {
                    void persistVoicePrompt(asset, draft).catch((err) =>
                      onError(err instanceof Error ? err.message : t('dramaAssets.common.saveFailed')),
                    )
                  }
                }}
                onSynth={() => void handleSynthVoice(asset)}
                onDelete={() => void handleDeleteVoice(asset)}
                onError={onError}
              />
            )
          }

          const mediaSrc = resolveDramaAssetPreviewUrl(asset)
          const voice = readAssetVoiceBinding(asset)
          const isCharacter = (asset.type || '').toLowerCase() === 'character'
          const busy = busyAssetIds.has(asset.id)
          return (
            <article
              key={asset.id}
              className="drama-asset-card drama-asset-card-clickable"
              role="button"
              tabIndex={0}
              onClick={() => setDetailAsset(asset)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setDetailAsset(asset)
                }
              }}
            >
              {mediaSrc ? (
                <button
                  type="button"
                  className="drama-asset-thumb-btn"
                  title={t('dramaAssets.common.clickToZoom')}
                  onClick={(e) => {
                    e.stopPropagation()
                    setLightbox({ src: mediaSrc, alt: asset.name ? displayDramaAssetName(asset.name) : t('dramaAssets.common.preview') })
                  }}
                >
                  <img key={mediaSrc} src={mediaSrc} alt={asset.name ? displayDramaAssetName(asset.name) : ''} />
                </button>
              ) : (
                <div className="drama-asset-placeholder">{kindLabel(asset.type) || 'asset'}</div>
              )}
              <h3>{displayDramaAssetName(asset.name)}</h3>
              <p>
                {kindLabel(asset.type)}
                {isCharacter && voice ? ` · ${displayDramaAssetName(voice.label)}` : ''}
              </p>
              <div
                className="drama-asset-card-actions"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => e.stopPropagation()}
              >
                {tab === 'character' && isCharacter ? (
                  <label
                    className="drama-voice-multi-select"
                    style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginRight: 8, cursor: 'pointer' }}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCharacterIds.includes(asset.id)}
                      onChange={(e) => {
                        e.stopPropagation()
                        setSelectedCharacterIds((prev) =>
                          prev.includes(asset.id) ? prev.filter((id) => id !== asset.id) : [...prev, asset.id],
                        )
                      }}
                    />
                    <span className="drama-muted">{t('dramaAssets.step.select')}</span>
                  </label>
                ) : null}
                <button
                  type="button"
                  className="pf-btn pf-btn-sm"
                  disabled={busy || batchBusy}
                  onClick={() => enqueueOne(asset)}
                >
                  {genButtonLabel(asset)}
                </button>
                {isCharacter ? (
                  <>
                    {DRAMA_VOICE_BINDING_ENABLED ? (
                      voice ? (
                        <CharacterVoicePreviewButton
                          url={voice.url}
                          label={displayDramaAssetName(voice.label)}
                          onError={onError}
                        />
                      ) : (
                        <button
                          type="button"
                          className="pf-btn pf-btn-sm pf-btn-lime"
                          disabled={
                            batchBusy ||
                            batchVoiceBusy ||
                            characterVoiceBusyIds.has(asset.id)
                          }
                          onClick={() => void handleGenerateCharacterVoice(asset)}
                        >
                          {characterVoiceBusyIds.has(asset.id)
                            ? t('dramaAssets.common.generating')
                            : t('dramaAssets.step.generateVoice')}
                        </button>
                      )
                    ) : null}
                    <button
                      type="button"
                      className="pf-btn pf-btn-sm drama-btn-danger-text"
                      disabled={busy || batchBusy || batchVoiceBusy}
                      onClick={() => void handleDeleteCharacter(asset)}
                    >
                      {t('common.delete')}
                    </button>
                  </>
                ) : null}
              </div>
            </article>
          )
        })}
      </div>
      {!loading && filtered.length === 0 ? <p className="drama-muted">{t('dramaAssets.step.empty')}</p> : null}

      {!loading && filtered.length > 0 ? (
        <Pagination
          page={safePage}
          pageCount={pageCount}
          total={filtered.length}
          pageSize={pageSize}
          pageSizeOptions={PAGE_SIZE_OPTIONS}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPage(1)
          }}
          onChange={setPage}
          ariaLabel={t('dramaAssets.common.paginationAria')}
          className="drama-assets-pagination"
        />
      ) : null}

      {detailAsset && (detailAsset.type || '').toLowerCase() !== 'voice' ? (
        <DramaAssetDetailModal
          asset={detailAsset}
          open
          busy={busyAssetIds.has(detailAsset.id)}
          genLabel={genButtonLabel(detailAsset)}
          onClose={() => setDetailAsset(null)}
          onUpdated={(updated) => {
            setAssets((prev) => (prev ?? []).map((a) => (a.id === updated.id ? updated : a)))
            setDetailAsset(updated)
          }}
          onGenerate={(a) => enqueueOne(a)}
          onBindVoice={DRAMA_VOICE_BINDING_ENABLED ? (a) => setVoiceAsset(a) : undefined}
          onDelete={(a) => {
            setDetailAsset(null)
            void handleDeleteCharacter(a)
          }}
          onError={onError}
        />
      ) : null}

      {lightbox ? (
        <DramaImageLightbox
          src={lightbox.src}
          alt={lightbox.alt}
          onClose={() => setLightbox(null)}
        />
      ) : null}

      {DRAMA_VOICE_BINDING_ENABLED && voiceAsset ? (
        <CharacterVoiceBindModal
          asset={voiceAsset}
          projectId={projectId}
          open
          onClose={() => setVoiceAsset(null)}
          onBound={(updated) => {
            handleVoiceBound(updated)
            setDetailAsset((prev) => (prev?.id === updated.id ? updated : prev))
          }}
          onError={onError}
        />
      ) : null}

      {DRAMA_VOICE_BINDING_ENABLED && project ? (
        <NarratorVoiceBindModal
          project={project}
          open={narratorVoiceOpen}
          onClose={() => setNarratorVoiceOpen(false)}
          onUpdated={(p) => setProject(p)}
          onError={onError}
        />
      ) : null}

      <GlobalAssetPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        projectId={projectId}
        defaultTab={tab === 'voice' ? 'voice' : tab}
        title={t('dramaAssets.step.importTitle')}
        confirmLabel={t('dramaAssets.step.importConfirm')}
        onPick={handleImportFromLibrary}
      />
    </div>
  )
}
