/** Chọn model phía user: rỗng = Tự động; model bị admin gỡ thì về Tự động; catalog chưa về thì giữ nguyên. */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { modelProviderLabel, reconcileCatalogModel } from '../src/lib/mediaModelChoice.ts'

const MODELS = [{ id: 'dola-seedream-5-0-pro-260628' }, { id: 'gpt-image-2' }]

test('reconcileCatalogModel keeps a still-allowed choice', () => {
  assert.equal(reconcileCatalogModel('gpt-image-2', MODELS), 'gpt-image-2')
})

test('reconcileCatalogModel turns a removed model into Auto (empty)', () => {
  assert.equal(reconcileCatalogModel('seedream-5.0', MODELS), '')
})

test('reconcileCatalogModel keeps Auto and never pins a default', () => {
  assert.equal(reconcileCatalogModel('', MODELS), '')
  assert.equal(reconcileCatalogModel(undefined, MODELS), '')
})

test('reconcileCatalogModel returns Auto when the catalog is empty', () => {
  assert.equal(reconcileCatalogModel('seedream-5.0', []), '')
})

test('reconcileCatalogModel leaves the value alone while the catalog is unknown', () => {
  assert.equal(reconcileCatalogModel(' seedream-5.0 ', null), 'seedream-5.0')
})

test('reconcileCatalogModel matches case/whitespace-insensitively, like the backend normalize_model_name, and returns the catalog id', () => {
  assert.equal(reconcileCatalogModel('GPT-Image-2', MODELS), 'gpt-image-2')
  assert.equal(reconcileCatalogModel('GPT- Image-2', MODELS), 'gpt-image-2')
})

test('modelProviderLabel shows description only, never the internal provider id', () => {
  assert.equal(modelProviderLabel({ description: 'Nhanh' }), 'Nhanh')
  assert.equal(modelProviderLabel({ description: '  ' }), '')
  assert.equal(modelProviderLabel({}), '')
})
