import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Card, Table, Input, Select, Button, Space, DatePicker } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { getOperationLogs, OperationLog, OperationLogParams } from '../../api/logs'

const { RangePicker } = DatePicker

const ACTION_LABELS: Record<string, string> = {
  create: '新建',
  update: '更新',
  delete: '删除',
  change_password: '修改密码',
  update_status: '修改状态',
  auto_freeze: '自动冻结',
  unfreeze: '解除冻结',
  adjust_quota: '调整额度',
  update_quota: '更新额度',
  sync_quota: '同步额度',
  sync_models: '同步模型',
  sync_pricing: '同步定价',
  bind_channel: '绑定渠道',
  unbind_channel: '解绑渠道',
  update_channel_binding: '修改渠道绑定',
  bind_model: '绑定模型',
  unbind_model: '解绑模型',
  update_model_binding: '修改模型绑定',
  replace_channels: '替换渠道',
  replace_models: '替换模型',
  batch_bind_models: '批量绑定模型',
}

const TARGET_TYPE_LABELS: Record<string, string> = {
  user: '用户',
  api_key: 'API Key',
  channel: '渠道',
  model: '模型',
  notification_settings: '通知设置',
}

const toOptions = (labels: Record<string, string>) => [
  { label: '全部', value: '' },
  ...Object.entries(labels).map(([value, label]) => ({ value, label })),
]

const ACTION_OPTIONS = toOptions(ACTION_LABELS)
const TARGET_TYPE_OPTIONS = toOptions(TARGET_TYPE_LABELS)

const OperationLogsPage = () => {
    const { token, isDark } = useThemeToken()

const [loading, setLoading] = useState(false)
  const [data, setData] = useState<OperationLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [keyword, setKeyword] = useState('')
  const [action, setAction] = useState('')
  const [targetType, setTargetType] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (params?: Partial<OperationLogParams>) => {
    setLoading(true)
    try {
      const start_date = dateRange?.[0] ? dateRange[0].format('YYYY-MM-DD') : undefined
      const end_date = dateRange?.[1] ? dateRange[1].format('YYYY-MM-DD') : undefined
      const result = await getOperationLogs({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        action: action || undefined,
        target_type: targetType || undefined,
        start_date,
        end_date,
        ...params,
      })
      setData(result.items || [])
      setTotal(result.total || 0)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPage(1)
    fetchData({ page: 1 })
  }

  const handleReset = () => {
    const resetParams = {
      keyword: '',
      action: '',
      target_type: '',
      start_date: undefined,
      end_date: undefined,
      page: 1,
    }
    setKeyword('')
    setAction('')
    setTargetType('')
    setDateRange(null)
    setPage(1)
    fetchData(resetParams)
  }

  const handlePageChange = (newPage: number, newPageSize: number) => {
    setPage(newPage)
    setPageSize(newPageSize)
    fetchData({ page: newPage, page_size: newPageSize })
  }

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => (
        <span style={{ color: token.colorTextSecondary, fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {dayjs.utc(val).local().format('YYYY-MM-DD HH:mm:ss')}
        </span>
      ),
    },
    {
      title: '操作人',
      dataIndex: 'operator_name',
      key: 'operator_name',
      render: (val: string) => (
        <span style={{ color: token.colorText, fontWeight: 500 }}>{val}</span>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      render: (val: string) => (
        <span style={{ color: token.colorText }}>{ACTION_LABELS[val] ?? val}</span>
      ),
    },
    {
      title: '目标类型',
      dataIndex: 'target_type',
      key: 'target_type',
      render: (val: string) => (
        <span style={{ color: token.colorText }}>{TARGET_TYPE_LABELS[val] ?? val}</span>
      ),
    },
    {
      title: '目标ID',
      dataIndex: 'target_id',
      key: 'target_id',
      render: (val: string) => (
        <span style={{ color: token.colorText, fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {val}
        </span>
      ),
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      render: (val: string) => (
        <span style={{ color: token.colorTextSecondary, fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {val}
        </span>
      ),
    },
    {
      title: '详情',
      dataIndex: 'detail',
      key: 'detail',
      render: (val: any) => {
        const json = typeof val === 'string' ? val : JSON.stringify(val, null, 2)
        return (
          <div
            style={{
              maxHeight: 200,
              overflowY: 'auto',
              background: isDark ? 'rgba(15, 23, 42, 0.6)' : 'rgba(248, 250, 252, 0.8)',
              borderRadius: 6,
              padding: '4px 8px',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <span
              style={{
                color: token.colorTextSecondary,
                fontFamily: "'Space Grotesk', monospace",
                fontSize: 11,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {json}
            </span>
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <Card
        style={{
          background: token.colorBgContainer,
          border: isDark ? '1px solid rgba(255, 255, 255, 0.06)' : '1px solid rgba(0, 0, 0, 0.06)',
          borderRadius: 12,
          marginBottom: 16,
        }}
        
      >
        <Space wrap size={12}>
          <Input
            placeholder="关键字搜索"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 180, borderRadius: 8 }}
          />
          <Select
            value={action}
            onChange={(val) => { setAction(val); setPage(1) }}
            options={ACTION_OPTIONS}
            style={{ width: 120 }}
          />
          <Select
            value={targetType}
            onChange={(val) => { setTargetType(val); setPage(1) }}
            options={TARGET_TYPE_OPTIONS}
            style={{ width: 140 }}
          />
          <RangePicker
            value={dateRange}
            onChange={(vals) => setDateRange(vals as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            style={{ borderRadius: 8 }}
          />
          <Button icon={<SearchOutlined />} onClick={handleSearch} style={{ borderRadius: 8 }}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset} style={{ borderRadius: 8 }}>
            重置
          </Button>
        </Space>
      </Card>

      <Card
        style={{
          background: token.colorBgContainer,
          border: isDark ? '1px solid rgba(255, 255, 255, 0.06)' : '1px solid rgba(0, 0, 0, 0.06)',
          borderRadius: 12,
        }}
        
      >
        <Table
          dataSource={data}
          columns={columns}
          rowKey="log_id"
          loading={loading}
          scroll={{ y: "calc(100vh - 425px)" }}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: handlePageChange,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
        />
      </Card>
    </div>
  )
}

export default OperationLogsPage
