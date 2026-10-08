import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'
import { theme } from 'antd'

const source = await readFile(new URL('../theme/themes.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2020 } }).outputText
const moduleUrl = new URL('../../node_modules/antd/lib/index.js', import.meta.url).href
const { createCustomTheme } = await import(`data:text/javascript,${encodeURIComponent(compiled.replace("from 'antd'", `from '${moduleUrl}'`))}`)

test('custom primary generates matching controls and distinct light/dark surfaces', () => {
  assert.equal(typeof createCustomTheme, 'function')
  const light = createCustomTheme('#d4380d', 'light')
  const dark = createCustomTheme('#d4380d', 'dark')
  const lightToken = theme.getDesignToken(light)
  const darkToken = theme.getDesignToken(dark)
  assert.equal(light.token.colorPrimary, '#d4380d')
  assert.equal(dark.token.colorPrimary, '#d4380d')
  assert.notEqual(lightToken.colorPrimaryHover, theme.getDesignToken(createCustomTheme('#2563eb', 'light')).colorPrimaryHover)
  assert.notEqual(lightToken.colorBgContainer, darkToken.colorBgContainer)
  assert.equal(lightToken.colorLink, lightToken.colorPrimary)
  assert.equal(light.components.Button.controlHeight, 32)
  assert.equal(dark.components.Button.controlHeightSM, 32)
})
