import { useEffect } from 'react'
import { App } from 'antd'
import { setMessageInstance } from '../utils/message'

// 此组件用于初始化全局 message 实例
// 在 App 组件树中使用一次即可
export const MessageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { message } = App.useApp()

  useEffect(() => {
    setMessageInstance(message)
  }, [message])

  return <>{children}</>
}
