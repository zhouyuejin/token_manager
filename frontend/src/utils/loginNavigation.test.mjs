import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import { defaultAdminPath } from './adminPermissions.mjs'

const source = ts.createSourceFile('Login.tsx', readFileSync(new URL('../pages/Login.tsx', import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
let passwordHandler
let oidcHandler
function findHandlers(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'onFinish') passwordHandler = node.initializer
  if (ts.isCallExpression(node) && node.expression.getText(source) === 'getCurrentUser().then') oidcHandler = node.arguments[0]
  ts.forEachChild(node, findHandlers)
}
findHandlers(source)

function loadHandler(node, user, paths) {
  assert.ok(node, 'login handler exists')
  const code = ts.transpileModule(`(${node.getText(source)})`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  return vm.runInNewContext(code, {
    username: 'test', password: 'test', login: async () => {},
    message: { success() {}, error() {} },
    useAuthStore: { getState: () => ({ user }), setState() {} },
    setTimeout: callback => callback(),
    defaultAdminPath,
    navigate: path => paths.push(path),
  })
}

const roles = [
  { role: 'department_admin', permissions: ['department:read', 'department:write'], path: '/admin/department-dashboard' },
  { role: 'admin', permissions: ['admin:read', 'admin:write', 'department:read', 'department:write'], path: '/admin/dashboard' },
  { role: 'auditor', permissions: ['admin:read'], path: '/admin/dashboard' },
  { role: 'user', permissions: [], path: '/stats' },
]

for (const user of roles) {
  test(`password login opens ${user.role} dashboard`, async () => {
    const paths = []
    await loadHandler(passwordHandler, user, paths)()
    assert.deepEqual(paths, [user.path])
  })
  test(`enterprise login opens ${user.role} dashboard`, () => {
    const paths = []
    loadHandler(oidcHandler, user, paths)(user)
    assert.deepEqual(paths, [user.path])
  })
}
