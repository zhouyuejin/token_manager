import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button } from 'antd'
import { getModelGroups, ModelGroup } from '../../api/modelGroups'

/**
 * Admin shared layout wrapper.
 * Shows a yellow closable warning banner when no active default model group exists.
 * Banner dismissal is session-only (cleared on tab close).
 */
const AdminLayout: React.FC<React.PropsWithChildren> = ({ children }) => {
  const navigate = useNavigate()
  const [noDefaultGroup, setNoDefaultGroup] = useState(false)
  const [bannerDismissed, setBannerDismissed] = useState(false)

  useEffect(() => {
    const dismissed = sessionStorage.getItem('default_group_banner_dismissed')
    if (dismissed === '1') {
      setBannerDismissed(true)
      return
    }

    getModelGroups()
      .then(res => {
        const items: ModelGroup[] = res.items || []
        const hasActiveDefault = items.some(
          g => g.is_default === 1 && g.status === 'active'
        )
        setNoDefaultGroup(!hasActiveDefault)
      })
      // Silently ignore fetch errors — banner stays hidden on network failure.
      .catch(() => {})
  }, [])

  const handleDismiss = () => {
    sessionStorage.setItem('default_group_banner_dismissed', '1')
    setBannerDismissed(true)
  }

  const showBanner = noDefaultGroup && !bannerDismissed

  return (
    <div>
      {showBanner && (
        <Alert
          type="warning"
          showIcon
          message="系统尚未设置默认模型分组，新用户可能无法正常使用 API Key。"
          description={
            <Button
              type="link"
              onClick={() => navigate('/admin/model-groups')}
              style={{ padding: 0, height: 'auto', fontWeight: 500 }}
            >
              前往设置 →
            </Button>
          }
          closable
          onClose={handleDismiss}
          style={{
            marginBottom: 16,
            borderRadius: 8,
          }}
        />
      )}
      {children}
    </div>
  )
}

export default AdminLayout
