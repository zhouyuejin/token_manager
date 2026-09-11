// Plain-Node test for stripThinkTags. Run with:
//   node --test frontend/src/utils/thinkTag.test.mjs
//
// Re-exports the TS helper via esbuild-like transpile is overkill here,
// so we mirror the regex instead. The contract tested is the *behavior*
// — if you change the regex in thinkTag.ts, mirror it here.

import { test } from 'node:test'
import assert from 'node:assert/strict'

// Mirror of THINK_TAG_RE from thinkTag.ts. Keep these in sync.
const THINK_TAG_RE = /<think>[\s\S]*?<\/think>/g
const stripThinkTags = (content) => (content ?? '').replace(THINK_TAG_RE, '')

test('returns empty string for empty input', () => {
  assert.equal(stripThinkTags(''), '')
})

test('tolerates null/undefined input', () => {
  assert.equal(stripThinkTags(null), '')
  assert.equal(stripThinkTags(undefined), '')
})

test('passes through plain content unchanged', () => {
  const plain = '你好世界\n这是一段普通回复。'
  assert.equal(stripThinkTags(plain), plain)
})

test('strips a single think block at the start', () => {
  const input = '<think>让我分析一下这个问题...\n用户问的是 X</think>这是最终答案。'
  assert.equal(stripThinkTags(input), '这是最终答案。')
})

test('strips a think block in the middle', () => {
  const input = '先给结论：\n<think>reasoning here</think>\n详细说明如下。'
  assert.equal(stripThinkTags(input), '先给结论：\n\n详细说明如下。')
})

test('strips multiple think blocks', () => {
  const input = '<think>first</think>中间<think>second</think>结尾'
  assert.equal(stripThinkTags(input), '中间结尾')
})

test('does not match unclosed think block', () => {
  // Half-streamed content where closing tag hasn't arrived yet.
  // We deliberately do NOT eat unclosed blocks, so the user sees
  // the partial state instead of losing the trailing answer.
  const input = '<think>用户问的是 X\n答案是 Y'
  assert.equal(stripThinkTags(input), input)
})

test('handles think block containing newlines', () => {
  const input = '<think>line1\nline2\nline3</think>answer'
  assert.equal(stripThinkTags(input), 'answer')
})

test('non-greedy: only matches up to the first closing tag', () => {
  const input = '<think>a</think>keep this<think>b</think>end'
  assert.equal(stripThinkTags(input), 'keep thisend')
})
