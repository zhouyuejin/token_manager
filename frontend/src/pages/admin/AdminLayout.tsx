import React from 'react'

// Thin outlet wrapper for /admin/* routes. The "no default model group" warning
// is rendered contextually (sidebar dot + slim in-page banner on the ModelGroups
// page) via the shared useDefaultModelGroupWarning hook instead of a global bar.
const AdminLayout: React.FC<React.PropsWithChildren> = ({ children }) => {
  return <>{children}</>
}

export default AdminLayout
