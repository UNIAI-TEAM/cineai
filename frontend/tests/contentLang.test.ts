/** 项目内容语言：归一、默认值（跟随界面语言）与可选项（zh 仅在开放中文或项目本就是中文时出现） */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  contentLangOptions,
  cutToLimit,
  defaultContentLang,
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
