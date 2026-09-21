/** 浏览器端视频下载与打包 zip（无服务端打包接口） */

import JSZip from 'jszip'
import { getActiveLocale } from '../i18n/detect'
import { interpolate } from '../i18n/lookup'
import { messages } from '../i18n/messages'

// 按当前界面语言取下载相关文案
function dl() {
  return messages[getActiveLocale()].settingsPanels.download
}

// 安全文件名：标题去非法字符 + 项目 id；空标题用「未命名作品」
export function safeDownloadBasename(title: string, projectId: number): string {
  const untitled = dl().untitled
  const raw = (title || untitled).trim() || untitled
  const cleaned = raw
    .replace(/[<>:"/\\|?*\x00-\x1f]+/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 60)
  return `${cleaned || untitled}_p${projectId}`
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function fetchMediaBlob(url: string): Promise<Blob> {
  const res = await fetch(url, { mode: 'cors', credentials: 'omit' })
  if (!res.ok) {
    throw new Error(interpolate(dl().failed, { status: res.status }))
  }
  return res.blob()
}

export async function downloadSingleVideo(opts: {
  url: string
  title: string
  projectId: number
}): Promise<void> {
  const blob = await fetchMediaBlob(opts.url)
  triggerBlobDownload(blob, `${safeDownloadBasename(opts.title, opts.projectId)}.mp4`)
}

export type ZipVideoItem = {
  id: number
  title: string
  url: string
}

export async function zipVideosClient(
  items: ZipVideoItem[],
  onProgress?: (done: number, total: number) => void,
): Promise<{ blob: Blob; filename: string }> {
  if (!items.length) {
    throw new Error(dl().selectDone)
  }
  const zip = new JSZip()
  const used = new Set<string>()
  const total = items.length

  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const blob = await fetchMediaBlob(item.url)
    let base = `${safeDownloadBasename(item.title, item.id)}.mp4`
    if (used.has(base)) {
      base = `${safeDownloadBasename(item.title, item.id)}_${i + 1}.mp4`
    }
    used.add(base)
    zip.file(base, blob)
    onProgress?.(i + 1, total)
  }

  const out = await zip.generateAsync({ type: 'blob', compression: 'STORE' })
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  return { blob: out, filename: `printfilm_videos_${stamp}_${items.length}.zip` }
}
