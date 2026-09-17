import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadModule() {
  let source = await readFile(new URL('./channelForm.ts', import.meta.url), 'utf8')
  source = source.replace("import { $message } from './message'", "const $message = { warning() {}, error() {} }")
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  return import(`data:text/javascript,${encodeURIComponent(output)}`)
}

test('prepareChannelPayload removes blank api key when editing', async () => {
  const { prepareChannelPayload } = await loadModule()

  assert.deepEqual(
    prepareChannelPayload({ name: 'OpenAI', api_key: '   ', extra_keys: '' }, true),
    { name: 'OpenAI' },
  )
})

test('prepareChannelPayload keeps new api key and parses extra keys', async () => {
  const { prepareChannelPayload } = await loadModule()

  assert.deepEqual(
    prepareChannelPayload({ api_key: 'sk-new', extra_keys: '["sk-extra"]' }, true),
    { api_key: 'sk-new', extra_keys: ['sk-extra'] },
  )
})

test('channel key payload rejects null, blank and masked replacements', async () => {
  const { prepareChannelPayload } = await loadModule()
  for (const extra_keys of ['null', '[null]', '[""]', '["  "]', '["sk-old...1234"]', '["***"]']) {
    assert.throws(() => prepareChannelPayload({ extra_keys }, true))
  }
  assert.throws(() => prepareChannelPayload({ api_key: 'sk-old...1234' }, true))
  assert.deepEqual(prepareChannelPayload({ extra_keys: '[]' }, true), { extra_keys: [] })
})

test('per-item extra key edits omit unchanged secrets and explicitly delete selected items', async () => {
  const { prepareChannelPayload } = await loadModule()
  assert.deepEqual(prepareChannelPayload({ extra_key_edits: [{ action: 'keep' }, { action: 'replace', value: 'sk-new' }, { action: 'remove' }] }, true), {
    extra_key_updates: { 1: 'sk-new', 2: null },
  })
  assert.deepEqual(prepareChannelPayload({ extra_key_edits: [{ action: 'keep' }] }, true), {})
  assert.throws(() => prepareChannelPayload({ extra_key_edits: [{ action: 'replace', value: '' }] }, true))
})

test('explicit channel modes preserve, replace or clear keys without leaking form controls', async () => {
  const { prepareChannelPayload } = await loadModule()
  assert.deepEqual(prepareChannelPayload({ main_key_action: 'keep', api_key: 'sk-stale', extra_keys_action: 'keep', extra_keys: '["sk-stale"]' }, true), {})
  assert.deepEqual(prepareChannelPayload({ extra_keys_action: 'clear', extra_keys: '' }, true), { extra_keys: [] })
  assert.throws(() => prepareChannelPayload({ main_key_action: 'replace', api_key: '' }, true))
})

test('secret list revision is sent only for individual updates', async () => {
  const { prepareChannelPayload } = await loadModule()
  assert.deepEqual(prepareChannelPayload({ extra_keys_action: 'keep', extra_keys_revision: 'revision' }, true), {})
  assert.deepEqual(prepareChannelPayload({ extra_keys_action: 'edit', extra_keys_revision: 'revision', extra_key_edits: [{ action: 'remove' }] }, true), {
    extra_keys_revision: 'revision', extra_key_updates: { 0: null },
  })
})
