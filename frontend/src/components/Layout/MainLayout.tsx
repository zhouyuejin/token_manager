import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, theme } from 'antd'
import {
  DashboardOutlined,
  KeyOutlined,
  BarChartOutlined,
  SettingOutlined,
  TeamOutlined,
  CloudOutlined,
  AppstoreOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../../store/auth'

const { Header, Sider, Content } = Layout

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { token, user, logout } = useAuthStore()
  const [collapsed, setCollapsed] = useState(false)
  const { token: antToken } = theme.useToken()

  useEffect(() => {
    if (!token) {
      navigate('/login')
    }
  }, [token, navigate])

  const isAdmin = user?.role === 'admin'

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/api-keys',
      icon: <KeyOutlined />,
      label: 'API Key',
    },
    {
      key: '/stats',
      icon: <BarChartOutlined />,
      label: '用量统计',
    },
    ...(isAdmin ? [
      {
        key: 'admin',
        icon: <AppstoreOutlined />,
        label: '管理后台',
        children: [
          { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
          { key: '/admin/providers', icon: <CloudOutlined />, label: '供应商管理' },
          { key: '/admin/models', icon: <AppstoreOutlined />, label: '模型映射' },
        ]
      },
    ] : []),
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '个人设置',
    },
  ]

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: user?.username,
      disabled: true,
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout()
        navigate('/login')
      },
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ background: '#fff' }}
      >
        <div style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderBottom: `1px solid ${antToken.colorBorder}`,
        }}>
          <h2 style={{ margin: 0, color: antToken.colorPrimary }}>
            {collapsed ? 'TM' : 'Token中转平台'}
          </h2>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          padding: '0 24px', 
          background: '#fff', 
          display: 'flex', 
          justifyContent: 'flex-end',
          alignItems: 'center',
          borderBottom: `1px solid ${antToken.colorBorder}`,
        }}>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: antToken.colorPrimary }} />
              <span>{user?.username}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
