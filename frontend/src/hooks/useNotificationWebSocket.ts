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
  // useRef 而非 let: React 18 StrictMode 在开发模式下会 mount→unmount→mount，
  // 闭包内的 let 在第二次 effect 里看不到第一次 cleanup 设置的 true。
  const isCancelledRef = useRef(false)

  useEffect(() => {
    if (!token) {
      return
    }

    // 重置取消标志：StrictMode 下 mount→unmount→mount，cleanup 会把
    // isCancelledRef 置 true；如果不重置，第二次 effect 永远 return，
    // WebSocket 永远不会创建。
    isCancelledRef.current = false

    let currentWs: WebSocket | null = null

    const connect = () => {
      if (isCancelledRef.current || !token) return

      // 关闭已有连接
      if (wsRef.current && wsRef.current !== currentWs) {
        try { wsRef.current.close() } catch {}
      }

      const wsUrl = `${getWsBaseUrl()}?token=${token}`
      console.log('[WS] 尝试连接:', wsUrl)
      
      const ws = new WebSocket(wsUrl)
      currentWs = ws
      wsRef.current = ws
      reconnectAttempts.current++

      ws.onopen = () => {
        console.log('[WS] 通知 WebSocket 已连接')
        reconnectAttempts.current = 0
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = undefined
        }
      }

      ws.onmessage = (event) => {
        // 同样检查 ws 是否还是当前 ws：避免被弃用 WS 的 'connected' 帧覆盖 store
        if (wsRef.current !== ws) return
        try {
          const data = JSON.parse(event.data)
          console.log('[WS] 收到消息:', data.type, data)
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
          console.error('[WS] 解析消息失败:', e)
        }
      }

      ws.onclose = (e) => {
        // 同 onerror：依赖 wsRef.current 自身而非会被重置的共享 ref
        if (wsRef.current !== ws) return
        console.log('[WS] 通知 WebSocket 断开 code=' + e.code + ', reason=' + e.reason)
        
        // 如果是正常关闭，不重连
        if (e.code === 1000) {
          console.log('[WS] WebSocket 正常关闭，不重连')
          return
        }
        
        // 非正常关闭，指数退避重连
        const delay = Math.min(5000 * Math.pow(1.5, reconnectAttempts.current - 1), 30000)
        console.log(`[WS] ${delay}ms 后重连 (第 ${reconnectAttempts.current} 次尝试)`)
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
        reconnectTimer.current = setTimeout(connect, delay)
      }

      ws.onerror = (e) => {
        // 检查 ws 自身是否还是当前 ws：StrictMode 下 cleanup 会把 wsRef 清掉
        // 之后才异步触发 onerror，此时共享的 isCancelledRef 已被第二次 effect
        // 重置为 false，旧的 ws 不能依赖共享 ref 来判断自己是否被取消。
        if (wsRef.current !== ws) return
        console.error('[WS] WebSocket 错误:', e)
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
        try { wsRef.current.close(1000, 'Component unmount') } catch {}
        wsRef.current = null
      }
      // 重置：StrictMode 第二次 mount 不应继承前次失败计数
      reconnectAttempts.current = 0
    }
  }, [token])
}
