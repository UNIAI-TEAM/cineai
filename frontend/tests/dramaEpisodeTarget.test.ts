/** 单集目标时长：解析优先级、条数与正文门槛 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  episodeMaxFragments,
  estimateFragmentCount,
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
  assert.equal(estimateFragmentCount(90, 245), 8)
  assert.equal(estimateFragmentCount(0, 245), 21)
})

test('min body chars relaxes for short targets and warns when script is too long', () => {
  assert.equal(minEpisodeBodyChars(0), 500)
  assert.equal(minEpisodeBodyChars(90), 450)
  assert.equal(minEpisodeBodyChars(30), 150)
  assert.equal(isScriptOverTarget(90, 245), true)
  assert.equal(isScriptOverTarget(90, 100), false)
  assert.equal(isScriptOverTarget(0, 999), false)
})
