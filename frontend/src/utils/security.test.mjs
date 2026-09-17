import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadModule() {
  const source = await readFile(new URL('./security.ts', import.meta.url), 'utf8').catch(() => '')
  return import(`data:text/javascript,${encodeURIComponent(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2020 } }).outputText)}`)
}

test('lifecycle status handles expiry boundary and prioritizes revoked and frozen', async () => {
  const { getApiKeyStatus } = await loadModule()
  assert.equal(typeof getApiKeyStatus, 'function')
  const key = { status: 'active', expires_at: '2026-09-17T00:00:00Z' }
  const now = Date.parse(key.expires_at)
  assert.equal(getApiKeyStatus(key, now), 'expired')
  assert.equal(getApiKeyStatus({ ...key, frozen_at: '2026-09-16T00:00:00Z' }, now), 'frozen')
  assert.equal(getApiKeyStatus({ ...key, status: 'revoked', frozen_at: '2026-09-16T00:00:00Z' }, now), 'revoked')
  assert.equal(getApiKeyStatus({ status: 'unknown' }, now), 'unknown')
})

test('masking never shows an entire short or long key', async () => {
  const { maskKey } = await loadModule()
  assert.equal(typeof maskKey, 'function')
  assert.equal(maskKey('short'), '***')
  assert.equal(maskKey('sk-123456789012345'), 'sk-123...2345')
  assert.equal(maskKey('sk-123...2345'), 'sk-123...2345')
})

test('error feedback preserves backend security and stream error reasons', async () => {
  const { getRequestErrorMessage } = await loadModule()
  assert.equal(typeof getRequestErrorMessage, 'function')
  for (const reason of ['IP 不匹配', 'Key 已过期', 'Key 已吊销', 'Key 已自动冻结', 'RPM 限流']) {
    assert.equal(getRequestErrorMessage({ detail: reason }, '请求失败'), reason)
    assert.equal(getRequestErrorMessage({ error: { message: reason } }, '请求失败'), reason)
  }
  assert.equal(getRequestErrorMessage({ detail: [{ loc: ['body', 'name'], msg: '必填' }] }, '请求失败'), 'body.name: 必填')
  assert.equal(getRequestErrorMessage({}, '没有权限'), '没有权限')
})
