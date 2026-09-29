import { Alert, Button, Card, Space, Table, Tag } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useThemeToken } from '../../theme/useThemeToken'
import { RolePermissions } from '../../api/admin'
import { useSwrData } from '../../hooks/useSwr'
import { useAuthStore } from '../../store/auth'
import { hasPermission } from '../../utils/adminPermissions.mjs'

const roleNames: Record<string, string> = {
  admin: '平台管理员',
  department_admin: '部门管理员',
  auditor: '审计只读',
  user: '普通用户',
}

const RolesPage = () => {
  const navigate = useNavigate()
  const { token } = useThemeToken()
  const permissions = useAuthStore((state) => state.user?.permissions || [])
  const { data, error, isLoading } = useSwrData<{ items: RolePermissions[] }>('/admin/roles/permissions')

  return <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <h2 style={{ margin: 0 }}>角色与权限</h2>
      {hasPermission(permissions, 'admin:write') && <Button onClick={() => navigate('/admin/users')}>用户角色分配</Button>}
    </div>
    <Alert type="info" showIcon style={{ marginBottom: 16 }} message="内置角色权限" description="权限为后端当前授权表中的实际内容；平台管理员的完整权限由后端内置。此页面不提供权限规则编辑。" />
    {error && <Alert type="error" showIcon message="权限加载失败" description="请刷新后重试。" style={{ marginBottom: 16 }} />}
    <Card>
      <Table
        rowKey="role"
        pagination={false}
        loading={isLoading}
        dataSource={data?.items || []}
        columns={[
          { title: '角色', dataIndex: 'role', render: (role: string) => <Space><strong>{roleNames[role] || role}</strong><Tag>{role}</Tag></Space> },
          { title: '后端授权', dataIndex: 'permissions', render: (items: string[]) => items.length ? items.join('、') : '无管理权限' },
          { title: '模式', dataIndex: 'role', render: (role: string) => role === 'auditor' ? <Tag color="gold">只读</Tag> : <Tag color="blue">按后端授权执行</Tag> },
        ]}
      />
    </Card>
  </div>
}

export default RolesPage
