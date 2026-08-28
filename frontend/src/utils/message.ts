import { App } from 'antd'
import type { MessageInstance } from 'antd/es/message/interface'

// 全局 message 实例容器
// 用于在非组件上下文（如 API 拦截器）中访问 message
let messageInstance: MessageInstance | null = null

export const setMessageInstance = (instance: MessageInstance) => {
  messageInstance = instance
}

export const getMessageInstance = (): MessageInstance => {
  return messageInstance!
}

// 组件中使用此 hook
export const useMessage = () => {
  const { message } = App.useApp()
  return message
}

// 用于 API 拦截器等非组件上下文
export const $message = {
  success: (content: string) => messageInstance?.success(content),
  error: (content: string) => messageInstance?.error(content),
  warning: (content: string) => messageInstance?.warning(content),
  info: (content: string) => messageInstance?.info(content),
  loading: (content: string, duration?: number) => messageInstance?.loading(content, duration),
}
