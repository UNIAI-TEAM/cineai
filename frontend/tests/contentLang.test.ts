/** 项目内容语言：归一、默认值（跟随界面语言）与可选项（zh 仅在开放中文或项目本就是中文时出现） */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  contentLangOptions,
  defaultContentLang,
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
