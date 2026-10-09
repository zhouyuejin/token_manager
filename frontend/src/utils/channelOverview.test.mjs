import test from 'node:test'
import assert from 'node:assert/strict'
import { channelState, quotaSummary, topChannelUsage } from './channelOverview.mjs'

const health = { status: 'active', health_status: 'healthy', windows: { '24h': { requests: 0 } }, cooldown: { keys: [] } }
test('unverified channels stay unknown and billing failures override quota warnings', () => {
  assert.equal(channelState(health).key, 'unknown')
  assert.equal(channelState({ ...health, health_status: 'unhealthy' }, { low: true }).key, 'error')
  assert.equal(channelState({ ...health, last_check_at: '2026-10-09' }).key, 'healthy')
  assert.equal(channelState(health, { low: true }).key, 'warning')
  assert.equal(channelState({ ...health, cooldown: { channel_until: '2099-01-01' } }).key, 'warning')
  assert.equal(channelState({ ...health, last_check_at: '2026-10-09', cooldown: { channel_until: '2000-01-01' } }).key, 'healthy')
  assert.equal(channelState({ ...health, status: 'disabled' }).key, 'disabled')
})
test('quota distinguishes missing data, zero balance and remaining percentage', () => {
  assert.equal(quotaSummary().text, '未接入余额／配额查询')
  assert.equal(quotaSummary({ windows: [{ raw_data: { window: { raw_data: { balance_infos: [{ total_balance: '0', currency: 'CNY' }], is_available: false } } } }] }).unavailable, true)
  assert.equal(quotaSummary({ windows: [{ limit: 100, remain: 10 }] }, 20).low, true)
  assert.equal(quotaSummary({ windows: [{ limit: 0, remain: 0 }] }).low, false)
})
test('ranking uses channel IDs, limits to five, and never mutates statistics', () => {
  const rows = Array.from({ length: 7 }, (_, i) => ({ channel_id: `ch${i}`, channel: 'same', tokens: i, requests: 7 - i, cost: i }))
  assert.deepEqual(topChannelUsage(rows, 'tokens').map(row => row.channel_id), ['ch6', 'ch5', 'ch4', 'ch3', 'ch2'])
  assert.equal(topChannelUsage(rows, 'requests')[0].channel_id, 'ch0')
  assert.equal(rows[0].tokens, 0)
  assert.deepEqual(topChannelUsage([{ channel_id: 'a', cost: null }], 'cost'), [])
})
