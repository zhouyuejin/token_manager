import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
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
import AdminProviders from './pages/admin/Providers'
import AdminModels from './pages/admin/Models'
import AdminModelGroups from './pages/admin/ModelGroups'
import OperationLogs from './pages/admin/OperationLogs'
import LoginLogs from './pages/admin/LoginLogs'
import { MessageProvider } from './components/MessageProvider'
import { useNotificationWebSocket } from './hooks/useNotificationWebSocket'

function App() {
  const { token, checkAuth, user } = useAuthStore()
  const navigate = useNavigate()
  // 区分"还没拉过用户信息"和"用户已加载但未必为管理员"，
  // 避免刷新时因 user 尚未回填导致基于角色的路由提前误判并跳转。
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (token) {
      // 拉取失败也会进入 finally，避免一直卡在 loading。
      Promise.resolve(checkAuth()).finally(() => {
        if (!cancelled) setAuthChecked(true)
      })
    } else {
      setAuthChecked(true)
    }
    return () => {
      cancelled = true
    }
  }, [token, checkAuth])

  // 登录后根据角色重定向
  useEffect(() => {
    if (token && user) {
      // 如果是管理员且当前在 /stats，重定向到管理员仪表盘
      if (user.role === 'admin' && window.location.pathname === '/stats') {
        navigate('/admin/dashboard', { replace: true })
      }
    }
  }, [token, user, navigate])

  // 判断是否为管理员
  const isAdmin = user?.role === 'admin'

  // 持有 token 但还未完成 checkAuth 时，避免基于角色的路由判断把页面误跳走。
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
          {/* 公开路由 */}
          <Route path="/login" element={!token ? <Login /> : <Navigate to={isAdmin ? "/admin/dashboard" : "/stats"} />} />
          <Route path="/register" element={!token ? <Register /> : <Navigate to="/stats" />} />
          
          {/* 受保护路由 */}
          <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" />}>
            <Route index element={<Navigate to={isAdmin ? "/admin/dashboard" : "/stats"} />} />
            
            {/* 普通用户路由 */}
            <Route path="stats" element={isAdmin ? <Navigate to="/admin/dashboard" /> : <Stats />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="api-keys" element={<ApiKeys />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
            
            {/* 管理员专属路由 */}
            <Route path="admin/dashboard" element={isAdmin ? <AdminDashboard /> : <Navigate to="/stats" />} />
            <Route path="admin/users" element={isAdmin ? <AdminUsers /> : <Navigate to="/stats" />} />
            <Route path="admin/providers" element={isAdmin ? <AdminProviders /> : <Navigate to="/stats" />} />
            <Route path="admin/models" element={isAdmin ? <AdminModels /> : <Navigate to="/stats" />} />
            <Route path="admin/model-groups" element={isAdmin ? <AdminModelGroups /> : <Navigate to="/stats" />} />
            <Route path="admin/logs/operations" element={isAdmin ? <OperationLogs /> : <Navigate to="/stats" />} />
            <Route path="admin/logs/logins" element={isAdmin ? <LoginLogs /> : <Navigate to="/stats" />} />
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
