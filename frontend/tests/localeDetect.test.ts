/** 语言识别：中文暂时关闭，zh 浏览器落到 en，默认 vi。 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_LOCALE, ENABLED_LOCALES, isLocaleEnabled, localeFromBrowser } from '../src/i18n/detect.ts'

test('zh is not selectable while disabled', () => {
  assert.deepEqual(ENABLED_LOCALES, ['vi', 'en'])
  assert.equal(isLocaleEnabled('zh'), false)
  assert.equal(isLocaleEnabled('vi'), true)
})

test('browser language maps to enabled locales only', () => {
  assert.equal(localeFromBrowser('vi-VN'), 'vi')
  assert.equal(localeFromBrowser('zh-CN'), 'en')
  assert.equal(localeFromBrowser('en-US'), 'en')
  assert.equal(DEFAULT_LOCALE, 'vi')
})
