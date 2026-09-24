/** Ngoại hình nhân vật theo trường: đọc params, so sánh, dựng body lưu (chế độ tự ghép / chỉnh tay) */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  APPEARANCE_KEYS,
  appearanceEqual,
  appearanceIsEmpty,
  buildAppearanceSave,
  emptyAppearance,
  readAppearance,
  readPromptManual,
} from '../src/lib/dramaAppearance.ts'

test('readAppearance fills all 8 keys and ignores junk', () => {
  const a = readAppearance({ params: { appearance: { hair: ' ponytail ', age: 25, junk: 'x' } } })
  assert.deepEqual(Object.keys(a), [...APPEARANCE_KEYS])
  assert.equal(a.hair, 'ponytail')
  assert.equal(a.age, '25')
  assert.ok(appearanceIsEmpty(readAppearance({ params: { appearance: 'text' } })))
  assert.ok(appearanceIsEmpty(readAppearance({})))
})

test('appearanceEqual compares trimmed values', () => {
  const a = { ...emptyAppearance(), hair: 'x' }
  assert.ok(appearanceEqual(a, { ...emptyAppearance(), hair: ' x ' }))
  assert.ok(!appearanceEqual(a, emptyAppearance()))
})

test('readPromptManual only true for literal true', () => {
  assert.equal(readPromptManual({ params: { promptManual: true } }), true)
  assert.equal(readPromptManual({ params: { promptManual: 'yes' } }), false)
})

test('buildAppearanceSave: field edit in auto mode asks backend to recompose', () => {
  const appearance = { ...emptyAppearance(), hair: 'long' }
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: true, promptText: 'p', promptDirty: false, wasManual: false }),
    { appearance, promptManual: false },
  )
})

test('buildAppearanceSave: typed prompt switches to manual and keeps text', () => {
  const appearance = emptyAppearance()
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: false, promptText: ' mine ', promptDirty: true, wasManual: false }),
    { promptManual: true, visualPrompt: 'mine', visualImage: 'mine' },
  )
})

test('buildAppearanceSave: field edit while manual keeps manual prompt', () => {
  const appearance = { ...emptyAppearance(), hair: 'long' }
  assert.deepEqual(
    buildAppearanceSave({ appearance, appearanceDirty: true, promptText: 'mine', promptDirty: false, wasManual: true }),
    { appearance },
  )
})

test('buildAppearanceSave: nothing changed → null', () => {
  assert.equal(
    buildAppearanceSave({ appearance: emptyAppearance(), appearanceDirty: false, promptText: 'x', promptDirty: false, wasManual: false }),
    null,
  )
})
