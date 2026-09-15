import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadModule() {
  const source = await readFile(new URL('./apiKeyWhitelist.ts', import.meta.url), 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  return import(`data:text/javascript,${encodeURIComponent(output)}`)
}

test('parseApiKeyWhitelist splits lines and commas', async () => {
  const { parseApiKeyWhitelist } = await loadModule()

  assert.deepEqual(
    parseApiKeyWhitelist('10.0.0.1, 10.0.0.0/8\n203.0.113.5'),
    ['10.0.0.1', '10.0.0.0/8', '203.0.113.5'],
  )
})

test('parseApiKeyWhitelist drops blank items', async () => {
  const { parseApiKeyWhitelist } = await loadModule()

  assert.deepEqual(parseApiKeyWhitelist(' \n,  ,10.0.0.1,'), ['10.0.0.1'])
})

test('formatApiKeyWhitelist renders one entry per line', async () => {
  const { formatApiKeyWhitelist } = await loadModule()

  assert.equal(formatApiKeyWhitelist(['10.0.0.1', '10.0.0.0/8']), '10.0.0.1\n10.0.0.0/8')
})
