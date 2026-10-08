import test from 'node:test'
import assert from 'node:assert/strict'
import { formatTokenCount } from './formatTokenCount.mjs'

test('token counts stay readable across Chinese units', () => {
  assert.equal(formatTokenCount(0), '0')
  assert.equal(formatTokenCount(9999), '9,999')
  assert.equal(formatTokenCount(10000), '1 万')
  assert.equal(formatTokenCount(12345678), '1234.6 万')
  assert.equal(formatTokenCount(100000000), '1 亿')
  assert.equal(formatTokenCount(123456789), '1.23 亿')
})
