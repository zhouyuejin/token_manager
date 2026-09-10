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
import ChannelBindings from './pages/admin/ChannelBindings'
import AdminModels from './pages/admin/Models'
import AdminModelGroups from './pages/admin/ModelGroups'
import AdminLayout from './pages/admin/AdminLayout'
import OperationLogs from './pages/admin/OperationLogs'
import LoginLogs from './pages/admin/LoginLogs'
import { MessageProvider } from './components/MessageProvider'
import { useNotificationWebSocket } from './hooks/useNotificationWebSocket'

function App() {
  const { token, checkAuth, user } = useAuthStore()
  const navigate = useNavigate()
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (token) {
      Promise.resolve(checkAuth()).finally(() => {
        if (!cancelled) setAuthChecked(true)
      })
    } else {
      setAuthChecked(true)
    }
    return () => { cancelled = true }
  }, [token, checkAuth])

  useEffect(() => {
    if (token && user) {
      if (user.role === 'admin' && window.location.pathname === '/stats') {
        navigate('/admin/dashboard', { replace: true })
      }
    }
  }, [token, user, navigate])

  const isAdmin = user?.role === 'admin'

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
            
            <Route path="admin" element={isAdmin ? <AdminLayout><Outlet /></AdminLayout> : <Navigate to="/stats" />}>
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="channels" element={<AdminChannels />} />
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
