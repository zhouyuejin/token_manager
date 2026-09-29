const departmentPaths = ['/admin/projects', '/admin/departments']

export const hasPermission = (permissions = [], permission) => permissions.includes(permission)

export const canReadAdminPath = (path, permissions = []) => {
  if (path === '/admin/approvals' || path === '/admin/billing') {
    return hasPermission(permissions, 'admin:read') && hasPermission(permissions, 'department:read')
  }
  return hasPermission(permissions, departmentPaths.includes(path) ? 'department:read' : 'admin:read')
}

export const defaultAdminPath = (permissions = []) => {
  if (hasPermission(permissions, 'admin:read')) return '/admin/dashboard'
  if (hasPermission(permissions, 'department:read')) return '/admin/departments'
  return '/stats'
}

export const canWriteAdminPath = (path, permissions = []) =>
  hasPermission(permissions, departmentPaths.some((item) => path.startsWith(item)) ? 'department:write' : 'admin:write')

export const canAccessAdminPath = (path, permissions = []) => {
  if (/\/(new|edit)(\/|$)/.test(path)) return canWriteAdminPath(path, permissions)
  return canReadAdminPath(departmentPaths.find((item) => path.startsWith(`${item}/`)) || path, permissions)
}
