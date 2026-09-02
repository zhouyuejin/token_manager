import { useEffect, useRef } from 'react'
import { notification } from 'antd'
import { useAuthStore } from '../store/auth'
import { useNotificationStore } from '../store/notification'

// 开发环境直连后端，生产环境通过 nginx
const getWsBaseUrl = () => {
  const isDev = import.meta.env.DEV
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  
  if (isDev) {
    // 开发环境直连后端 8000 端口，绕过 Vite 代理
    return `ws://localhost:8000/ws/notifications`
  }
  // 生产环境通过 nginx 反向代理
  return `${protocol}//${window.location.host}/ws/notifications`
}

export const useNotificationWebSocket = () => {
  const token = useAuthStore((s) => s.token)
  const setUnreadCount = useNotificationStore((s) => s.setUnreadCount)
  const addNotification = useNotificationStore((s) => s.addNotification)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const reconnectAttempts = useRef(0)
  const isCancelledRef = useRef(false)

  useEffect(() => {
    if (!token) {
      return
    }

    isCancelledRef.current = false

    let currentWs: WebSocket | null = null

    const connect = () => {
      if (isCancelledRef.current || !token) return

      // 关闭已有连接
      if (wsRef.current && wsRef.current !== currentWs) {
        try { wsRef.current.close() } catch {}
      }

      const wsUrl = `${getWsBaseUrl()}?token=${token}`
      
      const ws = new WebSocket(wsUrl)
      currentWs = ws
      wsRef.current = ws
      reconnectAttempts.current++

      ws.onopen = () => {
        reconnectAttempts.current = 0
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = undefined
        }
      }

      ws.onmessage = (event) => {
        if (wsRef.current !== ws) return
        try {
          const data = JSON.parse(event.data)
          switch (data.type) {
            case 'connected':
              setUnreadCount(data.unread_count)
              break
            case 'new_notification':
              addNotification(data.notif)
              setUnreadCount((prev: number) => prev + 1)
              notification.info({
                message: data.notif.title,
                description: data.notif.content,
                duration: 5,
                placement: 'topRight',
              })
              break
            case 'pong':
              break
          }
        } catch (e) {
          // 解析消息失败，忽略
        }
      }

      ws.onclose = (e) => {
        if (wsRef.current !== ws) return
        
        // 如果是正常关闭，不重连
        if (e.code === 1000) {
          return
        }
        
        // 非正常关闭，指数退避重连
        const delay = Math.min(5000 * Math.pow(1.5, reconnectAttempts.current - 1), 30000)
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
        reconnectTimer.current = setTimeout(connect, delay)
      }

      ws.onerror = () => {
        // WebSocket 错误由 onclose 处理
        if (wsRef.current !== ws) return
      }
    }

    connect()

    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    return () => {
      isCancelledRef.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      clearInterval(heartbeat)
      if (wsRef.current) {
        const ws = wsRef.current
        // 检查连接状态，避免在连接过程中关闭导致浏览器警告
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          try { ws.close(1000, 'Component unmount') } catch {}
        }
        wsRef.current = null
      }
      reconnectAttempts.current = 0
    }
  }, [token])
}
