/** Lồng tiếng TTS phim truyện: đọc chế độ tiếng của dự án và trạng thái params.dub của phân cảnh */

export type DramaVoiceMode = 'dub' | 'native'
export type FragmentDubStatus = 'running' | 'done' | 'failed' | 'skipped'
export type FragmentDubLine = { kind: string; name: string; text: string; speaker: string }
export type FragmentDub = {
  status: FragmentDubStatus
  url?: string | null
  lines: FragmentDubLine[]
  errorCode?: string | null
  errorParams?: Record<string, unknown> | null
  /** 'stale': video đổi trong lúc lồng tiếng nên kết quả bị bỏ */
  reason?: string | null
}

const STATUSES: FragmentDubStatus[] = ['running', 'done', 'failed', 'skipped']

/** Chế độ tiếng hiệu lực: params.voiceMode của dự án; chưa đặt thì vi/en → dub, zh → native */
export function readProjectVoiceMode(
  params: Record<string, unknown> | null | undefined,
  contentLang: string | null | undefined,
): DramaVoiceMode {
  const raw = params?.voiceMode
  if (raw === 'dub' || raw === 'native') return raw
  return contentLang === 'vi' || contentLang === 'en' ? 'dub' : 'native'
}

/** Video phân cảnh có được tạo ở chế độ lồng tiếng không (mới cho phép "Lồng tiếng lại") */
export function fragmentUsesDub(params: Record<string, unknown> | null | undefined): boolean {
  return params?.voice_mode === 'dub'
}

/** Đọc params.dub; sai kiểu hoặc trạng thái lạ trả null */
export function readFragmentDub(params: Record<string, unknown> | null | undefined): FragmentDub | null {
  const raw = params?.dub
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  const status = obj.status as FragmentDubStatus
  if (!STATUSES.includes(status)) return null
  const lines = Array.isArray(obj.lines)
    ? obj.lines
        .filter((l): l is Record<string, unknown> => Boolean(l) && typeof l === 'object')
        .map((l) => ({
          kind: String(l.kind ?? ''),
          name: String(l.name ?? ''),
          text: String(l.text ?? ''),
          speaker: String(l.speaker ?? ''),
        }))
    : []
  return {
    status,
    url: typeof obj.url === 'string' ? obj.url : null,
    lines,
    errorCode: typeof obj.error_code === 'string' ? obj.error_code : null,
    reason: typeof obj.reason === 'string' ? obj.reason : null,
    errorParams:
      obj.error_params && typeof obj.error_params === 'object'
        ? (obj.error_params as Record<string, unknown>)
        : null,
  }
}

/** Phân cảnh tối thiểu để trộn kết quả lồng tiếng từ server */
type DubMergeable = {
  id: number
  video: string
  cover: string
  params?: Record<string, unknown> | null
}

/** Khoá params do backend ghi khi lồng tiếng; phần còn lại của phân cảnh giữ theo bản đang sửa trên máy */
const SERVER_DUB_PARAM_KEYS = ['dub', 'voice_mode'] as const

/**
 * Trộn kết quả lồng tiếng từ server vào danh sách phân cảnh đang sửa (theo id):
 * chỉ lấy video, cover, params.dub, params.voice_mode; nội dung, chèn/xoá chưa lưu được giữ nguyên.
 * Phân cảnh không đổi giữ nguyên object để tránh render lại vô ích.
 */
export function mergeServerDubFields<T extends DubMergeable>(local: T[], server: DubMergeable[]): T[] {
  const byId = new Map(server.filter((f) => f.id > 0).map((f) => [f.id, f]))
  return local.map((f) => {
    const remote = f.id > 0 ? byId.get(f.id) : undefined
    if (!remote) return f
    const localParams = f.params && typeof f.params === 'object' ? f.params : {}
    const remoteParams = remote.params && typeof remote.params === 'object' ? remote.params : {}
    const params: Record<string, unknown> = { ...localParams }
    let changed = f.video !== remote.video || f.cover !== remote.cover
    for (const key of SERVER_DUB_PARAM_KEYS) {
      if (key in remoteParams) params[key] = remoteParams[key]
      else delete params[key]
      if (JSON.stringify(localParams[key]) !== JSON.stringify(params[key])) changed = true
    }
    if (!changed) return f
    return { ...f, video: remote.video, cover: remote.cover, params }
  })
}
