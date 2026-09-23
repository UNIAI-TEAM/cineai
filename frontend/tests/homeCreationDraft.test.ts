import assert from 'node:assert/strict'
import test from 'node:test'
import { readHomeCreationDraft } from '../src/lib/homeCreationDraft.ts'

test('restores the prompt and aspect ratio only for the selected creation tool', () => {
  const raw = JSON.stringify({ toolId: 't2v', prompt: '  Một thành phố trong mưa  ', ratio: '16:9' })
  assert.deepEqual(readHomeCreationDraft(raw, 't2v'), { prompt: 'Một thành phố trong mưa', ratio: '16:9' })
  assert.equal(readHomeCreationDraft(raw, 't2i'), null)
})

test('ignores missing, corrupt, empty and unsupported creation drafts', () => {
  for (const raw of [null, '{', 'null', '[]', JSON.stringify({ toolId: 't2v', prompt: ' ' }), JSON.stringify({ toolId: 't2v', prompt: 4 })]) {
    assert.equal(readHomeCreationDraft(raw, 't2v'), null)
  }
})

test('falls back to a supported aspect ratio and bounds prompt length', () => {
  assert.deepEqual(readHomeCreationDraft(JSON.stringify({ toolId: 't2i', prompt: 'x'.repeat(5000), ratio: 'invalid' }), 't2i'), { prompt: 'x'.repeat(4000), ratio: '16:9' })
})
