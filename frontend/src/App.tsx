import LegacyApprovalsRedirect from './components/LegacyApprovalsRedirect'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate, Outlet } from 'react-router-dom'
import { App as AntApp, Spin } from 'antd'
import { useAuthStore } from './store/auth'
import MainLayout from './components/Layout/MainLayout'
import AdminLayout from './pages/admin/AdminLayout'
import { MessageProvider } from './components/MessageProvider'
import { useNotificationWebSocket } from './hooks/useNotificationWebSocket'
import { useSwrData } from './hooks/useSwr'
import { UserInfo } from './api/auth'
import { isAuthSessionCurrent } from './utils/authSession.mjs'
import { defaultAdminPath, hasPermission } from './utils/adminPermissions.mjs'

const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const ApiKeys = lazy(() => import('./pages/ApiKeys'))
const Stats = lazy(() => import('./pages/Stats'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const DepartmentDashboard = lazy(() => import('./pages/admin/DepartmentDashboard'))
const Notifications = lazy(() => import('./pages/Notifications'))
const Settings = lazy(() => import('./pages/Settings'))
const Chat = lazy(() => import('./pages/Chat'))
const Applications = lazy(() => import('./pages/Approvals'))
const ApprovalWorkbench = lazy(() => import('./pages/ApprovalWorkbench'))
const AdminUsers = lazy(() => import('./pages/admin/Users'))
const ProjectsPage = lazy(() => import('./pages/admin/Projects'))
const Budgets = lazy(() => import('./pages/admin/Budgets'))
const Reservations = lazy(() => import('./pages/admin/Reservations'))
const Reconciliation = lazy(() => import('./pages/admin/Reconciliation'))
const AdminChannels = lazy(() => import('./pages/admin/Channels'))
const ChannelForm = lazy(() => import('./pages/admin/ChannelForm'))
const ChannelBindings = lazy(() => import('./pages/admin/ChannelBindings'))
const ChannelQuota = lazy(() => import('./pages/admin/ChannelQuota'))
const AdminModels = lazy(() => import('./pages/admin/Models'))
const AdminModelGroups = lazy(() => import('./pages/admin/ModelGroups'))
const ModelGroupForm = lazy(() => import('./pages/admin/ModelGroupForm'))
const OperationLogs = lazy(() => import('./pages/admin/OperationLogs'))
const LoginLogs = lazy(() => import('./pages/admin/LoginLogs'))
const HealthDashboard = lazy(() => import('./pages/admin/HealthDashboard'))
const Roles = lazy(() => import('./pages/admin/Roles'))
const RouteMonitor = lazy(() => import('./pages/admin/RouteMonitor'))
const AdminApprovals = lazy(() => import('./pages/admin/Approvals'))

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
    if (userData && token && isAuthSessionCurrent(token, useAuthStore.getState().token)) {
      setAuth(token, useAuthStore.getState().refreshToken || '')
      useAuthStore.setState({ user: userData })
    }
  }, [token, userData, setAuth])

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
      const nextPath = defaultAdminPath(user.permissions)
      if ((hasPermission(user.permissions, 'admin:read') || hasPermission(user.permissions, 'department:read')) && window.location.pathname === '/stats') {
        navigate(nextPath, { replace: true })
      }
    }
  }, [token, user, navigate])

  // 关键：user 加载中时保持当前路由
  const homePath = defaultAdminPath(user?.permissions)

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
        <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spin size="large" /></div>}>
        <Routes>
          <Route path="/login" element={!token ? <Login /> : <Navigate to={homePath} />} />
          <Route path="/register" element={!token ? <Register /> : <Navigate to="/stats" />} />
          
          <Route path="/" element={token ? <MainLayout /> : <Navigate to="/login" />}>
            <Route index element={<Navigate to={homePath} />} />
            
            <Route path="stats" element={user && (hasPermission(user.permissions, 'admin:read') || hasPermission(user.permissions, 'department:read')) ? <Navigate to={homePath} /> : <Stats />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="approvals" element={<LegacyApprovalsRedirect />} />
            <Route path="applications" element={<Applications />} />
            <Route path="approval-workbench" element={<ApprovalWorkbench />} />
            <Route path="api-keys" element={<ApiKeys />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
            
            <Route path="admin" element={<AdminLayout><Outlet /></AdminLayout>}>
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="department-dashboard" element={<DepartmentDashboard />} />
              <Route path="approvals" element={<AdminApprovals />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="billing" element={<Navigate to="/admin/billing/budgets" replace />} />
              <Route path="billing/budgets" element={<Budgets />} />
              <Route path="billing/reservations" element={<Reservations />} />
              <Route path="billing/reconciliation" element={<Reconciliation />} />
              <Route path="departments" element={<ProjectsPage departmentsOnly />} />
              <Route path="channels" element={<AdminChannels />} />
              <Route path="health" element={<HealthDashboard />} />
              <Route path="roles" element={<Roles />} />
              <Route path="logs/routes" element={<RouteMonitor />} />
              <Route path="channels/new" element={<ChannelForm />} />
              <Route path="channels/:channelId/edit" element={<ChannelForm />} />
              <Route path="channels/:channelId/bindings" element={<ChannelBindings />} />
              <Route path="channels/:channelId/quota" element={<ChannelQuota />} />
              <Route path="providers" element={<Navigate to="/admin/channels" replace />} />
              <Route path="models" element={<AdminModels />} />
              <Route path="model-groups" element={<AdminModelGroups />} />
              <Route path="model-groups/new" element={<ModelGroupForm />} />
              <Route path="model-groups/:groupId/edit" element={<ModelGroupForm />} />
              <Route path="logs/operations" element={<OperationLogs />} />
              <Route path="logs/logins" element={<LoginLogs />} />
            </Route>
          </Route>
        </Routes>
        </Suspense>
      </MessageProvider>
    </AntApp>
  )
}

const NotificationWebSocketBridge: React.FC = () => {
  useNotificationWebSocket()
  return null
}

export default App
