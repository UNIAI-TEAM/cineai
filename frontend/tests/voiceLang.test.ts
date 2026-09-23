/** 音色按内容语言过滤 / 默认音色 / 不支持时自动替换（与后端 voice_lang.py 同规则，共用 fixture 向量） */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  defaultVoiceForLang,
  fnv1a32,
  speakerForPrompt,
  voiceKeyForLang,
  voiceSupportsLang,
  voicesForLang,
} from '../src/lib/voiceLang.ts'

const VOICES = [
  { id: 'zh_female_cancan_uranus_bigtts', speaker: 'zh_female_cancan_uranus_bigtts', gender: 'female', languages: ['zh'] },
  { id: 'zh_male_m191_uranus_bigtts', speaker: 'zh_male_m191_uranus_bigtts', gender: 'male', languages: ['zh'] },
  { id: 'vi_female_ruan_uranus_bigtts', speaker: 'vi_female_ruan_uranus_bigtts', gender: 'female', languages: ['vi'] },
  { id: 'vi_male_wumg_uranus_bigtts', speaker: 'vi_male_wumg_uranus_bigtts', gender: 'male', languages: ['vi'] },
  { id: 'en_female_hayley_uranus_bigtts', speaker: 'en_female_hayley_uranus_bigtts', gender: 'female', languages: ['en'] },
  { id: 'en_male_tim_uranus_bigtts', speaker: 'en_male_tim_uranus_bigtts', gender: 'male', languages: ['en'] },
]

test('voiceSupportsLang treats missing languages / lang as supported', () => {
  assert.equal(voiceSupportsLang(VOICES[0], 'vi'), false)
  assert.equal(voiceSupportsLang(VOICES[2], 'vi'), true)
  assert.equal(voiceSupportsLang({ id: 'x' }, 'vi'), true)
  assert.equal(voiceSupportsLang(VOICES[0], ''), true)
})

test('voicesForLang keeps only matching voices in catalog order', () => {
  assert.deepEqual(
    voicesForLang(VOICES, 'vi').map((v) => v.id),
    ['vi_female_ruan_uranus_bigtts', 'vi_male_wumg_uranus_bigtts'],
  )
  // 未知语言 / 无匹配：不过滤，避免空列表
  assert.equal(voicesForLang(VOICES, undefined).length, VOICES.length)
  assert.equal(voicesForLang(VOICES, 'fr').length, VOICES.length)
})

test('defaultVoiceForLang prefers same gender, else first of language', () => {
  assert.equal(defaultVoiceForLang(VOICES, 'en')?.id, 'en_female_hayley_uranus_bigtts')
  assert.equal(defaultVoiceForLang(VOICES, 'en', 'male')?.id, 'en_male_tim_uranus_bigtts')
  assert.equal(defaultVoiceForLang(VOICES.slice(0, 3), 'vi', 'male')?.id, 'vi_female_ruan_uranus_bigtts')
  assert.equal(defaultVoiceForLang(VOICES, 'ja'), undefined)
})

test('voiceKeyForLang swaps unsupported voice keeping gender, keeps supported/unknown', () => {
  assert.equal(voiceKeyForLang(VOICES, 'zh_male_m191_uranus_bigtts', 'vi'), 'vi_male_wumg_uranus_bigtts')
  assert.equal(voiceKeyForLang(VOICES, 'zh_female_cancan_uranus_bigtts', 'en'), 'en_female_hayley_uranus_bigtts')
  assert.equal(voiceKeyForLang(VOICES, 'vi_female_ruan_uranus_bigtts', 'vi'), null)
  // 模板别名 / 复刻音色（不在目录）不强改；语言未知不改
  assert.equal(voiceKeyForLang(VOICES, 'narrator_calm', 'vi'), null)
  assert.equal(voiceKeyForLang(VOICES, 'zh_male_m191_uranus_bigtts', ''), null)
})

test('voiceKeyForLang matches backend voice_for_lang on the shared vectors', () => {
  const url = new URL('../../backend/tests/fixtures/voice_lang_vectors.json', import.meta.url)
  const data = JSON.parse(readFileSync(url, 'utf-8')) as {
    fnv1a32: [string, number][]
    catalog: { id: string; speaker: string; gender: string; languages: string[] }[]
    vectors: [string, string, string][]
  }
  for (const [key, expected] of data.fnv1a32) assert.equal(fnv1a32(key), expected, key)
  assert.ok(data.vectors.length > 10)
  for (const [src, lang, expected] of data.vectors) {
    assert.equal(voiceKeyForLang(data.catalog, src, lang), expected, `${src} → ${lang}`)
  }
  // 分散：不同的中文女声换成越南语时不全是同一个
  const viFemale = new Set(data.vectors.filter(([s, l]) => l === 'vi' && s.startsWith('zh_female_')).map((v) => v[2]))
  assert.ok(viFemale.size >= 2)
})

test('suggested speaker is dropped once the voice prompt is edited', () => {
  const suggested = 'Giọng nữ trẻ, trong trẻo'
  assert.equal(speakerForPrompt(suggested, suggested, 'vi_female_ling_uranus_bigtts'), 'vi_female_ling_uranus_bigtts')
  assert.equal(speakerForPrompt(`  ${suggested} `, suggested, 'vi_female_ling_uranus_bigtts'), 'vi_female_ling_uranus_bigtts')
  assert.equal(speakerForPrompt('Giọng nam trầm', suggested, 'vi_female_ling_uranus_bigtts'), '')
  assert.equal(speakerForPrompt(suggested, suggested, ''), '')
})
