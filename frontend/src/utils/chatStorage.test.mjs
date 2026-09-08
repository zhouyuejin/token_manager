// Plain-Node test for chatStorage. No test framework required: uses
// node:test (built-in to Node >=18). Run with:
//   node --test frontend/src/utils/chatStorage.test.mjs
//
// Strategy: stub `localStorage` on globalThis before importing the module
// so the SUT's references resolve to the stub. The stub is a fresh in-memory
// map per test (set in beforeEach).

import { test } from 'node:test'
import assert from 'node:assert/strict'

const makeStorage = () => {
  const map = new Map()
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    clear: () => map.clear(),
    _map: map,
  }
}

const importFresh = async () => {
  // Bust the ESM cache so the module re-reads globalThis.localStorage.
  const url = new URL('./chatStorage.ts', import.meta.url)
  const mod = await import(`${url}?t=${Date.now()}`)
  return mod
}

test('returns empty config when storage is empty', async () => {
  globalThis.localStorage = makeStorage()
  const { loadModelConfig } = await importFresh()
  assert.deepEqual(loadModelConfig(), {})
})

test('roundtrips a saved config', async () => {
  const store = makeStorage()
  globalThis.localStorage = store
  const { loadModelConfig, saveModelConfig } = await importFresh()
  saveModelConfig({ modelId: 'm-2' })
  assert.deepEqual(loadModelConfig(), { modelId: 'm-2' })
})

test('overwrites a previous config', async () => {
  const store = makeStorage()
  globalThis.localStorage = store
  const { loadModelConfig, saveModelConfig } = await importFresh()
  saveModelConfig({ modelId: 'm-2' })
  saveModelConfig({ modelId: 'm-7' })
  assert.deepEqual(loadModelConfig(), { modelId: 'm-7' })
})

test('coerces non-string fields to undefined', async () => {
  const store = makeStorage()
  store.setItem('chat.modelConfig.v1', JSON.stringify({ modelId: null, extra: 'ignored' }))
  globalThis.localStorage = store
  const { loadModelConfig } = await importFresh()
  assert.deepEqual(loadModelConfig(), { modelId: undefined })
})

test('returns empty config on corrupted JSON', async () => {
  const store = makeStorage()
  store.setItem('chat.modelConfig.v1', '{not json')
  globalThis.localStorage = store
  const { loadModelConfig } = await importFresh()
  assert.deepEqual(loadModelConfig(), {})
})
