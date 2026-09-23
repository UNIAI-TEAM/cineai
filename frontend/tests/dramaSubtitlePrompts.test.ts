/** 字幕开关改写分镜 cue：有项目内容语言时用它，不按台词文字猜 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  applySubtitleModeToFragments,
  applySubtitlePromptsToContent,
  stripSubtitlePromptsFromContent,
} from '../src/lib/dramaSubtitlePrompts.ts'

const VI_CUE = '【字幕：底部居中·越南语·逐句轮换·与口播同步】'
const EN_CUE = '【字幕：底部居中·英语·逐句轮换·与口播同步】'

test('subtitle toggle uses the project content language when given', () => {
  // 越南语项目里不带越南语字母的台词：按文字会被猜成 en
  const fragments = [{ id: 1, content: '【对白·慢速清晰】Lan：OK, go!' }]
  const withLang = applySubtitleModeToFragments(fragments, 'model', 'vi')
  assert.ok(withLang[0].content.includes(VI_CUE))
  assert.ok(!withLang[0].content.includes(EN_CUE))
  // 未知项目语言：沿用按台词判断
  const guessed = applySubtitleModeToFragments(fragments, 'model', null)
  assert.ok(guessed[0].content.includes(EN_CUE))
})

test('existing cue in another language is replaced by the project language cue', () => {
  const content = `${EN_CUE}\nLan：OK, go!`
  const next = applySubtitlePromptsToContent(content, 'vi')
  assert.ok(next.includes(VI_CUE) && !next.includes(EN_CUE))
  assert.ok(!stripSubtitlePromptsFromContent(next).includes('字幕：'))
})
