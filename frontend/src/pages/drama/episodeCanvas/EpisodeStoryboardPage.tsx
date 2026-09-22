/** 分集分镜故事板全屏画布：按分镜连线，节点含视频 / 出境资产 / 提示词 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ChevronLeft } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  dramaApi,
  resolveDramaAssetPreviewUrl,
  type DramaAsset,
  type DramaEpisode,
  type DramaFragment,
} from '../../../api/drama'
import Modal from '../../../components/ui/Modal'
import {
  collectFragmentAssetIds,
  normalizeAssetTab,
} from '../dramaEpisodeEditUtils'
import RequireAuth from '../RequireAuth'
import {
  buildEpisodeFragmentFlow,
  type EpisodeFragmentNodeData,
  type EpisodeFlowNodeData,
} from './buildEpisodeFlow'
import { EpisodeAssetNode } from './EpisodeAssetNode'
import { EpisodeFragmentNode } from './EpisodeFragmentNode'
import { useI18n } from '../../../i18n/context'
import { getActiveLocale } from '../../../i18n/detect'
import { messages } from '../../../i18n/messages'
import './episodeCanvas.css'

const SAVE_DEBOUNCE_MS = 800

// 正文补上 @asset 提及
function ensureAssetMention(content: string, assetId: number): string {
  const token = `@asset:${assetId}`
  if ((content || '').includes(token)) return content || ''
  const trimmed = (content || '').trimEnd()
  return trimmed ? `${trimmed} ${token}` : token
}

// 正文去掉 @asset 提及
function removeAssetMention(content: string, assetId: number): string {
  return (content || '')
    .replace(new RegExp(`\\s*@asset:${assetId}\\b`, 'g'), ' ')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

// 鉴权后进入分镜故事板
export default function EpisodeStoryboardPage() {
  return (
    <RequireAuth>
      <ReactFlowProvider>
        <EpisodeStoryboardInner />
      </ReactFlowProvider>
    </RequireAuth>
  )
}

// 加载分集并渲染全屏故事板
function EpisodeStoryboardInner() {
  const { projectId, episodeId } = useParams()
  const pid = Number(projectId)
  const eid = Number(episodeId)
  const navigate = useNavigate()
  const { fitView } = useReactFlow()
  const { t } = useI18n()

  /*
   * episode / fragments / assets 数据
   * linkTargetFragId 正在选资产关联的分镜
   * dirty / busy / error / status 状态
   */
  const [episode, setEpisode] = useState<DramaEpisode | null>(null)
  const [fragments, setFragments] = useState<DramaFragment[]>([])
  const [assets, setAssets] = useState<DramaAsset[]>([])
  const [linkTargetFragId, setLinkTargetFragId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // status 为空或 'saved'（展示时翻译）
  const [status, setStatus] = useState<'' | 'saved'>('')
  const [dirty, setDirty] = useState(false)
  const fittedRef = useRef(false)
  const fragmentsRef = useRef<DramaFragment[]>([])
  const assetsRef = useRef<DramaAsset[]>([])
  const saveTimer = useRef<number | null>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<EpisodeFlowNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    fragmentsRef.current = fragments
  }, [fragments])

  useEffect(() => {
    assetsRef.current = assets
  }, [assets])

  // 结构键：成片 + 关联资产变化时重建；提示词编辑走局部更新
  const structureKey = fragments
    .map((f) => {
      const aids = collectFragmentAssetIds(f).join(',')
      return `${f.id}:${f.sort_order}:${f.video || ''}:${f.cover || ''}:${f.duration_sec ?? 0}:${aids}`
    })
    .join('|')

  useEffect(() => {
    const flow = buildEpisodeFragmentFlow(fragmentsRef.current, assetsRef.current)
    setNodes(flow.nodes)
    setEdges(flow.edges)
  }, [structureKey, assets, setNodes, setEdges])

  useEffect(() => {
    fittedRef.current = false
  }, [eid])

  useEffect(() => {
    if (fittedRef.current || nodes.length === 0) return
    fittedRef.current = true
    void fitView({ padding: 0.22, duration: 280 })
  }, [nodes.length, fitView])

  // 拉取分集 + 项目资产
  useEffect(() => {
    if (!eid || !pid) return
    let cancelled = false
    setBusy(true)
    setError('')
    Promise.all([dramaApi.getEpisode(eid), dramaApi.listAssets(pid)])
      .then(([ep, assetList]) => {
        if (cancelled) return
        setEpisode(ep)
        setFragments(ep.fragments || [])
        setAssets(assetList || [])
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : messages[getActiveLocale()].dramaCanvas.episode.loadFailed)
      })
      .finally(() => {
        if (!cancelled) setBusy(false)
      })
    return () => {
      cancelled = true
      if (saveTimer.current) window.clearTimeout(saveTimer.current)
    }
  }, [eid, pid])

  // 持久化全部分镜（保序，保留成片与引用）
  const persistFragments = useCallback(
    async (next: DramaFragment[]) => {
      if (!eid) return
      setBusy(true)
      setError('')
      try {
        const saved = await dramaApi.saveFragments(
          eid,
          next.map((f, index) => {
            const prevParams =
              f.params && typeof f.params === 'object' && !Array.isArray(f.params)
                ? (f.params as Record<string, unknown>)
                : {}
            return {
              id: typeof f.id === 'number' && f.id > 0 ? f.id : undefined,
              sort_order: index,
              content: f.content || '',
              cover: f.cover || '',
              video: f.video || '',
              duration_sec: f.duration_sec ?? 8,
              params: prevParams,
              asset_ids: collectFragmentAssetIds(f),
            }
          }),
        )
        setEpisode(saved)
        setFragments(saved.fragments || [])
        setDirty(false)
        setStatus('saved')
        window.setTimeout(() => setStatus(''), 1600)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('dramaCanvas.episode.saveFailed'))
      } finally {
        setBusy(false)
      }
    },
    [eid, t],
  )

  // 防抖保存
  const scheduleSave = useCallback(() => {
    setDirty(true)
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      void persistFragments(fragmentsRef.current)
    }, SAVE_DEBOUNCE_MS)
  }, [persistFragments])

  // 刷新单个分镜节点提示词（关联资产变化靠 structureKey 重建）
  const patchFragmentPrompt = useCallback(
    (fragmentId: number, content: string) => {
      setNodes((prev) =>
        prev.map((node) => {
          if (node.type !== 'episodeFragment') return node
          const data = node.data as EpisodeFragmentNodeData
          if (data.fragmentId !== fragmentId) return node
          return { ...node, data: { ...data, content } }
        }),
      )
    },
    [setNodes],
  )

  // 改提示词
  const handlePromptChange = useCallback(
    (fragmentId: number, content: string) => {
      setFragments((prev) =>
        prev.map((f) => {
          if (f.id !== fragmentId) return f
          const updated = { ...f, content }
          return { ...updated, asset_ids: collectFragmentAssetIds(updated) }
        }),
      )
      patchFragmentPrompt(fragmentId, content)
      scheduleSave()
    },
    [patchFragmentPrompt, scheduleSave],
  )

  // 取消关联出境资产
  const handleUnlinkAsset = useCallback(
    (fragmentId: number, assetId: number) => {
      setFragments((prev) =>
        prev.map((f) => {
          if (f.id !== fragmentId) return f
          const content = removeAssetMention(f.content || '', assetId)
          const asset_ids = (f.asset_ids || []).filter((id) => id !== assetId)
          return { ...f, content, asset_ids }
        }),
      )
      scheduleSave()
    },
    [scheduleSave],
  )

  // 打开关联选择
  const handleRequestLinkAsset = useCallback((fragmentId: number) => {
    setLinkTargetFragId(fragmentId)
  }, [])

  // 确认关联资产
  const handlePickAsset = useCallback(
    (asset: DramaAsset) => {
      if (linkTargetFragId == null) return
      const fragmentId = linkTargetFragId
      setFragments((prev) =>
        prev.map((f) => {
          if (f.id !== fragmentId) return f
          const content = ensureAssetMention(f.content || '', asset.id)
          const asset_ids = Array.from(new Set([...(f.asset_ids || []), asset.id]))
          return { ...f, content, asset_ids }
        }),
      )
      setLinkTargetFragId(null)
      scheduleSave()
    },
    [linkTargetFragId, scheduleSave],
  )

  const nodeTypes: NodeTypes = useMemo(
    () => ({
      episodeFragment: (props) => (
        <EpisodeFragmentNode
          {...props}
          onPromptChange={handlePromptChange}
          onRequestLinkAsset={handleRequestLinkAsset}
        />
      ),
      episodeAsset: (props) => (
        <EpisodeAssetNode {...props} onUnlinkAsset={handleUnlinkAsset} />
      ),
    }),
    [handlePromptChange, handleRequestLinkAsset, handleUnlinkAsset],
  )

  const linkFrag = fragments.find((f) => f.id === linkTargetFragId) || null
  const linkedIdSet = new Set(linkFrag ? collectFragmentAssetIds(linkFrag) : [])
  const pickerAssets = assets.filter((a) => {
    const tab = normalizeAssetTab(a.type || '')
    return Boolean(tab) && !linkedIdSet.has(a.id)
  })

  const backHref = `/drama/projects/${pid}/episodes/${eid}`

  // 资产分类展示名：已知分类翻译，其余回退原始类型
  const assetTypeLabel = (type: string | null | undefined) => {
    const tab = normalizeAssetTab(type || '')
    if (tab) return t(`dramaCanvas.assetTab.${tab}`)
    return type || t('dramaCanvas.episode.asset')
  }

  return (
    <div className="ep-storyboard-page">
      <header className="ep-storyboard-topbar">
        <div className="ep-storyboard-topbar-left">
          <button
            type="button"
            className="ep-storyboard-back"
            aria-label={t('dramaCanvas.episode.back')}
            title={t('dramaCanvas.episode.back')}
            onClick={() => navigate(backHref)}
          >
            <ChevronLeft size={20} strokeWidth={1.8} />
          </button>
          <div className="ep-storyboard-title">
            <strong>{episode?.name || t('dramaCanvas.episode.episodeFallback', { id: eid })}</strong>
            <span>
              {t('dramaCanvas.episode.subtitle', { count: fragments.length })}
              {dirty
                ? ` · ${t('dramaCanvas.episode.unsaved')}`
                : status
                  ? ` · ${t('dramaCanvas.episode.saved')}`
                  : ''}
            </span>
          </div>
        </div>
        <div className="ep-storyboard-actions">
          <button
            type="button"
            className="ep-storyboard-btn ghost"
            onClick={() => navigate(`/drama/projects/${pid}/canvas`)}
          >
            {t('dramaCanvas.episode.assetCanvas')}
          </button>
          <button
            type="button"
            className="ep-storyboard-btn dark"
            disabled={busy || !dirty}
            onClick={() => void persistFragments(fragments)}
          >
            {busy ? t('dramaCanvas.episode.saving') : t('dramaCanvas.episode.save')}
          </button>
        </div>
      </header>

      <div className="ep-storyboard-flow">
        {fragments.length === 0 && !busy ? (
          <div className="ep-storyboard-empty">
            <strong>{t('dramaCanvas.episode.emptyTitle')}</strong>
            <span>{t('dramaCanvas.episode.emptyHint')}</span>
          </div>
        ) : null}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.35}
          maxZoom={1.6}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'default' }}
        >
          <Background gap={20} size={1} color="#dbe2ea" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable />
        </ReactFlow>
        {error ? (
          <p className="ep-storyboard-toast" role="alert">
            {error}
          </p>
        ) : null}
        {busy && fragments.length === 0 ? (
          <p className="ep-storyboard-toast">{t('dramaCanvas.episode.loading')}</p>
        ) : null}
      </div>

      <Modal
        open={linkTargetFragId != null}
        onClose={() => setLinkTargetFragId(null)}
        title={t('dramaCanvas.episode.linkAssets')}
        size="lg"
      >
        <p className="ep-storyboard-picker-hint">{t('dramaCanvas.episode.pickerHint')}</p>
        {pickerAssets.length === 0 ? (
          <p className="ep-storyboard-picker-empty">{t('dramaCanvas.episode.pickerEmpty')}</p>
        ) : (
          <div className="ep-storyboard-picker-grid">
            {pickerAssets.map((asset) => {
              const cover = resolveDramaAssetPreviewUrl(asset)
              return (
                <button
                  key={asset.id}
                  type="button"
                  className="ep-storyboard-picker-card"
                  onClick={() => handlePickAsset(asset)}
                >
                  <div className="ep-storyboard-picker-thumb">
                    {cover ? <img src={cover} alt="" /> : <span>{(asset.name || '?')[0]}</span>}
                  </div>
                  <strong>{asset.name || t('dramaCanvas.episode.assetFallback', { id: asset.id })}</strong>
                  <em>{assetTypeLabel(asset.type)}</em>
                </button>
              )
            })}
          </div>
        )}
      </Modal>
    </div>
  )
}
