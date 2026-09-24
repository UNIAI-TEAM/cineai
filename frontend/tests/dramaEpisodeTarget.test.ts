/** 单集目标时长：解析优先级、条数与正文门槛 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  EPISODE_TARGET_DEFAULT,
  EPISODE_TARGET_OPTIONS,
  FRAGMENT_MAX_SEC,
  episodeMaxFragments,
  estimateFragmentRange,
  formatFragmentRange,
  isScriptOverTarget,
  minEpisodeBodyChars,
  normalizeEpisodeTargetSec,
  resolveEpisodeTargetSec,
} from '../src/lib/dramaEpisodeTarget.ts'

test('resolve prefers episode, then project, then default 90', () => {
  assert.equal(resolveEpisodeTargetSec({ episodeTargetSec: 30 }, { episodeTargetSec: 120 }), 30)
  assert.equal(resolveEpisodeTargetSec({}, { episodeTargetSec: 120 }), 120)
  assert.equal(resolveEpisodeTargetSec(null, undefined), 90)
  assert.equal(resolveEpisodeTargetSec({ episodeTargetSec: 0 }, { episodeTargetSec: 120 }), 0)
  assert.equal(resolveEpisodeTargetSec({ episodeTargetSec: 45 }, { episodeTargetSec: '60' }), 60)
})

test('normalize rejects unknown values', () => {
  assert.equal(normalizeEpisodeTargetSec(true), null)
  assert.equal(normalizeEpisodeTargetSec(75), null)
  assert.equal(normalizeEpisodeTargetSec('180'), 180)
})

test('fragment budget matches backend', () => {
  assert.equal(episodeMaxFragments(90), 10)
  assert.equal(episodeMaxFragments(0), 30)
  assert.equal(episodeMaxFragments(30), 4)
  // 剧本长于目标：按目标；自动：按剧本估时；剧本更短：按剧本
  assert.deepEqual(estimateFragmentRange(90, 245), [6, 10])
  assert.deepEqual(estimateFragmentRange(0, 245), [17, 30])
  assert.deepEqual(estimateFragmentRange(90, 40), [3, 7])
  assert.equal(estimateFragmentRange(0, 0), null)
  assert.equal(formatFragmentRange([6, 10]), '6–10')
  assert.equal(formatFragmentRange([2, 2]), '2')
})

test('min body chars relaxes for short targets and warns when script is too long', () => {
  assert.equal(minEpisodeBodyChars(0), 450)
  assert.equal(minEpisodeBodyChars(90), 450)
  assert.equal(minEpisodeBodyChars(30), 150)
  assert.equal(isScriptOverTarget(90, 245), true)
  assert.equal(isScriptOverTarget(90, 100), false)
  assert.equal(isScriptOverTarget(0, 999), false)
})

test('budget matches the shared backend table', () => {
  const url = new URL('../../backend/tests/fixtures/episode_target_table.json', import.meta.url)
  const table = JSON.parse(readFileSync(url, 'utf-8')) as {
    default_target_sec: number
    fragment_max_sec: number
    rows: { target_sec: number; max_fragments: number; shot_range: [number, number] | null; min_body_chars: number }[]
  }
  assert.equal(table.default_target_sec, EPISODE_TARGET_DEFAULT)
  assert.equal(table.fragment_max_sec, FRAGMENT_MAX_SEC)
  assert.deepEqual(
    table.rows.map((row) => row.target_sec),
    [...EPISODE_TARGET_OPTIONS],
  )
  for (const row of table.rows) {
    assert.equal(episodeMaxFragments(row.target_sec), row.max_fragments, `max ${row.target_sec}`)
    assert.equal(minEpisodeBodyChars(row.target_sec), row.min_body_chars, `min chars ${row.target_sec}`)
    // 自动模式区间取决于剧本估时，后端为 null
    if (row.target_sec) assert.deepEqual(estimateFragmentRange(row.target_sec, 0), row.shot_range, `range ${row.target_sec}`)
    else assert.equal(row.shot_range, null)
  }
})
