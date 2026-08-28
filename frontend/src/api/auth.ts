import { post, get } from './request'

// 登录
export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: {
    user_id: string
    username: string
    role: string
  }
}

export const login = (data: LoginParams) => post<LoginResult>('/auth/login', data)

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
