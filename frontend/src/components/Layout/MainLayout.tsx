import { useState, useEffect, useMemo } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Avatar, Dropdown, MenuProps, Badge, Tooltip } from 'antd'
import {
  DashboardOutlined,
  MessageOutlined,
  KeyOutlined,
  BarChartOutlined,
  SettingOutlined,
  TeamOutlined,
  CloudOutlined,
  AppstoreOutlined,
  LogoutOutlined,
  BellOutlined,
  FileSearchOutlined,
  LoginOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../../store/auth'
import { useTheme } from '../../theme'
import NotificationDropdown from '../NotificationDropdown'
import { useNotificationStore } from '../../store/notification'

const { Sider } = Layout

// Layout 常量
const SIDEBAR_WIDTH = 220
const SIDEBAR_COLLAPSED_WIDTH = 64
const HEADER_HEIGHT = 56
const COLLAPSE_STORAGE_KEY = 'token-manager-sidebar-collapsed'

// 根据路由生成页面标题
const getPageTitle = (pathname: string): string => {
  const map: Record<string, string> = {
    '/dashboard': '仪表盘',
    '/api-keys': 'API Key 管理',
    '/chat': 'AI 对话',
    '/stats': '仪表盘',
    '/notifications': '消息通知',
    '/admin/users': '用户管理',
    '/admin/providers': '供应商管理',
    '/admin/models': '模型管理',
    '/admin/model-groups': '模型分组',
    '/admin/logs/operations': '操作日志',
    '/admin/logs/logins': '登录日志',
    '/settings': '个人设置',
  }
  return map[pathname] ?? 'Token Manager'
}

const roleLabel = (role?: string) => {
  if (role === 'admin') return '管理员'
  if (role === 'user') return '普通用户'
  return ''
}

const MainLayout = () => {
  const { theme, setTheme, themeOptions } = useTheme()
  const navigate = useNavigate()

  // 主题菜单项
  const themeMenuItems = useMemo(() => themeOptions.map((option) => ({
    key: option.name,
    label: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 14 }}>{option.icon}</span>
        <span>{option.label}</span>
        {theme === option.name && (
          <span style={{ marginLeft: 'auto', color: '#2563EB' }}>✓</span>
        )}
      </div>
    ),
    onClick: () => setTheme(option.name),
  })), [theme, setTheme, themeOptions])
  const location = useLocation()
  const { token, user, logout } = useAuthStore()
  const { unreadCount } = useNotificationStore()

  // 初始化折叠状态,优先从 localStorage 读取
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSE_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    if (!token) {
      navigate('/login')
    }
  }, [token, navigate])

  // 持久化折叠状态
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed))
    } catch {
      // 忽略存储异常(隐私模式等)
    }
  }, [collapsed])

  const isAdmin = user?.role === 'admin'

  const menuItems: MenuProps['items'] = [
    isAdmin
      ? { key: '/admin/dashboard', icon: <DashboardOutlined />, label: '仪表盘' }
      : { key: '/stats', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: '/notifications', icon: <BellOutlined />, label: '消息通知' },
    { key: '/api-keys', icon: <KeyOutlined />, label: 'API Key' },
    { key: '/chat', icon: <MessageOutlined />, label: 'AI 对话' },
    ...(isAdmin
      ? [
          {
            key: 'admin',
            icon: <AppstoreOutlined />,
            label: '管理后台',
            children: [
              { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
              { key: '/admin/providers', icon: <CloudOutlined />, label: '供应商管理' },
              { key: '/admin/models', icon: <AppstoreOutlined />, label: '模型管理' },
              { key: '/admin/model-groups', icon: <UnorderedListOutlined />, label: '模型分组' },
              { key: '/admin/logs/operations', icon: <FileSearchOutlined />, label: '操作日志' },
              { key: '/admin/logs/logins', icon: <LoginOutlined />, label: '登录日志' },
            ],
          },
        ]
      : []),
    { key: '/settings', icon: <SettingOutlined />, label: '个人设置' },
  ]

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
          <Avatar
            size={36}
            style={{
              background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
              fontSize: 14,
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {user?.username?.charAt(0).toUpperCase() || 'U'}
          </Avatar>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                color: '#F8FAFC',
                fontWeight: 600,
                fontSize: 13,
                whiteSpace: 'nowrap',
              }}
            >
              {user?.username}
            </div>
            <div
              style={{
                color: 'rgba(148, 163, 184, 0.7)',
                fontSize: 11,
                whiteSpace: 'nowrap',
                maxWidth: 160,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {user?.email}
            </div>
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
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

  const pageTitle = getPageTitle(location.pathname)
  const userRoleText = roleLabel(user?.role)

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: 'var(--color-background)',
        overflow: 'hidden',
      }}
    >
      {/* ========== 左侧可折叠菜单 ========== */}
      <Sider
        collapsed={collapsed}
        width={SIDEBAR_WIDTH}
        collapsedWidth={SIDEBAR_COLLAPSED_WIDTH}
        style={{
          background:
            'linear-gradient(180deg, rgba(17, 24, 39, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderRight: '1px solid rgba(255, 255, 255, 0.06)',
          position: 'sticky',
          top: 0,
          height: '100vh',
          flexShrink: 0,
          zIndex: 100,
          overflow: 'hidden',
        }}
      >
        {/* Logo 区 + 折叠按钮 */}
        <div
          style={{
            height: HEADER_HEIGHT,
            padding: collapsed ? '0' : '0 12px 0 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
            gap: 8,
            position: 'relative',
          }}
        >
          {/* Logo */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              overflow: 'hidden',
              minWidth: 0,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontWeight: 700,
                fontSize: 12,
                letterSpacing: 0.5,
                flexShrink: 0,
                boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)',
              }}
              aria-hidden
            >
              TM
            </div>
            {!collapsed && (
              <span
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 700,
                  fontSize: 15,
                  background:
                    'linear-gradient(135deg, #F8FAFC 0%, #94A3B8 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                Token Manager
              </span>
            )}
          </div>

          {/* 折叠按钮(展开态时显示在右侧) */}
          {!collapsed && (
            <Tooltip title="折叠菜单" placement="bottom">
              <button
                type="button"
                aria-label="折叠菜单"
                onClick={() => setCollapsed(true)}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 6,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'rgba(148, 163, 184, 0.75)',
                  background: 'transparent',
                  border: 'none',
                  flexShrink: 0,
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                  e.currentTarget.style.color = '#60A5FA'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'rgba(148, 163, 184, 0.75)'
                }}
              >
                <MenuFoldOutlined style={{ fontSize: 14 }} />
              </button>
            </Tooltip>
          )}
        </div>

        {/* 折叠态的展开按钮(logo 正下方) */}
        {collapsed && (
          <div
            style={{
              padding: '12px 0',
              display: 'flex',
              justifyContent: 'center',
            }}
          >
            <Tooltip title="展开菜单" placement="right">
              <button
                type="button"
                aria-label="展开菜单"
                onClick={() => setCollapsed(false)}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'rgba(148, 163, 184, 0.75)',
                  background: 'transparent',
                  border: 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)'
                  e.currentTarget.style.color = '#60A5FA'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'rgba(148, 163, 184, 0.75)'
                }}
              >
                <MenuUnfoldOutlined style={{ fontSize: 16 }} />
              </button>
            </Tooltip>
          </div>
        )}

        {/* 菜单列表 */}
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={isAdmin ? ['admin'] : []}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{
            background: 'transparent',
            borderRight: 'none',
            padding: '4px 8px',
          }}
          inlineCollapsed={collapsed}
        />
      </Sider>

      {/* ========== 右侧主区域 ========== */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
        }}
      >
        {/* 固定头部 */}
        <header
          style={{
            height: HEADER_HEIGHT,
            padding: '0 20px',
            background: 'rgba(15, 23, 42, 0.9)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexShrink: 0,
            position: 'sticky',
            top: 0,
            zIndex: 99,
          }}
        >
          {/* 左:页面标题 + 在线状态 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            <h1
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: '#F8FAFC',
                fontFamily: "'Space Grotesk', sans-serif",
                margin: 0,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {pageTitle}
            </h1>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 9px',
                borderRadius: 6,
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                flexShrink: 0,
              }}
              aria-label="服务在线"
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: '#10B981',
                  boxShadow: '0 0 6px rgba(16, 185, 129, 0.8)',
                }}
              />
              <span
                style={{
                  color: '#10B981',
                  fontSize: 11,
                  fontWeight: 500,
                  letterSpacing: '0.2px',
                  whiteSpace: 'nowrap',
                }}
              >
                在线
              </span>
            </div>
          </div>

          {/* 右:主题切换 + 通知 + 用户 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            {/* 主题切换 */}
            <Dropdown
              menu={{
                items: themeMenuItems,
                style: {
                  background: 'rgba(17, 24, 39, 0.95)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 12,
                  padding: '8px',
                  minWidth: 160,
                },
              }}
              placement="bottomRight"
              trigger={['click']}
            >
              <Tooltip title="切换主题" placement="bottom">
                <button
                  type="button"
                  aria-label="切换主题"
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    background: 'transparent',
                    border: 'none',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)')
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = 'transparent')
                  }
                >
                  <span style={{ fontSize: 16 }}>
                    {themeOptions.find((t) => t.name === theme)?.icon || '🎨'}
                  </span>
                </button>
              </Tooltip>
            </Dropdown>

            <NotificationDropdown
              trigger={
                <Tooltip title="通知" placement="bottom">
                  <button
                    type="button"
                    aria-label="通知"
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 8,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      background: 'transparent',
                      border: 'none',
                      transition: 'all 0.2s ease',
                      position: 'relative',
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)')
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = 'transparent')
                    }
                  >
                    <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                      <BellOutlined
                        style={{ color: 'rgba(148, 163, 184, 0.85)', fontSize: 16 }}
                      />
                    </Badge>
                  </button>
                </Tooltip>
              }
            />

            {/* 用户信息下拉 */}
            <Dropdown
              menu={{
                items: userMenuItems,
                style: {
                  background: 'rgba(17, 24, 39, 0.95)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 12,
                  padding: '8px',
                  minWidth: 220,
                },
              }}
              placement="bottomRight"
              trigger={['click']}
            >
              <button
                type="button"
                aria-label="用户菜单"
                style={{
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '4px 14px 4px 4px',
                  borderRadius: 22,
                  background: 'transparent',
                  border: 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)')
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = 'transparent')
                }
              >
                <Avatar
                  size={32}
                  style={{
                    background:
                      'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
                    fontSize: 13,
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </Avatar>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    lineHeight: 1.2,
                    textAlign: 'left',
                    minWidth: 0,
                  }}
                >
                  <span
                    style={{
                      color: '#E2E8F0',
                      fontWeight: 600,
                      fontSize: 13,
                      fontFamily: "'DM Sans', sans-serif",
                      whiteSpace: 'nowrap',
                      maxWidth: 140,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {user?.username || '未登录'}
                  </span>
                  {userRoleText && (
                    <span
                      style={{
                        color: 'rgba(148, 163, 184, 0.7)',
                        fontSize: 10,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {userRoleText}
                    </span>
                  )}
                </div>
              </button>
            </Dropdown>
          </div>
        </header>

        {/* 可滚动内容区 */}
        <main
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            padding: 20,
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default MainLayout
