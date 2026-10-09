import assert from 'node:assert/strict'
import test from 'node:test'
import { modelDisplayName } from './modelDisplayName.mjs'

test('preserves provider prefixes in model IDs and configured display names', () => {
  for (const model of ['deepseek-chat', 'deepseek-reasoner', 'gemini-flash', 'MiniMax-M2.7-highspeed']) {
    assert.equal(modelDisplayName(model), model)
    assert.equal(modelDisplayName(model, model), model)
  }
})

test('uses the configured display name and falls back to the full model ID', () => {
  assert.equal(modelDisplayName('deepseek-chat', 'DeepSeek Chat'), 'DeepSeek Chat')
  assert.equal(modelDisplayName('deepseek-chat', ''), 'deepseek-chat')
  assert.equal(modelDisplayName('deepseek-chat', null), 'deepseek-chat')
})
