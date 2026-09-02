import { post, get } from './request'

// 登录
export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  refresh_token: string
  expires_in: number  // access_token 剩余秒数
}

export const login = (data: LoginParams) => post<LoginResult>('/auth/login', data)

// refresh
export interface RefreshParams { refresh_token: string }
export interface RefreshResult extends LoginResult {}

export const refresh = (data: RefreshParams) => post<RefreshResult>('/auth/refresh', data)

// 登出（撤销服务端 refresh_token；前端同时丢弃 access_token）
export const logoutServer = (refresh_token?: string) =>
  post<void>('/auth/logout', refresh_token ? { refresh_token } : {})

// 注册
export interface RegisterParams {
  username: string
  email: string
  password: string
}

export const register = (data: RegisterParams) => post('/auth/register', data)

// 获取当前用户
export interface UserInfo {
  user_id: string
  username: string
  email: string
  role: string
  status: string
  quota: number
  quota_used: number
  quota_remain: number
  created_at: string
}

export const getCurrentUser = () => get<UserInfo>('/users/me')
