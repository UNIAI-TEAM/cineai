/** 独立创作工具 API：/api/tools/* */

import { apiErrorText, parseApiError, throwApiError } from '../lib/apiError'
import { uiLocaleHeaders } from '../lib/uiLocaleHeader'

function defaultApiBase() {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const { protocol, hostname } = window.location
    return `${protocol}//${hostname}:8000`
  }
  return 'http://127.0.0.1:8000'
}

const _viteApiBase = import.meta.env.VITE_API_BASE
const API_BASE =
  _viteApiBase === undefined || _viteApiBase === null ? defaultApiBase() : String(_viteApiBase)

export type ToolRunResult = {
  kind: string
  urls: string[]
  task_id?: string | null
  status: string
  preview_url?: string | null
  message?: string | null
}

export type ToolTaskResult = {
  status: string
  kind: string
  urls: string[]
  error?: string | null
}

export type ToolRunRecord = {
  id: number
  tool_id: string
  kind: string
  status: string
  prompt: string
  preview_url?: string | null
  urls: string[]
  task_id?: string | null
  params?: Record<string, string> | null
  error?: string | null
  /** 落库错误码与参数（后端补齐前可能缺省），展示用 localizeStoredError */
  error_code?: string | null
  error_params?: Record<string, unknown> | null
  created_at: string
}

export type ToolRunList = {
  items: ToolRunRecord[]
  total: number
  page: number
  page_size: number
}

// 将 /static 相对路径补全为可访问地址
export function resolveToolMediaUrl(url?: string | null): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url
  }
  if (url.startsWith('/')) return `${API_BASE}${url}`
  return url
}

export type ToolRunPayload = {
  toolId: string
  prompt?: string
  negative?: string
  ratio?: string
  strength?: string
  mode?: string
  pack?: string
  duration?: string
  motion?: string
  files?: File[]
}

// 提交工具生成（multipart）
export async function runStudioTool(payload: ToolRunPayload): Promise<ToolRunResult> {
  const token = localStorage.getItem('token')
  const body = new FormData()
  body.append('tool_id', payload.toolId)
  body.append('prompt', payload.prompt || '')
  body.append('negative', payload.negative || '')
  body.append('ratio', payload.ratio || '')
  body.append('strength', payload.strength || '')
  body.append('mode', payload.mode || '')
  body.append('pack', payload.pack || '')
  body.append('duration', payload.duration || '')
  body.append('motion', payload.motion || '')
  for (const file of payload.files || []) {
    body.append('files', file)
  }
  const res = await fetch(`${API_BASE}/api/tools/run`, {
    method: 'POST',
    headers: { ...uiLocaleHeaders(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body,
  })
  if (res.status === 401) throw parseApiError(401, null, apiErrorText('loginRequired'))
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throwApiError(res.status, err, apiErrorText('generateFailed'))
  }
  return res.json()
}

// 查询视频任务状态
export async function pollStudioToolTask(taskId: string): Promise<ToolTaskResult> {
  const token = localStorage.getItem('token')
  const res = await fetch(`${API_BASE}/api/tools/tasks/${encodeURIComponent(taskId)}`, {
    headers: { ...uiLocaleHeaders(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (res.status === 401) throw parseApiError(401, null, apiErrorText('loginRequired'))
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throwApiError(res.status, err, apiErrorText('queryFailed'))
  }
  return res.json()
}

// 个人中心：分页拉取工具创作记录
export async function listToolRuns(page = 1, pageSize = 8): Promise<ToolRunList> {
  const token = localStorage.getItem('token')
  const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  const res = await fetch(`${API_BASE}/api/tools/runs?${qs}`, {
    headers: { ...uiLocaleHeaders(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (res.status === 401) throw parseApiError(401, null, apiErrorText('loginRequired'))
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throwApiError(res.status, err, apiErrorText('loadFailed'))
  }
  return res.json()
}

// 个人中心：单条创作详情（含 OSS 结果地址）
export async function getToolRun(runId: number): Promise<ToolRunRecord> {
  const token = localStorage.getItem('token')
  const res = await fetch(`${API_BASE}/api/tools/runs/${runId}`, {
    headers: { ...uiLocaleHeaders(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (res.status === 401) throw parseApiError(401, null, apiErrorText('loginRequired'))
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throwApiError(res.status, err, apiErrorText('loadFailed'))
  }
  return res.json()
}
