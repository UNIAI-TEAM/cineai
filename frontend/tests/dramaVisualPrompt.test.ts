/** 生图提示词语言：中文项目用中文标签，越南语 / 英文项目用英文（与后端 seed_asset_params 一致）。 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readVisualPrompt } from '../src/lib/dramaVisualPrompt.ts'
import type { DramaAsset } from '../src/api/drama.ts'

function asset(partial: Partial<DramaAsset>): DramaAsset {
  return { id: 1, project_id: 1, type: 'character', name: '', params: {}, ...partial } as DramaAsset
}

test('scene template follows project language', () => {
  assert.match(readVisualPrompt(asset({ type: 'scene', name: '河岸' })), /^场景：河岸/)
  assert.match(readVisualPrompt(asset({ type: 'scene', name: 'Bến sông' })), /^Scene: Bến sông/)
  assert.match(readVisualPrompt(asset({ type: 'scene', name: 'Bến sông' }), 'zh'), /^场景：/)
})

test('character labels are English for vi / en projects and drop Chinese stub values', () => {
  const params = {
    visualImage: 'Young fisherman with tanned skin and a woven hat, standing on a wooden boat at dawn, calm eyes, holding a net',
    title: 'Ngư dân',
    roleType: '配角',
  }
  const vi = readVisualPrompt(asset({ name: 'Minh', params }), 'vi')
  assert.ok(vi.includes('Identity: Ngư dân'))
  assert.ok(!vi.includes('配角'))
  const zh = readVisualPrompt(
    asset({
      name: '禹',
      params: { visualImage: '青年男子，身形清瘦，'.repeat(11), title: '治水首领', roleType: '主角' },
    }),
    'zh',
  )
  assert.ok(zh.includes('身份：治水首领'))
})

test('short field-composed or hand-edited character prompt is returned as stored (no duplicated labels)', () => {
  const stored = 'Gender: female. Age: about 20. Hair: short black hair. Outfit: faded brown ao ba ba, conical hat. Role: lead'
  const composed = asset({ name: 'Lan', params: { visualPrompt: stored, visualImage: stored, roleType: 'lead', appearance: { gender: 'female', age: 'about 20', hair: 'short black hair', outfit: 'faded brown ao ba ba, conical hat' }, promptManual: false } })
  assert.equal(readVisualPrompt(composed), stored)
  const manual = asset({ name: 'Lan', params: { visualPrompt: 'A young girl standing on a wooden boat at dawn, long black braid, faded ao ba ba. Role: lead', roleType: 'lead', promptManual: true } })
  assert.equal(readVisualPrompt(manual), 'A young girl standing on a wooden boat at dawn, long black braid, faded ao ba ba. Role: lead')
})
