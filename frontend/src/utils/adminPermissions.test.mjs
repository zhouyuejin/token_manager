import test from 'node:test'
import assert from 'node:assert/strict'
import { canAccessAdminPath, canReadAdminPath, canWriteAdminPath, defaultAdminPath } from './adminPermissions.mjs'

const roles = {
  admin: ['admin:read', 'admin:write', 'department:read', 'department:write'],
  department_admin: ['department:read', 'department:write'],
  auditor: ['admin:read'],
  user: [],
}

test('admin routes and menus follow effective permissions for each role', () => {
  assert.equal(defaultAdminPath(roles.admin), '/admin/dashboard')
  assert.equal(defaultAdminPath(roles.department_admin), '/admin/departments')
  assert.equal(defaultAdminPath(roles.auditor), '/admin/dashboard')
  assert.equal(defaultAdminPath(roles.user), '/stats')

  assert.equal(canAccessAdminPath('/admin/projects', roles.department_admin), true)
  assert.equal(canAccessAdminPath('/admin/projects', roles.auditor), false)
  assert.equal(canAccessAdminPath('/admin/users', roles.auditor), true)
  assert.equal(canAccessAdminPath('/admin/users', roles.user), false)
  assert.equal(canAccessAdminPath('/admin/channels/new', roles.auditor), false)
  assert.equal(canAccessAdminPath('/admin/channels/new', roles.admin), true)
  assert.equal(canAccessAdminPath('/admin/billing', roles.auditor), false)
  assert.equal(canAccessAdminPath('/admin/approvals', roles.auditor), false)
})

test('read access never grants management writes', () => {
  assert.equal(canReadAdminPath('/admin/health', roles.auditor), true)
  assert.equal(canWriteAdminPath('/admin/health', roles.auditor), false)
  assert.equal(canWriteAdminPath('/admin/departments', roles.department_admin), true)
  assert.equal(canWriteAdminPath('/admin/projects', roles.auditor), false)
})
