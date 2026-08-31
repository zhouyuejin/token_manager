import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import ApiKeys from './pages/ApiKeys'
import Stats from './pages/Stats'
import Settings from './pages/Settings'
import Chat from './pages/Chat'
import AdminUsers from './pages/admin/Users'
import AdminProviders from './pages/admin/Providers'
import AdminModels from './pages/admin/Models'
import AdminModelGroups from './pages/admin/ModelGroups'
import OperationLogs from './pages/admin/OperationLogs'
import LoginLogs from './pages/admin/LoginLogs'

function App() {
  const { token, checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={!token ? <Login /> : <Navigate to="/stats" />} />
      <Route path="/register" element={!token ? <Register /> : <Navigate to="/stats" />} />
      
      {/* 受保护路由 */}
      <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" />}>
        <Route index element={<Navigate to="/stats" />} />
        <Route path="stats" element={<Stats />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="chat" element={<Chat />} />
        <Route path="settings" element={<Settings />} />
        
        {/* 管理员路由 */}
        <Route path="admin/users" element={<AdminUsers />} />
        <Route path="admin/providers" element={<AdminProviders />} />
        <Route path="admin/models" element={<AdminModels />} />
        <Route path="admin/model-groups" element={<AdminModelGroups />} />
        <Route path="admin/logs/operations" element={<OperationLogs />} />
        <Route path="admin/logs/logins" element={<LoginLogs />} />
      </Route>
    </Routes>
  )
}

export default App
