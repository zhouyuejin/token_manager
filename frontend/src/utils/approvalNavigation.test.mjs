import assert from 'node:assert/strict'
import test from 'node:test'
import { approvalNotificationLink, legacyApprovalPath } from './approvalNavigation.mjs'

test('approval notices route applicants and reviewers to the specific application', () => {
  assert.equal(approvalNotificationLink({ type: 'approval_update', metadata: { audience: 'reviewer', request_id: 'a/b' } }).href, '/approval-workbench?request_id=a%2Fb')
  assert.equal(approvalNotificationLink({ type: 'approval_result', metadata: JSON.stringify({ audience: 'requester', request_id: 'one' }) }).href, '/applications?request_id=one')
  assert.equal(approvalNotificationLink({ type: 'approval_update', metadata: { status: 'needs_info', request_id: 'one' } }).href, '/applications?request_id=one')
  assert.equal(approvalNotificationLink({ type: 'approval_update', metadata: { status: 'pending', request_id: 'one' } }).href, '/approval-workbench?request_id=one')
  assert.equal(approvalNotificationLink({ type: 'approval_result', metadata: 'bad json' }).href, '/applications')
  assert.equal(approvalNotificationLink({ type: 'system' }), null)
})

test('legacy approval links preserve request location and review intent', () => {
  assert.equal(legacyApprovalPath('?request_id=one', '#details'), '/applications?request_id=one#details')
  assert.equal(legacyApprovalPath('?tab=review&request_id=one', ''), '/approval-workbench?tab=review&request_id=one')
})
