import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('./approvalPresentation.ts', import.meta.url), 'utf8')
const ast = ts.createSourceFile('Approvals.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
const declaration = ast.statements.find(node => ts.isVariableStatement(node) && node.declarationList.declarations.some(item => item.name.getText(ast) === 'summary'))
const code = ts.transpileModule(declaration.getText(ast), { compilerOptions: { module: ts.ModuleKind.ES2020 } }).outputText
const { summary } = await import(`data:text/javascript,${encodeURIComponent(code)}`)

test('approval summary shows project names for Key and project-access requests with ID fallback', () => {
  const projects = [{ project_id: 'project_123', name: '测试项目' }]
  assert.equal(summary({ request_type: 'api_key', payload: { name: '开发调试', project_id: 'project_123' } }, projects), '用途：开发调试；项目：测试项目')
  assert.equal(summary({ request_type: 'project_access', payload: {}, target_id: 'project_123' }, projects), '申请加入项目：测试项目')
  assert.equal(summary({ request_type: 'project_access', payload: { project_id: 'unknown' } }, projects), '申请加入项目：unknown')
  assert.equal(summary({ request_type: 'project_access', payload: {} }, []), '申请加入项目：—')
  assert.equal(summary({ request_type: 'quota', payload: { amount: 100 } }, projects), '申请增加 100 tokens')
})
