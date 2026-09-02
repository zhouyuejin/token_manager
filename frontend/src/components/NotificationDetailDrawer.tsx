import { useState, useEffect, useRef } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Drawer, Collapse, Button, Tag } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Notification } from '../store/notification'

// 通知类型颜色 / 图标 / 中文名映射。
// 这里复制自 NotificationDropdown.tsx 的 typeConfig 并补上中文 label。
// 文件内自包含、可 export，让后续 Notifications 页面（Task 3）通过 import 复用，
// 避免再造一份独立文件导致样式漂移。
export interface NotificationTypeConfig {
  icon: string
  color: string
  label: string
}

export const NOTIFICATION_TYPE_CONFIG: Record<string, NotificationTypeConfig> = {
  quota_low: { icon: '🔴', color: '#EF4444', label: '额度预警' },
  quota_increase: { icon: '🟢', color: '#22C55E', label: '额度提升' },
  quota_decrease: { icon: '🔵', color: '#3B82F6', label: '额度降低' },
  daily_report: { icon: '🟡', color: '#EAB308', label: '每日报告' },
  system: { icon: '⚪', color: '#94A3B8', label: '系统通知' },
}

const getTypeConfig = (type: string): NotificationTypeConfig =>
  NOTIFICATION_TYPE_CONFIG[type] || NOTIFICATION_TYPE_CONFIG.system

// 把任意 metadata 渲染成可读 JSON：字符串原样、对象格式化、未定义返回 null
const formatMetadata = (value: unknown): string | null => {
  if (value === null || value === undefined) return null
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const hasMetadata = (value: unknown): boolean => {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value as object).length > 0
  return true
}

const formatTime = (val: string | null | undefined): string => {
  if (!val) return '-'
  return dayjs.utc(val).local().format('YYYY-MM-DD HH:mm:ss')
}

export interface NotificationDetailDrawerProps {
  notification: Notification | null
  open: boolean
  onClose: () => void
  onMarkAsRead?: (notifId: string) => Promise<void> | void
  onDelete?: (notifId: string) => Promise<void> | void
}

export default function NotificationDetailDrawer({
  notification,
  open,
  onClose,
  onMarkAsRead,
  onDelete,
}: NotificationDetailDrawerProps) {
  const { token, isDark } = useThemeToken()
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [markLoading, setMarkLoading] = useState(false)
  // 记录已经自动标记过的 notif_id，防止 React StrictMode 在开发态双调用 effect
  // 导致 store.unreadCount 被多扣一次。Promise 失败时会在 catch 中清空，允许重试。
  const lastAutoMarkedIdRef = useRef<string | null>(null)

  // 打开即已读：open → true 且当前通知未读 且 父组件提供 handler 时自动调用。
  useEffect(() => {
    if (!open || !notification || notification.is_read || !onMarkAsRead) return
    if (lastAutoMarkedIdRef.current === notification.notif_id) return
    lastAutoMarkedIdRef.current = notification.notif_id
    void Promise.resolve(onMarkAsRead(notification.notif_id)).catch(() => {
      // 接口失败时清掉 ref，下次打开同一条还能重试
      lastAutoMarkedIdRef.current = null
    })
  }, [open, notification, onMarkAsRead])

  const handleDelete = async () => {
    if (!notification || !onDelete) return
    setDeleteLoading(true)
    try {
      await onDelete(notification.notif_id)
      onClose()
    } catch {
      // 父级 onDelete 失败时保持打开，错误信息由 axios 拦截器统一提示
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleManualMarkAsRead = async () => {
    if (!notification || !onMarkAsRead) return
    setMarkLoading(true)
    try {
      await onMarkAsRead(notification.notif_id)
      lastAutoMarkedIdRef.current = notification.notif_id
    } catch {
      // 父级处理错误提示
    } finally {
      setMarkLoading(false)
    }
  }

  const typeConf = notification ? getTypeConfig(notification.type) : null
  const metadataJson = notification ? formatMetadata(notification.metadata) : null
  const showMetadataCollapse = notification ? hasMetadata(notification.metadata) : false

  return (
    <Drawer
      title={
        <span style={{ color: token.colorText, fontSize: 15, fontWeight: 600 }}>通知详情</span>
      }
      width={480}
      placement="right"
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        wrapper: { background: token.colorBgElevated },
        body: { padding: '20px 24px 28px' },
        header: {
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: 12,
        },
      }}
      style={{ backdropFilter: 'blur(20px)' }}
    >
      {notification ? (
        <div>
          {/* 类型 Tag — 顶部右上角 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              marginBottom: 12,
            }}
          >
            {typeConf && (
              <Tag
                style={{
                  background: `${typeConf.color}22`,
                  borderColor: `${typeConf.color}66`,
                  color: typeConf.color,
                  fontWeight: 500,
                  padding: '2px 10px',
                  borderRadius: 6,
                  fontSize: 12,
                  lineHeight: '20px',
                  margin: 0,
                }}
              >
                <span style={{ marginRight: 4 }}>{typeConf.icon}</span>
                {typeConf.label}
              </Tag>
            )}
          </div>

          {/* 标题 + 未读小圆点 */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 10,
              marginBottom: 8,
            }}
          >
            {!notification.is_read && (
              <span
                aria-label="未读"
                style={{
                  display: 'inline-block',
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: '#3B82F6',
                  marginTop: 9,
                  flexShrink: 0,
                  boxShadow: '0 0 6px rgba(59, 130, 246, 0.6)',
                }}
              />
            )}
            <h2
              style={{
                color: token.colorText,
                fontSize: 18,
                fontWeight: 600,
                lineHeight: 1.5,
                margin: 0,
                wordBreak: 'break-word',
                flex: 1,
              }}
            >
              {notification.title}
            </h2>
          </div>

          {/* 元数据行：创建时间 · 已读 / 未读 */}
          <div
            style={{
              color: '#94A3B8',
              fontSize: 12,
              marginBottom: 16,
              fontFamily: "'Space Grotesk', monospace",
            }}
          >
            创建于 {formatTime(notification.created_at)}
            {' · '}
            {notification.is_read
              ? notification.read_at
                ? `已于 ${formatTime(notification.read_at)} 已读`
                : '已读'
              : '未读'}
          </div>

          {/* 内容 */}
          <div
            style={{
              background: token.colorBgContainer,
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: 8,
              padding: '12px 14px',
              color: token.colorText,
              fontSize: 14,
              lineHeight: 1.7,
              marginBottom: 16,
              maxHeight: 280,
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {notification.content ? (
              notification.content
            ) : (
              <span style={{ color: '#94A3B8' }}>（无内容）</span>
            )}
          </div>

          {/* 附加数据折叠面板（默认展开） */}
          {showMetadataCollapse && metadataJson !== null && (
            <Collapse
              defaultActiveKey={['metadata']}
              style={{
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: 8,
                marginBottom: 16,
              }}
              items={[
                {
                  key: 'metadata',
                  label: (
                    <span style={{ color: '#94A3B8', fontSize: 13, fontWeight: 500 }}>
                      附加数据
                    </span>
                  ),
                  children: (
                    <div
                      style={{
                        background: token.colorBgContainer,
                        borderRadius: 6,
                        padding: '8px 12px',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        maxHeight: 240,
                        overflowY: 'auto',
                      }}
                    >
                      <pre
                        style={{
                          color: '#94A3B8',
                          fontFamily: "'Space Grotesk', monospace",
                          fontSize: 11,
                          margin: 0,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                          lineHeight: 1.5,
                        }}
                      >
                        {metadataJson}
                      </pre>
                    </div>
                  ),
                },
              ]}
            />
          )}

          {/* 底部操作区：删除（右上）+ 标记已读（底部） */}
          {(onDelete || (!notification.is_read && onMarkAsRead)) && (
            <div
              style={{
                marginTop: 8,
                paddingTop: 16,
                borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: 8,
              }}
            >
              {onDelete && (
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  loading={deleteLoading}
                  onClick={handleDelete}
                  style={{ padding: '4px 12px' }}
                >
                  删除
                </Button>
              )}
              {!notification.is_read && onMarkAsRead && (
                <Button
                  type="primary"
                  loading={markLoading}
                  onClick={handleManualMarkAsRead}
                  style={{ background: '#3B82F6', borderColor: '#3B82F6' }}
                >
                  标记已读
                </Button>
              )}
            </div>
          )}
        </div>
      ) : null}
    </Drawer>
  )
}
