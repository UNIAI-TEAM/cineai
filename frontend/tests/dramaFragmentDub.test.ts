/** Đọc chế độ tiếng dự án và trạng thái lồng tiếng phân cảnh */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fragmentUsesDub, mergeServerDubFields, readFragmentDub, readProjectVoiceMode } from '../src/lib/dramaFragmentDub.ts'

test('readProjectVoiceMode: explicit value wins, otherwise vi/en → dub, zh → native', () => {
  assert.equal(readProjectVoiceMode({ voiceMode: 'native' }, 'vi'), 'native')
  assert.equal(readProjectVoiceMode({ voiceMode: 'dub' }, 'zh'), 'dub')
  assert.equal(readProjectVoiceMode({}, 'vi'), 'dub')
  assert.equal(readProjectVoiceMode(null, 'en'), 'dub')
  assert.equal(readProjectVoiceMode({ voiceMode: 'x' }, 'zh'), 'native')
})

test('readFragmentDub parses status, lines and error code', () => {
  assert.equal(readFragmentDub(null), null)
  assert.equal(readFragmentDub({ dub: 'bad' }), null)
  const dub = readFragmentDub({
    dub: { status: 'failed', error_code: 'drama.dub_failed', lines: [{ kind: 'dialogue', name: 'Lan', text: 'Xin chào', speaker: 'vi_x' }] },
  })
  assert.equal(dub?.status, 'failed')
  assert.equal(dub?.errorCode, 'drama.dub_failed')
  assert.equal(dub?.lines[0].name, 'Lan')
})

test('fragmentUsesDub only for videos generated in dub mode', () => {
  assert.equal(fragmentUsesDub({ voice_mode: 'dub' }), true)
  assert.equal(fragmentUsesDub({ voice_mode: 'native' }), false)
  assert.equal(fragmentUsesDub(undefined), false)
})

test('readFragmentDub exposes skip reason', () => {
  assert.equal(readFragmentDub({ dub: { status: 'skipped', reason: 'stale' } })?.reason, 'stale')
  assert.equal(readFragmentDub({ dub: { status: 'done' } })?.reason, null)
})

test('mergeServerDubFields keeps unsaved local edits and only takes dub fields from server', () => {
  const local = [
    { id: 1, video: '/raw.mp4', cover: 'c', content: 'đang sửa', params: { voice_mode: 'dub', dub: { status: 'running' }, user_edited: true } },
    { id: 0, video: '', cover: '', content: 'phân cảnh mới chưa lưu', params: {} },
    { id: 2, video: '/b.mp4', cover: 'b', content: 'không đổi', params: { voice_mode: 'native' } },
  ]
  const server = [
    { id: 1, video: '/dub.mp4', cover: 'c2', content: 'nội dung cũ trên server', params: { voice_mode: 'dub', dub: { status: 'done', url: '/dub.mp4' } } },
    { id: 2, video: '/b.mp4', cover: 'b', content: 'x', params: { voice_mode: 'native' } },
    { id: 3, video: '/c.mp4', cover: '', content: 'đã bị xoá ở máy', params: {} },
  ]
  const merged = mergeServerDubFields(local, server)
  assert.equal(merged.length, 3)
  assert.equal(merged[0].content, 'đang sửa')
  assert.equal(merged[0].video, '/dub.mp4')
  assert.equal(merged[0].cover, 'c2')
  assert.deepEqual(merged[0].params, { voice_mode: 'dub', dub: { status: 'done', url: '/dub.mp4' }, user_edited: true })
  assert.equal(merged[1], local[1])
  assert.equal(merged[2], local[2])
})

test('mergeServerDubFields drops dub when server no longer has it', () => {
  const merged = mergeServerDubFields(
    [{ id: 5, video: '/d.mp4', cover: '', params: { dub: { status: 'running' }, voice_mode: 'dub' } }],
    [{ id: 5, video: '/new.mp4', cover: '', params: { voice_mode: 'native' } }],
  )
  assert.deepEqual(merged[0].params, { voice_mode: 'native' })
})
