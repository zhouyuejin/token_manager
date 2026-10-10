import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

test('builds text and image content, including image-only messages', async () => {
  const source = await readFile(new URL('./chatContent.ts', import.meta.url), 'utf8')
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2020 } }).outputText
  const { buildChatContent } = await import(`data:text/javascript,${encodeURIComponent(output)}`)
  globalThis.FileReader = class {
    readAsDataURL(file) {
      this.result = file.data
      this.onload()
    }
  }
  const files = [{ data: 'data:image/png;base64,YQ==' }, { data: 'data:image/jpeg;base64,Yg==' }]
  const images = [
    { type: 'image_url', image_url: { url: files[0].data } },
    { type: 'image_url', image_url: { url: files[1].data } },
  ]
  assert.equal(await buildChatContent('hello'), 'hello')
  assert.deepEqual(await buildChatContent('describe', files), [{ type: 'text', text: 'describe' }, ...images])
  assert.deepEqual(await buildChatContent('', files), images)
  globalThis.FileReader = class {
    readAsDataURL() { this.onerror() }
  }
  await assert.rejects(buildChatContent('', files), /图片读取失败/)
  delete globalThis.FileReader
})
