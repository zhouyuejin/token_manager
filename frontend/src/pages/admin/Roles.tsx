import { Alert, Button, Card, Space, Table, Tag } from 'antd'
import { useNavigate } from 'react-router-dom'
import { useThemeToken } from '../../theme/useThemeToken'

const roles = [
  { role: 'admin', name: '平台管理员', permissions: '平台配置、用户、渠道、模型及日志的读写' },
  { role: 'department_admin', name: '部门管理员', permissions: '负责部门及其项目的读写' },
  { role: 'auditor', name: '审计只读', permissions: '管理接口只读；不能修改配置' },
  { role: 'user', name: '普通用户', permissions: '个人用量、API Key、申请与对话' },
]

const RolesPage = () => {
  const navigate = useNavigate()
  const { token } = useThemeToken()

  return <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <h2 style={{ margin: 0 }}>角色与权限</h2>
      <Button onClick={() => navigate('/admin/users')}>用户角色分配</Button>
    </div>
    <Alert type="info" showIcon style={{ marginBottom: 16 }} message="内置角色权限" description="权限由后端按角色执行；当前版本不提供自定义角色或权限规则编辑。审计只读角色仅展示查看入口。" />
    <Card>
      <Table
        rowKey="role"
        pagination={false}
        dataSource={roles}
        columns={[
          { title: '角色', dataIndex: 'name', render: (name: string, row: typeof roles[number]) => <Space><strong>{name}</strong><Tag>{row.role}</Tag></Space> },
          { title: '权限范围', dataIndex: 'permissions' },
          { title: '模式', dataIndex: 'role', render: (role: string) => role === 'auditor' ? <Tag color="gold">只读</Tag> : <Tag color="blue">按角色授权</Tag> },
        ]}
      />
    </Card>
  </div>
}

export default RolesPage
