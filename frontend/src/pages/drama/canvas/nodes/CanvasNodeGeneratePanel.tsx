/** 选中节点底部：AI 提示词浮动面板（生图 / 生视频） */
import { useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from 'react'
import { ArrowUp, CircleHelp, Loader2, Sparkles, Wand2 } from 'lucide-react'
import { SeedanceRulesModal } from '../../../../components/drama/SeedanceRulesModal'
import { useCanvasStore } from '../CanvasStore'
import { CANVAS_GENERATABLE_KINDS, type CanvasNodeKind } from '../canvasTypes'
import {
  defaultOptionsForAssetKind,
  type ImageGenerationOptions,
} from '../../../../lib/dramaGenerationOptions'
import {
  DEFAULT_VIDEO_GENERATION_OPTIONS,
  readVideoGenerationOptions,
  type VideoGenerationOptions,
} from '../../../../lib/dramaVideoGenerationOptions'
import { optimizePromptWithSkills } from '../../../../api/agentSkills'
import { useAgentSkillSelection } from '../../../../hooks/useAgentSkillSelection'
import { DramaImageGenOptionsBar } from './DramaImageGenOptionsBar'
import { DramaSkillOptionsBar } from './DramaSkillOptionsBar'
import { DramaVideoGenOptionsBar } from './DramaVideoGenOptionsBar'
import { CanvasPromptEditor } from './CanvasPromptEditor'
import { useI18n } from '../../../../i18n/context'
import type { TFunction } from '../../../../i18n/context'

type CanvasNodeGeneratePanelProps = {
  nodeId: string
  kind: CanvasNodeKind
  generating?: boolean
  defaultPrompt?: string
  /** 节点展示名，用于过滤弱占位提示词 */
  label?: string
  /** 是否已有参考图（资产库/上传） */
  hasMedia?: boolean
  /** 视频节点已保存的 Seedance 参数 */
  videoOptions?: Record<string, unknown>
}

/** 按节点类型返回面板文案 */
function panelCopy(kind: CanvasNodeKind, hasMedia: boolean, t: TFunction) {
  const key = kind === 'video' || kind === 'character' || kind === 'scene' ? kind : 'image'
  const base = `dramaCanvas.generate.${key}`
  return {
    title: t(hasMedia ? `${base}.titleEdit` : `${base}.title`),
    placeholder: t(`${base}.placeholder`),
    hint: t(`${base}.hint`),
  }
}

const PLACEHOLDER_PROMPT = /^(character|scene|prop|material|none|image|audio|video)\s+\S+$/i

/** 清洗默认提示词：只去掉「video 新视频」这类占位，保留用户短描述与 @ 引用 */
function sanitizePrompt(raw: string, kind: CanvasNodeKind, label: string): string {
  const text = (raw || '').trim()
  if (!text) return ''
  if (PLACEHOLDER_PROMPT.test(text)) return ''
  if (label && (text === `${kind} ${label}` || text === label)) return ''
  return text
}

/** 渲染 AI 提示词编辑面板 */
export function CanvasNodeGeneratePanel({
  nodeId,
  kind,
  generating = false,
  defaultPrompt = '',
  label = '',
  hasMedia = false,
  videoOptions: savedVideoOptions,
}: CanvasNodeGeneratePanelProps) {
  const {
    generateNodeImage,
    generateNodeVideo,
    setErrorMessage,
    projectImageStyleId,
    updateNodePrompt,
    updateNodeVideoOptions,
    mentionableNodes,
  } = useCanvasStore()
  const { t } = useI18n()
  const [prompt, setPrompt] = useState(() => sanitizePrompt(defaultPrompt, kind, label))
  /*
   * busy 正在提交生成
   * rulesOpen Seedance 规则弹窗
   * optimizing Skill 改写进行中
   */
  const [busy, setBusy] = useState(false)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const { skills, selectedIds, toggleSkill, selectAll, selectNone, uploadSkill, uploading, uploadError } =
    useAgentSkillSelection()
  // imageOptions 生图风格/模型/画幅
  const [imageOptions, setImageOptions] = useState<ImageGenerationOptions>(() => ({
    ...defaultOptionsForAssetKind(kind),
    image_style_id: projectImageStyleId || undefined,
  }))
  // videoOpts Seedance 时长/比例/清晰度
  const [videoOpts, setVideoOpts] = useState<VideoGenerationOptions>(() => {
    const saved = readVideoGenerationOptions(savedVideoOptions)
    return {
      ...DEFAULT_VIDEO_GENERATION_OPTIONS,
      ...saved,
      image_style_id: saved.image_style_id || projectImageStyleId || undefined,
    }
  })
  const copy = panelCopy(kind, hasMedia, t)
  const allowMention = kind === 'video' || kind === 'image'
  const isVideo = kind === 'video'

  /* 可引用：排除当前节点自身 */
  const mentionItems = useMemo(
    () => mentionableNodes.filter((n) => n.nodeId !== nodeId),
    [mentionableNodes, nodeId],
  )

  const lastNodeIdRef = useRef(nodeId)

  /* 换节点时强制同步；同一节点不要用空默认值清掉用户正文 */
  useEffect(() => {
    const switched = lastNodeIdRef.current !== nodeId
    lastNodeIdRef.current = nodeId
    const next = sanitizePrompt(defaultPrompt, kind, label)
    if (switched) {
      setPrompt(next)
      return
    }
    setPrompt((prev) => next || prev)
  }, [defaultPrompt, nodeId, kind, label])

  /* 节点类型或项目风格变化时同步默认选项 */
  useEffect(() => {
    setImageOptions((prev) => ({
      ...defaultOptionsForAssetKind(kind),
      image_style_id: prev.image_style_id || projectImageStyleId || undefined,
      model_id: prev.model_id,
      resolution: prev.resolution,
    }))
  }, [kind, nodeId, projectImageStyleId])

  useEffect(() => {
    const saved = readVideoGenerationOptions(savedVideoOptions)
    setVideoOpts({
      ...DEFAULT_VIDEO_GENERATION_OPTIONS,
      ...saved,
      image_style_id: saved.image_style_id || projectImageStyleId || undefined,
    })
    // 仅切换节点时恢复已保存参数，避免编辑选项时被回写覆盖
  }, [nodeId, projectImageStyleId])

  const isBusy = busy || generating || optimizing
  const canSubmit = prompt.trim().length > 0 && !isBusy
  const canOptimize = prompt.trim().length > 0 && selectedIds.length > 0 && !isBusy

  if (!CANVAS_GENERATABLE_KINDS.has(kind)) return null

  const stopFlowEvent = (event: MouseEvent) => {
    event.stopPropagation()
  }

  const submit = async () => {
    if (!canSubmit) return
    setBusy(true)
    try {
      updateNodePrompt(nodeId, prompt)
      if (isVideo) {
        updateNodeVideoOptions(nodeId, videoOpts)
      }
      if (isVideo) {
        await generateNodeVideo(nodeId, prompt, videoOpts)
      } else {
        await generateNodeImage(nodeId, prompt, imageOptions)
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : t('dramaCanvas.generate.failed'))
    } finally {
      setBusy(false)
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit()
  }

  // 按勾选 Skill 改写当前提示词，保留 @asset 引用
  const optimizePrompt = async () => {
    if (!canOptimize) return
    setOptimizing(true)
    try {
      const result = await optimizePromptWithSkills({
        prompt,
        skill_ids: selectedIds,
        task: isVideo ? 'video_prompt' : 'image_prompt',
      })
      const next = (result.prompt || '').trim()
      if (next) {
        setPrompt(next)
        updateNodePrompt(nodeId, next)
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : t('dramaCanvas.generate.skillFailed'))
    } finally {
      setOptimizing(false)
    }
  }

  return (
    <form
      className={`fc-generate-panel nodrag nopan nowheel${hasMedia ? ' has-media' : ''}`}
      onMouseDown={stopFlowEvent}
      onPointerDown={stopFlowEvent}
      onClick={stopFlowEvent}
      onSubmit={handleSubmit}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          updateNodePrompt(nodeId, prompt)
        }
      }}
    >
      <div className="fc-generate-head">
        <Sparkles size={14} strokeWidth={1.8} />
        <span>{copy.title}</span>
        {hasMedia ? <em className="fc-generate-tag">{t('dramaCanvas.generate.regenTag')}</em> : null}
        {isVideo ? (
          <button
            type="button"
            className="fc-generate-help"
            title={t('dramaCanvas.generate.seedanceRules')}
            aria-label={t('dramaCanvas.generate.seedanceRules')}
            disabled={isBusy}
            onClick={() => setRulesOpen(true)}
          >
            <CircleHelp size={14} strokeWidth={1.8} />
          </button>
        ) : null}
      </div>
      <CanvasPromptEditor
        value={prompt}
        placeholder={copy.placeholder}
        disabled={isBusy}
        allowMention={allowMention}
        mentionItems={mentionItems}
        onChange={(next) => {
          setPrompt(next)
        }}
        onSubmit={() => void submit()}
      />
      {isVideo ? (
        <DramaVideoGenOptionsBar
          value={videoOpts}
          disabled={isBusy}
          onChange={(next) => {
            setVideoOpts(next)
            updateNodeVideoOptions(nodeId, next)
          }}
        />
      ) : (
        <DramaImageGenOptionsBar value={imageOptions} onChange={setImageOptions} disabled={isBusy} />
      )}
      <DramaSkillOptionsBar
        skills={skills}
        selectedIds={selectedIds}
        disabled={isBusy}
        onToggle={toggleSkill}
        onSelectAll={selectAll}
        onSelectNone={selectNone}
        onUpload={(file) => void uploadSkill(file)}
        uploading={uploading}
        uploadError={uploadError}
      />
      <div className="fc-generate-actions">
        <span className="fc-generate-hint">{copy.hint}</span>
        <div className="fc-generate-action-btns">
          <button
            type="button"
            className="fc-generate-optimize"
            disabled={!canOptimize}
            title={
              selectedIds.length
                ? t('dramaCanvas.generate.optimizeTitle')
                : t('dramaCanvas.generate.pickSkillFirst')
            }
            onClick={() => void optimizePrompt()}
          >
            {optimizing ? <Loader2 size={14} className="fc-spin" /> : <Wand2 size={14} strokeWidth={1.8} />}
            {t('dramaCanvas.generate.optimize')}
          </button>
          <button type="submit" className="fc-generate-submit" disabled={!canSubmit} aria-label={t('dramaCanvas.generate.submit')}>
            {isBusy && !optimizing ? (
              <Loader2 size={16} className="fc-spin" />
            ) : (
              <ArrowUp size={16} strokeWidth={2} />
            )}
          </button>
        </div>
      </div>
      {isVideo ? <SeedanceRulesModal open={rulesOpen} onClose={() => setRulesOpen(false)} /> : null}
    </form>
  )
}
