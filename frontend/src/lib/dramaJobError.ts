/** 漫剧后台任务落库错误（params.<field> + <field>_code + <field>_params）转当前界面语言的文案 */
import { getActiveLocale } from '../i18n/detect'
import { messages } from '../i18n/messages'
import { localizeStoredError } from './apiError'

/**
 * 读取 params 里的任务错误：带已登记错误码时按界面语言翻译，否则原文（老数据）；无错误返回空串。
 * 参数 params：项目 / 剧本 / 分集 params；field：如 summary_error、fragment_plan_error。
 */
export function storedJobError(params: Record<string, unknown> | null | undefined, field: string): string {
  const p = params || {}
  const raw = p[field]
  const code = p[`${field}_code`]
  return localizeStoredError(
    raw == null ? '' : String(raw),
    typeof code === 'string' ? code : undefined,
    p[`${field}_params`],
  )
}

/** 资产提示词 AI 刷新失败项（后端 llm_error_items / params.assets_seed_llm_error_items） */
export type SeedLlmErrorItem = {
  kind?: string
  name?: string
  code?: string
  params?: Record<string, unknown>
}

// 失败项的资产类型显示名（角色 / 场景 / 道具），其余类型不加前缀
function seedKindLabel(kind: string | undefined): string {
  const slot = messages[getActiveLocale()].dramaGenError.slot
  if (kind === 'character') return slot.character
  if (kind === 'scene') return slot.scene
  if (kind === 'prop') return slot.prop
  return ''
}

/**
 * 资产提示词刷新失败列表转展示行：新数据按错误码翻译原因；
 * 老数据（「kind/name: 原始报错」字符串）只显示类型与名称，不显示原始报错。
 * 参数 items：结构化失败项；legacy：旧版字符串列表（items 为空时使用）。
 */
export function seedLlmErrorLines(items: unknown, legacy: unknown): string[] {
  if (Array.isArray(items) && items.length > 0) {
    return items
      .filter((it): it is SeedLlmErrorItem => Boolean(it && typeof it === 'object'))
      .map((it) => {
        const label = seedKindLabel(it.kind)
        const name = String(it.name || '')
        const head = label ? `${label} “${name}”` : `“${name}”`
        const reason = localizeStoredError('', it.code, it.params)
        return reason ? `${head}: ${reason}` : head
      })
  }
  if (!Array.isArray(legacy)) return []
  return legacy.map((raw) => {
    const text = String(raw || '')
    const sep = text.indexOf(': ')
    const head = sep >= 0 ? text.slice(0, sep) : text
    const slash = head.indexOf('/')
    if (slash < 0) return head
    const label = seedKindLabel(head.slice(0, slash))
    const name = head.slice(slash + 1)
    return label ? `${label} “${name}”` : `“${name}”`
  })
}
