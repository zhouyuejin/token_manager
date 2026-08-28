import { useState, useEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, MenuProps, Badge } from 'antd'
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
  BellOutlined,

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
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Avatar size={32} style={{ background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)' }}>
            {user?.username?.charAt(0).toUpperCase() || 'U'}
          </Avatar>
          <div>
            <div style={{ color: '#F8FAFC', fontWeight: 600, fontSize: 13 }}>{user?.username}</div>
            <div style={{ color: 'rgba(148, 163, 184, 0.7)', fontSize: 11 }}>{user?.email}</div>
          </div>
        </div>
      ),
      disabled: true,
    },
    {
      type: 'divider',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '个人设置',
      onClick: () => navigate('/settings'),
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
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
          background: 'linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255, 255, 255, 0.06)',
        }}
        width={220}
        collapsedWidth={72}
      >
        <div className="logo-container" style={{
          padding: collapsed ? '16px 8px' : '16px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 12,
          height: 56,
        }}>
          <div className="logo-icon" style={{
            width: 36,
            height: 36,
            background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
            borderRadius: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 700,
            fontSize: 14,
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
          }}>
            {collapsed ? 'TM' : 'T'}
          </div>
          {!collapsed && (
            <span className="logo-text" style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 16,
              background: 'linear-gradient(135deg, #F8FAFC 0%, #94A3B8 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              whiteSpace: 'nowrap',
            }}>
              Token中转
            </span>
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
            padding: '12px 8px',
          }}
          inlineCollapsed={collapsed}
        />
      </Sider>
      <Layout>
        <Header style={{ 
          padding: '0 20px', 
          background: 'rgba(15, 23, 42, 0.9)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          display: 'flex', 
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          height: 48,
          lineHeight: '48px',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <div style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: '#10B981',
              boxShadow: '0 0 8px rgba(16, 185, 129, 0.8)',
            }} />
            <span style={{
              color: 'rgba(148, 163, 184, 0.8)',
              fontSize: 12,
              fontFamily: "'DM Sans', sans-serif",
              letterSpacing: '0.3px',
            }}>
              Token Manager
            </span>
          </div>
          
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
          }}>
            {/* 通知按钮 */}
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              position: 'relative',
            }}>
              <Badge count={3} size="small" offset={[-2, 2]}>
                <BellOutlined style={{ color: 'rgba(148, 163, 184, 0.8)', fontSize: 14 }} />
              </Badge>
            </div>
          
            {/* 用户信息 */}
            <Dropdown 
              menu={{ 
                items: userMenuItems,
                style: {
                  background: 'rgba(17, 24, 39, 0.95)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 12,
                  padding: '8px',
                }
              }} 
              placement="bottomRight" 
              trigger={['click']}
            >
              <div style={{ 
                cursor: 'pointer', 
                display: 'flex', 
                alignItems: 'center', 
                gap: 8,
                padding: '4px 10px 4px 4px',
                borderRadius: 8,
                background: 'rgba(37, 99, 235, 0.12)',
                border: '1px solid rgba(37, 99, 235, 0.2)',
                transition: 'all 0.2s ease',
              }}>
                <Avatar 
                  size={26}
                  style={{ 
                    background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </Avatar>
                <span style={{ 
                  color: '#E2E8F0', 
                  fontWeight: 500, 
                  fontSize: 12,
                  fontFamily: "'DM Sans', sans-serif",
                }}>
                  {user?.username}
                </span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ 
          padding: 20, 
          minHeight: 0,
          overflow: 'auto',
          background: 'transparent',
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
