import test from 'node:test'
import assert from 'node:assert/strict'
import { userDisplayName } from './userDisplayName.mjs'

test('display prefers nickname and falls back for existing accounts', () => {
  assert.equal(userDisplayName({ nickname: '小周', username: 'account' }), '小周')
  for (const nickname of [undefined, null, '', '  ']) {
    assert.equal(userDisplayName({ nickname, username: 'account' }), 'account')
  }
  assert.equal(userDisplayName({ user_id: 'deleted-user' }), 'deleted-user')
  assert.equal(userDisplayName(null), '')
})
