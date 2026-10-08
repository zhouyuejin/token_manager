import assert from 'node:assert/strict'
import test from 'node:test'
import { normalizeApiDates } from './normalizeApiDates.mjs'

test('normalizes nested UTC timestamps without changing dates or zoned values', () => {
  assert.deepEqual(normalizeApiDates({ items: [{
    created_at: '2026-09-20T08:00:00',
    decided_at: '2026-09-20 09:00:00',
    expires_at: '2026-09-20T10:00:00+08:00',
    business_date: '2026-09-20',
  }] }), { items: [{
    created_at: '2026-09-20T08:00:00Z',
    decided_at: '2026-09-20T09:00:00Z',
    expires_at: '2026-09-20T10:00:00+08:00',
    business_date: '2026-09-20',
  }] })
})
