import { test } from 'node:test'
import assert from 'node:assert/strict'
import { modelUpdate } from './modelUpdate.mjs'

test('metadata edits do not freeze USD source prices into CNY', () => {
  const model = { display_name: 'old', price_per_1k_input: 0.000007123456, price_per_1k_output: 0.001, price_per_request: 0 }
  const update = modelUpdate({ ...model, display_name: 'new' }, model)
  assert.equal(update.display_name, 'new')
  assert.equal('price_per_1k_input' in update, false)
  assert.equal('price_per_1k_output' in update, false)
  assert.equal('price_per_request' in update, false)
})

test('explicit tiny price change is retained without rounding', () => {
  assert.deepEqual(modelUpdate({ price_per_1k_input: 0.000007123457 }, { price_per_1k_input: 0.000007123456 }),
    { price_per_1k_input: 0.000007123457 })
})
