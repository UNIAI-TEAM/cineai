import type { DramaProject, DramaProjectListItem } from '../api/drama'
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { interpolate } from '../i18n/lookup'

export type DramaWorkflow = 'script' | 'canvas'

const CANVAS_SOURCE_MARKER = '自由画布创作项目'
const CANVAS_TITLE_MARKER = '自由画布'
/**
 * 画布项目默认标题：固定写中文主值入库（后端靠它识别「未改名」与画布工作流），
 * 展示时由 displayDramaTitle 按界面语言替换
 */
export const CANVAS_DEFAULT_TITLE = '自由画布项目'

type WorkflowSource = {
  workflow?: string | null
  title?: string | null
  params?: Record<string, unknown> | null
  script?: { source?: string | null } | null
}

/** 解析漫剧工作流：canvas=自由画布；script=大纲分集 */
export function resolveDramaWorkflow(item: WorkflowSource | null | undefined): DramaWorkflow {
  const raw = String(item?.workflow || item?.params?.workflow || '')
    .trim()
    .toLowerCase()
  if (raw === 'canvas' || raw === 'script') return raw

  const title = String(item?.title || '')
  if (title.includes(CANVAS_TITLE_MARKER)) return 'canvas'

  const source = String(item?.script?.source || '')
  if (source.includes(CANVAS_SOURCE_MARKER)) return 'canvas'

  return 'script'
}

/** 是否自由画布项目 */
export function isCanvasWorkflow(
  item: DramaProject | DramaProjectListItem | WorkflowSource | null | undefined,
): boolean {
  return resolveDramaWorkflow(item) === 'canvas'
}

/** 项目入口路径：画布仅进 canvas，普通进工作台 */
export function dramaProjectEntryPath(
  item: DramaProject | DramaProjectListItem | WorkflowSource,
): string {
  const id = Number((item as { id?: number }).id)
  if (!Number.isFinite(id) || id <= 0) return '/drama'
  if (isCanvasWorkflow(item)) return `/drama/projects/${id}/canvas`
  return `/drama/projects/${id}`
}

/** 列表卡片 meta 文案（按当前界面语言） */
export function formatDramaCardMeta(item: DramaProjectListItem): string {
  const l = messages[getActiveLocale()].dramaList
  const assets = item.asset_count || 0
  if (isCanvasWorkflow(item)) return interpolate(l.metaCanvas, { assets })
  if (item.has_script) {
    return interpolate(l.metaScript, { episodes: item.episode_count || 0, assets })
  }
  return interpolate(l.metaDraft, { assets })
}

/** 后端剧本流默认标题（schemas_drama / models_drama；agents 据此自动改名，落库保持中文） */
export const DRAMA_DEFAULT_TITLE = '未命名漫剧'

/** 项目展示标题：未改名的默认标题（画布 / 剧本流）按界面语言显示，其余原样返回 */
export function displayDramaTitle(title: string | null | undefined): string {
  const raw = title || ''
  const l = messages[getActiveLocale()].dramaList
  if (raw === CANVAS_DEFAULT_TITLE) return l.canvasDefaultTitle
  if (raw === DRAMA_DEFAULT_TITLE) return l.untitledDrama
  return raw
}

/** 分集展示名：后端默认名「第N集」/「第 N 集」按界面语言显示为「Tập N」等，其余原样返回 */
export function displayEpisodeName(name: string | null | undefined): string {
  const raw = (name || '').trim()
  const match = raw.match(/^第\s*(\d+)\s*集$/)
  if (!match) return name || ''
  return interpolate(messages[getActiveLocale()].dramaProject.episodeNo, { n: Number(match[1]) })
}
