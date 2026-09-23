/** 漫剧生成队列：后端 message_key 翻译、落库错误码分类、资产提示词失败列表（vi 界面）。 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// 源码里的相对 import 不带扩展名（Vite 解析）；测试里补全为 .ts / .tsx
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[cm]?[jt]sx?$/.test(specifier) && context.parentURL) {
      for (const ext of ['.ts', '.tsx', '/index.ts']) {
        const url = new URL(specifier + ext, context.parentURL)
        if (existsSync(fileURLToPath(url))) return nextResolve(url.href, context)
      }
    }
    return nextResolve(specifier, context)
  },
})

const { dramaGenJobMessage, toDramaGenMessageKey, registeredErrorCode } = await import('../src/lib/dramaGenQueue.ts')
const { formatDramaGenJobError, pickRootDramaGenErrorEntry } = await import('../src/lib/dramaGenError.ts')
const { seedLlmErrorLines, storedJobError } = await import('../src/lib/dramaJobError.ts')
const { interpolate } = await import('../src/i18n/lookup.ts')
const { messages } = await import('../src/i18n/messages.ts')

// vi 界面的 t()
function t(path: string, vars?: Record<string, string | number>): string {
  let node: unknown = messages.vi
  for (const part of path.split('.')) node = (node as Record<string, unknown>)?.[part]
  return interpolate(String(node ?? path), vars)
}

test('backend message_key is translated with params, unknown keys fall back to message', () => {
  assert.equal(toDramaGenMessageKey('generatingRefsItem'), 'generatingRefsItem')
  assert.equal(toDramaGenMessageKey('somethingNew'), undefined)
  const text = dramaGenJobMessage(
    { messageKey: 'generatingRefsItem', messageParams: { done: 1, total: 3, name: 'Minh' } },
    t,
  )
  assert.equal(text, 'Đang tạo ảnh tham chiếu 1/3: Minh')
  assert.equal(dramaGenJobMessage({ message: 'raw' }, t), 'raw')
})

test('only registered error codes are kept', () => {
  assert.equal(registeredErrorCode('drama.gen_timeout'), 'drama.gen_timeout')
  assert.equal(registeredErrorCode('RuntimeError'), undefined)
  assert.equal(registeredErrorCode(null), undefined)
})

test('stored error codes pick the matching view, unregistered codes fall back to text', () => {
  const vi = messages.vi.dramaGenError
  assert.equal(formatDramaGenJobError({ error: 'x', errorCode: 'drama.gen_timeout' }).title, vi.timeout.title)
  assert.equal(formatDramaGenJobError({ error: 'x', errorCode: 'drama.prev_shot_failed' }).title, vi.prevFailed.title)
  assert.equal(formatDramaGenJobError({ error: 'x', errorCode: 'drama.fragment_changed' }).title, vi.fragmentChanged.title)
  assert.equal(formatDramaGenJobError({ error: 'x', errorCode: 'drama.gen_cancelled' }).title, vi.cancelled.title)
  // 异常类名不是已登记错误码：按原文分类（这里是审核拦截）
  const view = formatDramaGenJobError({ error: 'PrivacyInformation detected', errorCode: 'RuntimeError' })
  assert.equal(view.title, vi.realPerson.title)
})

test('root cause prefers coded root errors over retry wrappers', () => {
  const best = pickRootDramaGenErrorEntry([
    { text: '分镜内部自动重试超过上限（3 次）' },
    { text: 'Cảnh trước bị lỗi', code: 'drama.prev_shot_failed' },
  ])
  assert.equal(best?.code, 'drama.prev_shot_failed')
})

test('stored job errors are translated by code, legacy text is kept', () => {
  assert.equal(
    storedJobError({ summary_error: '模型服务商繁忙', summary_error_code: 'drama.upstream_rate_limit' }, 'summary_error'),
    messages.vi.errors['drama.upstream_rate_limit'],
  )
  assert.equal(storedJobError({ summary_error: 'old text' }, 'summary_error'), 'old text')
  assert.equal(storedJobError(null, 'summary_error'), '')
})

test('seed prompt failures: coded items are translated, legacy strings hide raw errors', () => {
  const lines = seedLlmErrorLines(
    [{ kind: 'character', name: 'Minh', code: 'drama.visual_prompt_failed', params: { kind: 'character', name: 'Minh' } }],
    [],
  )
  assert.equal(lines[0], `${messages.vi.dramaGenError.slot.character} “Minh”: Không viết được prompt AI cho “Minh”, vui lòng thử lại`)
  const legacy = seedLlmErrorLines([], ['scene/Bến sông: RuntimeError: 场景「Bến sông」AI 提示词生成失败'])
  assert.equal(legacy[0], `${messages.vi.dramaGenError.slot.scene} “Bến sông”`)
})

test('script structure labels are shown in the UI language without changing data', async () => {
  const { localizeScriptMetaLine, localizeScriptActionLine } = await import('../src/lib/dramaScriptLabels.ts')
  const vi = messages.vi.dramaProject.preview
  assert.equal(localizeScriptMetaLine('出场人物：Minh、Lan', vi), 'Nhân vật xuất hiện: Minh, Lan')
  assert.equal(localizeScriptMetaLine('夜 外 Bến sông', vi), 'Đêm · Ngoại cảnh · Bến sông')
  assert.equal(localizeScriptMetaLine('清晨 内外 Nhà Minh', vi), 'Sáng sớm · Nội/ngoại cảnh · Nhà Minh')
  assert.equal(localizeScriptMetaLine('Thời gian: sáng', vi), 'Thời gian: sáng')
  assert.equal(localizeScriptActionLine('【空镜：Sương trên sông】', vi), '【Cảnh trống: Sương trên sông】')
  assert.equal(localizeScriptActionLine('△ Minh bước vào', vi), '△ Minh bước vào')
})
