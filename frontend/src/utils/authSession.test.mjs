import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isAuthSessionCurrent } from './authSession.mjs'

test('does not sync user data fetched for a previous session', () => {
  assert.equal(isAuthSessionCurrent('admin-token', 'user-token'), false)
  assert.equal(isAuthSessionCurrent('user-token', 'user-token'), true)
})
