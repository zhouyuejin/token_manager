import { ReactNode } from 'react'
import { useAuthStore } from '../store/auth'
import { AdminPermission, hasPermission } from '../utils/adminPermissions.mjs'

export const WriteOnly = ({ children, permission = 'admin:write' }: {
  children: ReactNode
  permission?: AdminPermission
}) => {
  const permissions = useAuthStore((state) => state.user?.permissions || [])
  return hasPermission(permissions, permission) ? <>{children}</> : null
}
