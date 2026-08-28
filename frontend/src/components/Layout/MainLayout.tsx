import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, MenuProps } from 'antd'
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
  

  useEffect(() => {
    if (!token) {
      navigate('/login')
    }
  }, [token, navigate])

  const isAdmin = user?.role === 'admin'

  const menuItems: MenuProps['items'] = [
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

  const userMenuItems: MenuProps['items'] = [
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
        style={{ 
          background: 'rgba(17, 24, 39, 0.7)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255, 255, 255, 0.1)',
        }}
        width={240}
        collapsedWidth={80}
      >
        <div className="logo-container">
          <div className="logo-icon">
            {collapsed ? 'TM' : 'T'}
          </div>
          {!collapsed && (
            <span className="logo-text">Token中转</span>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ 
            background: 'transparent',
            borderRight: 'none',
            padding: '8px',
          }}
          inlineCollapsed={collapsed}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          padding: '0 24px', 
          background: 'rgba(17, 24, 39, 0.7)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', 
          justifyContent: 'flex-end',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          height: 64,
        }}>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
            <div style={{ 
              cursor: 'pointer', 
              display: 'flex', 
              alignItems: 'center', 
              gap: 12,
              padding: '8px 16px',
              borderRadius: '10px',
              background: 'rgba(37, 99, 235, 0.1)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              transition: 'all 0.25s ease',
            }}
            className="user-dropdown"
            >
              <Avatar 
                icon={<UserOutlined />} 
                style={{ 
                  background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                }} 
              />
              <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{user?.username}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ 
          margin: 24, 
          padding: 24, 
          background: 'rgba(17, 24, 39, 0.5)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRadius: 16,
          border: '1px solid rgba(255, 255, 255, 0.1)',
          minHeight: 'calc(100vh - 64px - 48px)',
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
