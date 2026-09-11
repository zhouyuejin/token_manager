import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate, Outlet } from 'react-router-dom'
import { App as AntApp, Spin } from 'antd'
import { useAuthStore } from './store/auth'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import ApiKeys from './pages/ApiKeys'
import Stats from './pages/Stats'
import AdminDashboard from './pages/AdminDashboard'
import Notifications from './pages/Notifications'
import Settings from './pages/Settings'
import Chat from './pages/Chat'
import AdminUsers from './pages/admin/Users'
import AdminChannels from './pages/admin/Channels'
import ChannelForm from './pages/admin/ChannelForm'
import ChannelBindings from './pages/admin/ChannelBindings'
import AdminModels from './pages/admin/Models'
import AdminModelGroups from './pages/admin/ModelGroups'
import AdminLayout from './pages/admin/AdminLayout'
import OperationLogs from './pages/admin/OperationLogs'
import LoginLogs from './pages/admin/LoginLogs'
import { MessageProvider } from './components/MessageProvider'
import { useNotificationWebSocket } from './hooks/useNotificationWebSocket'
import { useSwrData } from './hooks/useSwr'
import { UserInfo } from './api/auth'

function App() {
  const { token, checkAuth, user, setAuth } = useAuthStore()
  const navigate = useNavigate()
  const [authChecked, setAuthChecked] = useState(false)

  // 使用 SWR 获取用户信息，自动缓存和去重
  const { data: userData, error: userError } = useSwrData<UserInfo>(
    token ? '/users/me' : null,
    { revalidateOnFocus: false }
  )

  // 同步 SWR 数据到 store
  useEffect(() => {
    if (userData) {
      setAuth(token!, useAuthStore.getState().refreshToken || '')
      useAuthStore.setState({ user: userData })
    }
  }, [userData])

  // 处理认证状态 - 只有 user 加载完成或 token 缺失时才标记完成
  useEffect(() => {
    if (!token) {
      setAuthChecked(true)
    } else if (userData || userError) {
      setAuthChecked(true)
    }
  }, [token, userData, userError])

  // 修复：只在 user 完全加载后才进行角色判断重定向
  useEffect(() => {
    if (token && user) {
      if (user.role === 'admin' && window.location.pathname === '/stats') {
        navigate('/admin/dashboard', { replace: true })
      }
    }
  }, [token, user, navigate])

  // 关键：user 加载中时保持当前路由
  const isUserLoaded = !!user
  const isAdmin = isUserLoaded && user?.role === 'admin'

  if (token && !authChecked) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <AntApp>
      <MessageProvider>
        {token && <NotificationWebSocketBridge />}
        <Routes>
          <Route path="/login" element={!token ? <Login /> : <Navigate to={isAdmin ? "/admin/dashboard" : "/stats"} />} />
          <Route path="/register" element={!token ? <Register /> : <Navigate to="/stats" />} />
          
          <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" />}>
            <Route index element={<Navigate to={isAdmin ? "/admin/dashboard" : "/stats"} />} />
            
            <Route path="stats" element={isAdmin ? <Navigate to="/admin/dashboard" /> : <Stats />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="api-keys" element={<ApiKeys />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
            
            {/* 
              修复：admin 路由判断逻辑
              - user 未加载: 保持当前路由，不重定向
              - isAdmin: 允许访问 admin 页面
              - 其他情况: 重定向到 /stats
            */}
            <Route path="admin" element={
              !isUserLoaded 
                ? <AdminLayout><Outlet /></AdminLayout>
                : isAdmin 
                  ? <AdminLayout><Outlet /></AdminLayout>
                  : <Navigate to="/stats" />
            }>
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="channels" element={<AdminChannels />} />
              <Route path="channels/new" element={<ChannelForm />} />
              <Route path="channels/:channelId/edit" element={<ChannelForm />} />
              <Route path="channels/:channelId/bindings" element={<ChannelBindings />} />
              <Route path="providers" element={<Navigate to="/admin/channels" replace />} />
              <Route path="models" element={<AdminModels />} />
              <Route path="model-groups" element={<AdminModelGroups />} />
              <Route path="logs/operations" element={<OperationLogs />} />
              <Route path="logs/logins" element={<LoginLogs />} />
            </Route>
          </Route>
        </Routes>
      </MessageProvider>
    </AntApp>
  )
}

const NotificationWebSocketBridge: React.FC = () => {
  useNotificationWebSocket()
  return null
}

export default App
