import { useState, useEffect, useRef, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Card,
  List,
  Tag,
  Button,
  Space,
  Input,
  Select,
  Pagination,
  Empty,
  Popconfirm,
  Alert,
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  InboxOutlined,
  EyeOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { useNotificationStore, Notification } from '../store/notification'
import {
  getNotifications,
  markAsRead,
  markAllAsRead,
  deleteNotification,
  deleteReadNotifications,
} from '../api/notifications'
import NotificationDetailDrawer, {
  NOTIFICATION_TYPE_CONFIG,
} from '../components/NotificationDetailDrawer'
import { useMessage } from '../utils/message'

// 类型筛选下拉选项（复用 Task 2 的 NOTIFICATION_TYPE_CONFIG）
const TYPE_FILTER_OPTIONS: { label: string; value: string }[] = [
  { label: '全部类型', value: '' },
  ...Object.entries(NOTIFICATION_TYPE_CONFIG).map(([key, cfg]) => ({
    label: `${cfg.icon} ${cfg.label}`,
    value: key,
  })),
]

const PAGE_SIZE_OPTIONS = [10, 20, 50]

// 与 OperationLogs 一致的绝对时间格式（计划 Global Constraints 要求全站统一）
const formatAbsoluteTime = (val: string | null | undefined): string => {
  if (!val) return '-'
  return dayjs.utc(val).local().format('YYYY-MM-DD HH:mm:ss')
}

const getTypeConfig = (type: string) =>
  NOTIFICATION_TYPE_CONFIG[type] ?? NOTIFICATION_TYPE_CONFIG.system

const NotificationsPage = () => {
  // Task 4 将挂载 /notifications 路由；这里直接消费 ?notif= 参数实现"点击下拉某条 → 自动打开详情"
  const [searchParams, setSearchParams] = useSearchParams()
  const focusId = searchParams.get('notif')

  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [type, setType] = useState<string>('')
  const [keyword, setKeyword] = useState('')

  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [selectedNotif, setSelectedNotif] = useState<Notification | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const [clearOpen, setClearOpen] = useState(false)

  const message = useMessage()

  const {
    notifications: storeNotifications,
    replaceNotifications,
    markAsRead: markAsReadStore,
    markAllAsRead: markAllAsReadStore,
    removeNotification,
    clearRead,
  } = useNotificationStore()

  // 记录最近一次 fetch 返回的首条通知 id，用于探测 WS 推送进来的新条目
  const lastFetchedFirstIdRef = useRef<string | null>(null)

  const refreshNow = async () => {
    setLoading(true)
    try {
      const result = await getNotifications({
        page,
        page_size: pageSize,
        type: type || undefined,
      })
      replaceNotifications(result.items, result.unread_count)
      setTotal(result.total)
      lastFetchedFirstIdRef.current = result.items[0]?.notif_id ?? null
      // 重新拉取后重置 banner 的 dismiss 状态，给用户一个干净的"已处理"反馈
      setBannerDismissed(false)
    } catch (err) {
      console.error('刷新通知失败:', err)
      message.error('刷新失败')
    } finally {
      setLoading(false)
    }
  }

  // page / pageSize / type 任一变化都会重新触发
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getNotifications({
      page,
      page_size: pageSize,
      type: type || undefined,
    })
      .then((result) => {
        if (cancelled) return
        replaceNotifications(result.items, result.unread_count)
        setTotal(result.total)
        lastFetchedFirstIdRef.current = result.items[0]?.notif_id ?? null
        setBannerDismissed(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        console.error('加载通知失败:', err)
        message.error('加载通知失败')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [page, pageSize, type, replaceNotifications, message])

  // 计算自上次 fetch 后，store 头部新增了几条 WS 推送的通知
  const newSinceLastFetch = useMemo(() => {
    const lastId = lastFetchedFirstIdRef.current
    if (!lastId) return 0
    if (!storeNotifications.some((n) => n.notif_id === lastId)) return 0
    let count = 0
    for (const n of storeNotifications) {
      if (n.notif_id === lastId) break
      count++
    }
    return count
  }, [storeNotifications])

  // 解析 ?notif= URL 参数：命中 store 则打开 drawer，未命中不静默翻页，仅清掉 query
  useEffect(() => {
    if (!focusId || storeNotifications.length === 0) return
    const target = storeNotifications.find((n) => n.notif_id === focusId)
    if (target) {
      setSelectedNotif(target)
      setDrawerOpen(true)
    }
    setSearchParams({}, { replace: true })
  }, [focusId, storeNotifications, setSearchParams])

  // 让 drawer 始终展示最新 store 数据：标记已读 / WS 更新 / 字段变更都即时同步
  // 若该通知已被删除（store 中找不到），自动关闭 drawer
  useEffect(() => {
    if (!selectedNotif) return
    const fresh = storeNotifications.find((n) => n.notif_id === selectedNotif.notif_id)
    if (!fresh) {
      setDrawerOpen(false)
      setSelectedNotif(null)
      return
    }
    if (fresh !== selectedNotif) setSelectedNotif(fresh)
  }, [storeNotifications, selectedNotif])

  // 关键词搜索：前端按 title 模糊匹配，不影响分页与 total
  const filteredNotifications = useMemo(() => {
    const k = keyword.trim().toLowerCase()
    if (!k) return storeNotifications
    return storeNotifications.filter((n) => n.title.toLowerCase().includes(k))
  }, [storeNotifications, keyword])

  const openDrawer = (notif: Notification) => {
    setSelectedNotif(notif)
    setDrawerOpen(true)
  }

  const closeDrawer = () => {
    setDrawerOpen(false)
    setSelectedNotif(null)
  }

  const handleMarkAllAsRead = async () => {
    try {
      await markAllAsRead()
      markAllAsReadStore()
      message.success('已将全部通知标记为已读')
    } catch (err) {
      console.error('全部已读失败:', err)
    }
  }

  const handleClearRead = async () => {
    try {
      const result = await deleteReadNotifications()
      clearRead()
      const removed = result.deleted ?? 0
      setTotal((prev) => Math.max(0, prev - removed))
      message.success(`已清空 ${removed} 条已读通知`)
    } catch (err) {
      console.error('清空已读失败:', err)
    } finally {
      setClearOpen(false)
    }
  }

  const handleRowDelete = async (notif: Notification, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await deleteNotification(notif.notif_id)
      removeNotification(notif.notif_id)
      if (selectedNotif?.notif_id === notif.notif_id) {
        closeDrawer()
      }
      setTotal((prev) => Math.max(0, prev - 1))
      message.success('已删除')
    } catch (err) {
      console.error('删除通知失败:', err)
    }
  }

  const handleMarkOneAsRead = async (notifId: string) => {
    try {
      await markAsRead(notifId)
      markAsReadStore(notifId)
    } catch (err) {
      console.error('标记已读失败:', err)
    }
  }

  const handleDeleteFromDrawer = async (notifId: string) => {
    try {
      await deleteNotification(notifId)
      removeNotification(notifId)
      setTotal((prev) => Math.max(0, prev - 1))
    } catch (err) {
      console.error('删除通知失败:', err)
    }
  }

  const showNewNotifBanner = newSinceLastFetch > 0 && !bannerDismissed

  return (
    <div>
      {/* 顶部筛选 + 操作 */}
      <Card
        style={{
          background: 'rgba(30, 41, 59, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 12,
          marginBottom: 16,
        }}
        styles={{ body: { padding: '16px 20px' } }}
      >
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 12,
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <Space wrap size={12}>
            <Select
              value={type}
              onChange={(val: string) => {
                setType(val)
                setPage(1)
              }}
              options={TYPE_FILTER_OPTIONS}
              style={{ width: 160 }}
            />
            <Input
              placeholder="搜索标题"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              allowClear
              prefix={<SearchOutlined style={{ color: '#64748B' }} />}
              style={{ width: 220 }}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={refreshNow}
              style={{ borderRadius: 8 }}
            >
              刷新
            </Button>
          </Space>
          <Space wrap size={8}>
            <Button onClick={handleMarkAllAsRead} style={{ borderRadius: 8 }}>
              全部已读
            </Button>
            <Popconfirm
              title="清空已读通知"
              description="将永久删除所有已读通知，无法恢复。确定吗？"
              open={clearOpen}
              onOpenChange={setClearOpen}
              onConfirm={handleClearRead}
              okText="清空"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger style={{ borderRadius: 8 }}>
                清空已读
              </Button>
            </Popconfirm>
          </Space>
        </div>
      </Card>

      {/* 新通知提示条（WS 推送时出现，避免分页场景下新通知被挤出视野） */}
      {showNewNotifBanner && (
        <Alert
          type="info"
          showIcon
          closable
          onClose={() => setBannerDismissed(true)}
          message={
            <span style={{ color: '#E2E8F0' }}>
              已收到 <b style={{ color: '#3B82F6' }}>{newSinceLastFetch}</b> 条新通知
              <Button
                type="link"
                size="small"
                onClick={refreshNow}
                style={{ marginLeft: 8, padding: 0, color: '#3B82F6' }}
              >
                刷新
              </Button>
            </span>
          }
          style={{
            marginBottom: 16,
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: 12,
          }}
        />
      )}

      {/* 列表 */}
      <Card
        style={{
          background: 'rgba(30, 41, 59, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 12,
        }}
        styles={{ body: { padding: '0 20px 20px' } }}
      >
        {total === 0 && !loading ? (
          <Empty
            image={<InboxOutlined style={{ fontSize: 64, color: '#475569' }} />}
            imageStyle={{ height: 80 }}
            description={<span style={{ color: '#94A3B8' }}>暂无通知</span>}
            style={{ padding: '40px 0' }}
          />
        ) : (
          <>
            {keyword.trim() && (
              <div
                style={{
                  padding: '14px 4px 8px',
                  color: '#94A3B8',
                  fontSize: 12,
                }}
              >
                筛选后 {filteredNotifications.length} 条 / 共 {total} 条
              </div>
            )}
            <List<Notification>
              dataSource={filteredNotifications}
              loading={loading}
              rowKey={(n) => n.notif_id}
              split={false}
              locale={{
                emptyText: (
                  <span style={{ color: '#94A3B8', padding: 24, display: 'block' }}>
                    没有匹配的通知
                  </span>
                ),
              }}
              renderItem={(notif) => {
                const cfg = getTypeConfig(notif.type)
                return (
                  <div
                    onClick={() => openDrawer(notif)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 16,
                      padding: '12px 14px',
                      borderRadius: 8,
                      minHeight: 64,
                      cursor: 'pointer',
                      background: notif.is_read
                        ? 'transparent'
                        : 'rgba(59, 130, 246, 0.06)',
                      border: '1px solid rgba(255, 255, 255, 0.04)',
                      marginBottom: 8,
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = notif.is_read
                        ? 'transparent'
                        : 'rgba(59, 130, 246, 0.06)'
                    }}
                  >
                    {/* 未读蓝点 */}
                    <div
                      aria-hidden
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        background: notif.is_read ? 'transparent' : '#3B82F6',
                        boxShadow: notif.is_read
                          ? 'none'
                          : '0 0 6px rgba(59, 130, 246, 0.6)',
                        flexShrink: 0,
                      }}
                    />
                    {/* 类型 */}
                    <div style={{ width: 96, flexShrink: 0 }}>
                      <Tag
                        style={{
                          background: `${cfg.color}20`,
                          color: cfg.color,
                          border: `1px solid ${cfg.color}40`,
                          borderRadius: 6,
                          margin: 0,
                          fontSize: 12,
                          width: '100%',
                          textAlign: 'center',
                          padding: '2px 6px',
                        }}
                      >
                        {cfg.label}
                      </Tag>
                    </div>
                    {/* 标题 + 摘要 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          color: notif.is_read ? '#94A3B8' : '#E2E8F0',
                          fontWeight: notif.is_read ? 400 : 600,
                          fontSize: 14,
                          marginBottom: 4,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {notif.title}
                      </div>
                      {notif.content && (
                        <div
                          style={{
                            color: '#64748B',
                            fontSize: 12,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {notif.content}
                        </div>
                      )}
                    </div>
                    {/* 时间 */}
                    <div
                      style={{
                        color: '#64748B',
                        fontSize: 12,
                        fontFamily: "'Space Grotesk', monospace",
                        flexShrink: 0,
                        width: 150,
                        textAlign: 'right',
                      }}
                    >
                      {formatAbsoluteTime(notif.created_at)}
                    </div>
                    {/* 操作 */}
                    <div
                      style={{ display: 'flex', gap: 4, flexShrink: 0 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        type="link"
                        icon={<EyeOutlined />}
                        onClick={() => openDrawer(notif)}
                        style={{ color: '#3B82F6', padding: '0 8px' }}
                      >
                        查看
                      </Button>
                      <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => handleRowDelete(notif, e)}
                        style={{ padding: '0 8px' }}
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                )
              }}
            />
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: 16,
              }}
            >
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                pageSizeOptions={PAGE_SIZE_OPTIONS.map(String)}
                showSizeChanger
                showTotal={(t) => `共 ${t} 条`}
                onChange={(p, ps) => {
                  setPage(p)
                  if (ps !== pageSize) setPageSize(ps)
                }}
              />
            </div>
          </>
        )}
      </Card>

      <NotificationDetailDrawer
        notification={selectedNotif}
        open={drawerOpen}
        onClose={closeDrawer}
        onMarkAsRead={handleMarkOneAsRead}
        onDelete={handleDeleteFromDrawer}
      />
    </div>
  )
}

export default NotificationsPage
