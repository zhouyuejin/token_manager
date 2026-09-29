// Plain-Node test for chatStorage. Run with `npm run test:utils`.

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

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

async function loadModule() {
  const source = (await readFile(new URL('./chatStorage.ts', import.meta.url), 'utf8'))
    .replace(
      "import { useAuthStore } from '../store/auth'",
      'const useAuthStore = { getState: () => ({ user: { user_id: globalThis.__testUserId } }) }',
    )
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  return import(`data:text/javascript,${encodeURIComponent(output)}`)
}

test('returns empty config when storage is empty', async () => {
  globalThis.localStorage = makeStorage()
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig } = await loadModule()
  assert.deepEqual(loadModelConfig(), {})
})

test('roundtrips a saved config', async () => {
  const store = makeStorage()
  globalThis.localStorage = store
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig, saveModelConfig } = await loadModule()
  saveModelConfig({ modelId: 'm-2' })
  assert.deepEqual(loadModelConfig(), { modelId: 'm-2' })
})

test('overwrites a previous config', async () => {
  const store = makeStorage()
  globalThis.localStorage = store
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig, saveModelConfig } = await loadModule()
  saveModelConfig({ modelId: 'm-2' })
  saveModelConfig({ modelId: 'm-7' })
  assert.deepEqual(loadModelConfig(), { modelId: 'm-7' })
})

test('coerces non-string fields to undefined', async () => {
  const store = makeStorage()
  store.setItem('chat.modelConfig.v1.user-1', JSON.stringify({ modelId: null, extra: 'ignored' }))
  globalThis.localStorage = store
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig } = await loadModule()
  assert.deepEqual(loadModelConfig(), { modelId: undefined })
})

test('returns empty config on corrupted JSON', async () => {
  const store = makeStorage()
  store.setItem('chat.modelConfig.v1.user-1', '{not json')
  globalThis.localStorage = store
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig } = await loadModule()
  assert.deepEqual(loadModelConfig(), {})
})

test('keeps saved configs isolated by user', async () => {
  globalThis.localStorage = makeStorage()
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig, saveModelConfig } = await loadModule()
  saveModelConfig({ modelId: 'm-1' })

  globalThis.__testUserId = 'user-2'
  assert.deepEqual(loadModelConfig(), {})
  saveModelConfig({ modelId: 'm-2' })

  globalThis.__testUserId = 'user-1'
  assert.deepEqual(loadModelConfig(), { modelId: 'm-1' })
})

test('clears only the logged-out user config', async () => {
  globalThis.localStorage = makeStorage()
  globalThis.__testUserId = 'user-1'
  const { loadModelConfig, saveModelConfig, clearModelConfigStorage } = await loadModule()
  saveModelConfig({ modelId: 'm-1' })
  clearModelConfigStorage('user-1')
  assert.deepEqual(loadModelConfig(), {})

  globalThis.__testUserId = 'user-2'
  saveModelConfig({ modelId: 'm-2' })
  clearModelConfigStorage('user-1')
  assert.deepEqual(loadModelConfig(), { modelId: 'm-2' })
})
