import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadUsersApi() {
  const source = (await readFile(new URL('../api/users.ts', import.meta.url), 'utf8'))
    .replace(
      "import { get, post, put, del } from './request'",
      'const { get, post, put, del } = globalThis.__testRequest',
    )
    .replace(
      "import { hashPassword } from '../utils/crypto'",
      'const hashPassword = globalThis.__testHashPassword',
    )
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText
  return import(`data:text/javascript,${encodeURIComponent(output)}`)
}

test('changePassword sends hashes to the personal password endpoint', async () => {
  const requests = []
  globalThis.__testRequest = {
    get: () => {},
    post: () => {},
    put: (...args) => requests.push(args),
    del: () => {},
  }
  globalThis.__testHashPassword = async (password) => `hashed:${password}`

  const { changePassword } = await loadUsersApi()
  await changePassword({ old_password: 'old-pass', new_password: 'new-pass' })

  assert.deepEqual(requests, [[
    '/users/me/password',
    { old_password: 'hashed:old-pass', new_password: 'hashed:new-pass' },
  ]])
})
