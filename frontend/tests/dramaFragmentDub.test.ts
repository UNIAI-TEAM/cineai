/** Đọc chế độ tiếng dự án và trạng thái lồng tiếng phân cảnh */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fragmentUsesDub, readFragmentDub, readProjectVoiceMode } from '../src/lib/dramaFragmentDub.ts'

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
