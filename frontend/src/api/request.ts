import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { $message } from '../utils/message'
import { useAuthStore } from '../store/auth'
import { refresh as refreshApi } from './auth'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 标记已重试的请求，避免 401 → refresh → 401 死循环
type RetryableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

// 单例 in-flight refresh：并发 401 只触发一次 /auth/refresh
let refreshInFlight: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    const store = useAuthStore.getState()
    const rt = store.refreshToken
    if (!rt) throw new Error('no refresh_token')
    refreshInFlight = (async () => {
      // 一定要用裸 axios，绕开 request 实例自身的拦截器
      const res = await axios.post(
        '/api/v1/auth/refresh',
        { refresh_token: rt },
        { timeout: 15000 },
      )
      const { access_token, refresh_token } = res.data
      store.setAuth(access_token, refresh_token)
      return access_token
    })()
  }
  try {
    return await refreshInFlight
  } finally {
    // 不论成败都清空 in-flight，让下次 401 能重新触发
    refreshInFlight = null
  }
}

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const res = response.data
    if (response.config.url === '/auth/login') return res
    if (res.detail) {
      $message.error(res.detail)
      return Promise.reject(new Error(res.detail))
    }
    if (res.code !== undefined && res.code !== 0) {
      $message.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res.data ?? res
  },
  async (error: AxiosError) => {
    const status = error.response?.status
    const config = error.config as RetryableConfig | undefined

    // 401：尝试 refresh + 重试
    if (status === 401 && config && !config._retried) {
      // /auth/refresh 自身 401 → refresh_token 也失效了，直接登出
      if (config.url === '/auth/refresh') {
        await useAuthStore.getState().logout()
        return Promise.reject(error)
      }
      try {
        const newAccess = await refreshAccessToken()
        config._retried = true
        config.headers = config.headers ?? ({} as any)
        config.headers.Authorization = `Bearer ${newAccess}`
        return request.request(config)
      } catch {
        await useAuthStore.getState().logout()
        $message.error('登录已过期，请重新登录')
        return Promise.reject(error)
      }
    }

    // 已经是重试后的 401 → 直接登出
    if (status === 401) {
      await useAuthStore.getState().logout()
      $message.error('登录已过期，请重新登录')
      return Promise.reject(error)
    }

    if (status === 403) {
      $message.error('没有权限')
    } else if (status === 429) {
      $message.error('请求过于频繁，请稍后重试')
    } else if (error.response?.data) {
      const data = error.response.data as { detail?: string }
      $message.error(data.detail || error.message || '网络错误')
    } else {
      $message.error(error.message || '网络错误')
    }
    return Promise.reject(error)
  },
)

export default request

export const get = <T = any>(url: string, config?: AxiosRequestConfig) =>
  request.get<any, T>(url, config)

export const post = <T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
  request.post<any, T>(url, data, config)

export const put = <T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
  request.put<any, T>(url, data, config)

export const del = <T = any>(url: string, config?: AxiosRequestConfig) =>
  request.delete<any, T>(url, config)
