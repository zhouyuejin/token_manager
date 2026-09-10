import useSWR, { SWRConfiguration, KeyedMutator } from 'swr'
import { get } from '../api/request'

// 全局 fetcher
export const fetcher = <T>(url: string): Promise<T> => get<T>(url)

// 默认配置
export const swrConfig: SWRConfiguration = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  dedupingInterval: 5000,
  shouldRetryOnError: false,
}

// 通用 useSWR hook - 简单 URL
export function useSwrData<T>(url: string | null, config?: SWRConfiguration) {
  return useSWR<T>(url, fetcher, { ...swrConfig, ...config })
}

// 带参数的 SWR hook - 用于需要动态参数的请求
export function useSwrDataWithParams<T>(url: string | null, params: Record<string, any> | null, config?: SWRConfiguration) {
  // 构建带参数的 URL
  const fullUrl = url && params
    ? `${url}?${new URLSearchParams(params).toString()}`
    : url
  
  return useSWR<T>(fullUrl, fetcher, { ...swrConfig, ...config })
}
