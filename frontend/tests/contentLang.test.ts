/** 项目内容语言：归一、默认值（跟随界面语言）与可选项（zh 仅在开放中文或项目本就是中文时出现） */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  contentLangOptions,
  cutToLimit,
  defaultContentLang,
  acceptLimitedInput,
  fitKepuDraft,
  kepuDraftOverflow,
  guessTextLang,
  kepuTextLimits,
  normalizeContentLang,
} from '../src/lib/contentLang.ts'

test('normalizeContentLang accepts region tags and rejects unknown', () => {
  assert.equal(normalizeContentLang('vi-VN'), 'vi')
  assert.equal(normalizeContentLang('en_US'), 'en')
  assert.equal(normalizeContentLang(' ZH '), 'zh')
  assert.equal(normalizeContentLang('fr'), null)
  assert.equal(normalizeContentLang(''), null)
  assert.equal(normalizeContentLang(undefined), null)
  assert.equal(normalizeContentLang(42), null)
})

test('options hide zh while the Chinese UI is disabled', () => {
  assert.deepEqual(contentLangOptions(null), ['vi', 'en'])
  assert.deepEqual(contentLangOptions('vi'), ['vi', 'en'])
  assert.deepEqual(contentLangOptions('en-US'), ['vi', 'en'])
})

test('options keep zh for projects that are already Chinese', () => {
  assert.deepEqual(contentLangOptions('zh'), ['vi', 'en', 'zh'])
  assert.deepEqual(contentLangOptions('zh-CN'), ['vi', 'en', 'zh'])
})

test('options include zh when the Chinese UI is enabled again', () => {
  assert.deepEqual(contentLangOptions(null, ['vi', 'en', 'zh']), ['vi', 'en', 'zh'])
})

test('default follows the UI locale, falling back to vi', () => {
  assert.equal(defaultContentLang('vi'), 'vi')
  assert.equal(defaultContentLang('en'), 'en')
  assert.equal(defaultContentLang('zh'), 'vi')
  assert.equal(defaultContentLang('zh', ['vi', 'en', 'zh']), 'zh')
})

test('guessTextLang only treats Vietnamese-specific letters as vi', () => {
  assert.equal(guessTextLang('Pokémon evolution'), 'en')
  assert.equal(guessTextLang('Why café culture spread'), 'en')
  assert.equal(guessTextLang('Vì sao bầu trời có màu xanh'), 'vi')
  assert.equal(guessTextLang('Tôi là ai'), 'vi')
  assert.equal(guessTextLang('Xin chào'), 'vi')
  assert.equal(guessTextLang('Tai sao bau troi mau xanh'), 'en')
  assert.equal(guessTextLang('大禹治水'), 'zh')
  assert.equal(guessTextLang('  '), null)
})

test('kepu limits follow content language and cut at word boundaries', () => {
  assert.deepEqual(kepuTextLimits('zh'), { theme: 100, title: 24 })
  assert.deepEqual(kepuTextLimits('vi'), { theme: 400, title: 80 })
  assert.deepEqual(kepuTextLimits('en'), { theme: 400, title: 80 })
  const vi = 'Vì sao bầu trời có màu xanh vào ban ngày'
  assert.equal(cutToLimit(vi, 17), 'Vì sao bầu trời')
  assert.equal(cutToLimit(vi, 15), 'Vì sao bầu trời') // 下一个字符是空格：整词保留
  assert.equal(cutToLimit('Why café culture spread, fast', 25), 'Why café culture spread')
  assert.equal(cutToLimit('short', 80), 'short')
  assert.equal(cutToLimit('Supercalifragilistic', 5), 'Super') // 无空格只能硬截
  assert.equal(cutToLimit('光合作用是什么原理呢', 4), '光合作用')
})

test('guessTextLang matches the shared backend vectors', () => {
  const url = new URL('../../backend/tests/fixtures/content_lang_vectors.json', import.meta.url)
  const { cases } = JSON.parse(readFileSync(url, 'utf-8')) as { cases: [string, string | null][] }
  assert.ok(cases.length > 10)
  for (const [text, expected] of cases) assert.equal(guessTextLang(text), expected, text)
  assert.equal(guessTextLang('Người đi đường'.normalize('NFD')), 'vi')
})

test('cutToLimit never splits a Latin word, even inside Chinese text', () => {
  assert.equal(cutToLimit('光合作用 Photosynthesis explained', 10), '光合作用')
  assert.equal(cutToLimit('iPhone 15 Pro 评测', 8), 'iPhone')
  assert.equal(cutToLimit('中文标题测试一下', 4), '中文标题')
  assert.equal(cutToLimit('Why café culture spread', 12), 'Why café')
  // 「词」= 不含空白的片段（同后端 cut_words）：撇号 / 小数点 / 连字符都不断开
  assert.equal(cutToLimit("I don't know", 5), 'I')
  assert.equal(cutToLimit('Version 3.5 released', 10), 'Version')
  assert.equal(cutToLimit('A state-of-the-art lab', 10), 'A')
  assert.equal(cutToLimit('光合作用Photosynthesis', 6), '光合作用')
})

test('fit-to-limit button trims theme and title to the current language limits', () => {
  const theme = 'Vì sao bầu trời có màu xanh '.repeat(12).trim() // ~335 ký tự
  const title = 'Bầu trời xanh và ánh sáng mặt trời qua khí quyển'
  const zh = fitKepuDraft({ sourceText: theme, title }, 'zh', 'theme')
  assert.ok(zh.sourceText.length <= 100 && theme.startsWith(zh.sourceText))
  assert.equal(theme.charAt(zh.sourceText.length), ' ') // 截在词边界
  assert.ok(zh.title.length <= 24 && title.startsWith(zh.title))
  assert.deepEqual(fitKepuDraft({ sourceText: theme, title }, 'vi', 'theme'), { sourceText: theme, title })
  // 文案模式正文不受主题上限影响
  assert.equal(fitKepuDraft({ sourceText: theme, title }, 'zh', 'script').sourceText, theme)
})

test('switching language never trims content: overflow is reported, input only refuses to grow', () => {
  const theme = 'Vì sao bầu trời có màu xanh '.repeat(12).trim()
  const title = 'Bầu trời xanh'
  assert.deepEqual(kepuDraftOverflow({ sourceText: theme, title }, 'zh', 'theme'), {
    themeOver: true,
    titleOver: false,
    any: true,
  })
  assert.equal(kepuDraftOverflow({ sourceText: theme, title }, 'vi', 'theme').any, false)
  assert.equal(kepuDraftOverflow({ sourceText: theme, title }, 'zh', 'script').themeOver, false)
  // 已超限：删减照收，变长不收，绝不截掉已有内容
  assert.equal(acceptLimitedInput(theme, theme.slice(0, -1), 100), theme.slice(0, -1))
  assert.equal(acceptLimitedInput(theme, `${theme}x`, 100), theme)
  // 未超限时仍按上限硬截（同 maxLength）
  assert.equal(acceptLimitedInput('abc', 'abcdef', 4), 'abcd')
  assert.equal(acceptLimitedInput('abc', 'abcd', 4), 'abcd')
})
