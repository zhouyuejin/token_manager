import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Spin } from 'antd'
import { useAuthStore } from '../../store/auth'
import { canAccessAdminPath, defaultAdminPath } from '../../utils/adminPermissions.mjs'

// Thin outlet wrapper for /admin/* routes. The "no default model group" warning
// is rendered contextually (sidebar dot + slim in-page banner on the ModelGroups
// page) via the shared useDefaultModelGroupWarning hook instead of a global bar.
const AdminLayout: React.FC<React.PropsWithChildren> = ({ children }) => {
  const user = useAuthStore((state) => state.user)
  const location = useLocation()
  if (!user) return <Spin style={{ display: 'block', margin: '20vh auto' }} />
  if (!canAccessAdminPath(location.pathname, user.permissions)) {
    return <Navigate to={defaultAdminPath(user.permissions)} replace />
  }
  return <>{children}</>
}

export default AdminLayout
