import { useEffect, useRef, useCallback } from 'react'
import { notification } from 'antd'
import { useAuthStore } from '../store/auth'
import { useNotificationStore } from '../store/notification'

export const useNotificationWebSocket = () => {
  const { token } = useAuthStore()
  const { setUnreadCount, addNotification } = useNotificationStore()
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()
  const isMountedRef = useRef(true)

  const connect = useCallback(() => {
    if (!token) return
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/notifications?token=${token}`
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      if (!isMountedRef.current) return
      console.log('[WS] 通知 WebSocket 已连接')
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return
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
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      if (!isMountedRef.current) return
      console.log('[WS] 通知 WebSocket 断开，5秒后重连')
      reconnectTimer.current = setTimeout(() => {
        if (isMountedRef.current) connect()
      }, 5000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [token, setUnreadCount, addNotification])

  useEffect(() => {
    isMountedRef.current = true
    connect()
    
    // 心跳
    const heartbeat = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    return () => {
      isMountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      clearInterval(heartbeat)
      wsRef.current?.close()
    }
  }, [connect])
}
