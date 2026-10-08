import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const moduleUrl = (code) => `data:text/javascript,${encodeURIComponent(code).replaceAll("'", "%27")}`
const zustandUrl = new URL('../../node_modules/zustand/esm/index.mjs', import.meta.url).href
const middlewareUrl = new URL('../../node_modules/zustand/esm/middleware.mjs', import.meta.url).href
async function compile(path, imports) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8')
  let code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020 } }).outputText
  for (const [name, url] of Object.entries(imports)) code = code.replaceAll(`from '${name}'`, `from '${url}'`)
  return moduleUrl(code)
}

const notificationUrl = await compile('../store/notification.ts', { zustand: zustandUrl })
const { useNotificationStore } = await import(notificationUrl)
const authApiUrl = moduleUrl(`
  export const login = async () => ({ access_token: 'user-token', refresh_token: 'user-refresh' });
  export const getCurrentUser = async () => ({ user_id: 'ordinary-user' });
  export const refresh = async () => ({});
  export const logoutServer = async () => {};
`)
const authUrl = await compile('../store/auth.ts', {
  zustand: zustandUrl,
  'zustand/middleware': middlewareUrl,
  '../api/auth': authApiUrl,
  './notification': notificationUrl,
  '../utils/chatStorage': moduleUrl('export const clearModelConfigStorage = () => {};'),
  swr: moduleUrl('export const mutate = async () => {};'),
})
// Persist middleware uses the same browser storage boundary as the app.
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
const { useAuthStore } = await import(authUrl)

test('logout then login without reload clears previous account notifications and badge', async () => {
  useAuthStore.setState({ token: 'admin-token', refreshToken: 'admin-refresh', user: { user_id: 'admin' } })
  useNotificationStore.getState().replaceNotifications([{ notif_id: 'admin-private-message' }], 7)
  await useAuthStore.getState().logout()
  assert.deepEqual(useNotificationStore.getState().notifications, [])
  assert.equal(useNotificationStore.getState().unreadCount, 0)
  await useAuthStore.getState().login({ username: 'ordinary-user', password: 'test' })
  assert.equal(useAuthStore.getState().user.user_id, 'ordinary-user')
  assert.deepEqual(useNotificationStore.getState().notifications, [])
  assert.equal(useNotificationStore.getState().unreadCount, 0)
})

test('authentication loss and direct account changes clear notifications, token refresh preserves them', () => {
  useAuthStore.setState({ token: 'admin-token', user: { user_id: 'admin' } })
  useNotificationStore.getState().replaceNotifications([{ notif_id: 'admin-message' }], 3)
  useAuthStore.getState().setAuth('refreshed-admin-token', 'refreshed-admin-refresh')
  assert.equal(useNotificationStore.getState().notifications.length, 1)
  assert.equal(useNotificationStore.getState().unreadCount, 3)
  useAuthStore.setState({ token: null, user: null })
  assert.deepEqual(useNotificationStore.getState().notifications, [])
  assert.equal(useNotificationStore.getState().unreadCount, 0)
  useAuthStore.setState({ token: 'admin-token', user: { user_id: 'admin' } })
  useNotificationStore.getState().replaceNotifications([{ notif_id: 'admin-message' }], 3)
  useAuthStore.setState({ token: 'user-token', user: { user_id: 'ordinary-user' } })
  assert.deepEqual(useNotificationStore.getState().notifications, [])
  assert.equal(useNotificationStore.getState().unreadCount, 0)
})
