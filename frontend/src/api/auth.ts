import { post, get } from './request'
import { hashPassword } from '../utils/crypto'

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

/**
 * 登录 - 密码在前端进行哈希后再传输
 */
export async function login(data: LoginParams): Promise<LoginResult> {
  const hashedPassword = await hashPassword(data.password)
  return post<LoginResult>('/auth/login', {
    username: data.username,
    password: hashedPassword
  })
}

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

/**
 * 注册 - 密码在前端进行哈希后再传输
 */
export async function register(data: RegisterParams): Promise<void> {
  const hashedPassword = await hashPassword(data.password)
  await post('/auth/register', {
    username: data.username,
    email: data.email,
    password: hashedPassword
  })
}

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
