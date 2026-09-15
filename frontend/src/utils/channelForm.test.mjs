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
