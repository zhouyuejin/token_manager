import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/auth'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ApiKeys from './pages/ApiKeys'
import Stats from './pages/Stats'
import Settings from './pages/Settings'
import AdminUsers from './pages/admin/Users'
import AdminProviders from './pages/admin/Providers'
import AdminModels from './pages/admin/Models'

function App() {
  const { token, checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  return (
    <Routes>
      {/* 公开路由 */}
      <Route path="/login" element={!token ? <Login /> : <Navigate to="/dashboard" />} />
      <Route path="/register" element={!token ? <Register /> : <Navigate to="/dashboard" />} />
      
      {/* 受保护路由 */}
      <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" />}>
        <Route index element={<Navigate to="/dashboard" />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="api-keys" element={<ApiKeys />} />
        <Route path="stats" element={<Stats />} />
        <Route path="settings" element={<Settings />} />
        
        {/* 管理员路由 */}
        <Route path="admin/users" element={<AdminUsers />} />
        <Route path="admin/providers" element={<AdminProviders />} />
        <Route path="admin/models" element={<AdminModels />} />
      </Route>
    </Routes>
  )
}

export default App
