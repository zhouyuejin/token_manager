import axios, { AxiosError, AxiosRequestConfig } from 'axios'
import { $message } from '../utils/message'
import { useAuthStore } from '../store/auth'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const res = response.data
    // 登录接口 (/auth/login) 返回的是 OAuth2 Token 格式，没有 code 字段
    if (response.config.url === '/auth/login') {
      return res
    }
    // 检查是否有错误响应格式 {detail: "..."}
    if (res.detail) {
      $message.error(res.detail)
      return Promise.reject(new Error(res.detail))
    }
    // 检查是否有 code 字段且不为 0
    if (res.code !== undefined && res.code !== 0) {
      $message.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    // 成功响应直接返回数据
    return res.data ?? res
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      $message.error('登录已过期，请重新登录')
    } else if (error.response?.status === 403) {
      $message.error('没有权限')
    } else if (error.response?.status === 429) {
      $message.error('请求过于频繁，请稍后重试')
    } else if (error.response?.data) {
      const data = error.response.data as any
      $message.error(data.detail || error.message || '网络错误')
    } else {
      $message.error(error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

export default request

// 封装GET/POST/PUT/DELETE
export const get = <T = any>(url: string, config?: AxiosRequestConfig) =>
  request.get<any, T>(url, config)

export const post = <T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
  request.post<any, T>(url, data, config)

export const put = <T = any>(url: string, data?: any, config?: AxiosRequestConfig) =>
  request.put<any, T>(url, data, config)

export const del = <T = any>(url: string, config?: AxiosRequestConfig) =>
  request.delete<any, T>(url, config)
