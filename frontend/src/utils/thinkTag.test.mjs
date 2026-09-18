// Plain-Node test for stripThinkTags. Run with:
//   node --test frontend/src/utils/thinkTag.test.mjs
//
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const source = await readFile(new URL('./thinkTag.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext },
})
const { stripThinkTags } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

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

test('hides unclosed think block while streaming', () => {
  const input = '<think>用户问的是 X\n答案是 Y'
  assert.equal(stripThinkTags(input), '')
  assert.equal(stripThinkTags('正文<think>尚未完成'), '正文')
})

test('keeps reasoning hidden at every character boundary of a stream', () => {
  const thinking = '<think>正在分析问题</think>'
  for (let length = 1; length <= thinking.length; length++) {
    assert.equal(stripThinkTags(thinking.slice(0, length)), '', `boundary ${length}`)
  }
  assert.equal(stripThinkTags(`${thinking}正式`), '正式')
  assert.equal(stripThinkTags(`${thinking}正式回复`), '正式回复')
})

test('preserves answers before a second partially streamed think tag', () => {
  assert.equal(stripThinkTags('<think>first</think>正文<thi'), '正文')
  assert.equal(stripThinkTags('<think>first</think>正文<think>second</thi'), '正文')
  assert.equal(stripThinkTags('比较：1 < 2'), '比较：1 < 2')
})

test('handles think block containing newlines', () => {
  const input = '<think>line1\nline2\nline3</think>answer'
  assert.equal(stripThinkTags(input), 'answer')
})

test('non-greedy: only matches up to the first closing tag', () => {
  const input = '<think>a</think>keep this<think>b</think>end'
  assert.equal(stripThinkTags(input), 'keep thisend')
})
