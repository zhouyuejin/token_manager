import { useState, useEffect } from 'react'
import { Card, Table, Input, Select, Button, Space, Typography, DatePicker } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { getOperationLogs, OperationLog, OperationLogParams } from '../../api/logs'

const { Text } = Typography
const { RangePicker } = DatePicker

const ACTION_OPTIONS = [
  { label: '全部', value: '' },
  { label: '创建', value: 'create' },
  { label: '更新', value: 'update' },
  { label: '删除', value: 'delete' },
]

const TARGET_TYPE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '用户', value: 'user' },
  { label: 'API Key', value: 'api_key' },
  { label: '模型', value: 'model' },
  { label: '供应商', value: 'provider' },
  { label: '额度', value: 'quota' },
]

const OperationLogsPage = () => {
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
    setKeyword('')
    setAction('')
    setTargetType('')
    setDateRange(null)
    setPage(1)
    fetchData({ page: 1 })
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
      width: 160,
      render: (val: string) => (
        <Text style={{ color: '#94A3B8', fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {dayjs(val).format('YYYY-MM-DD HH:mm:ss')}
        </Text>
      ),
    },
    {
      title: '操作人',
      dataIndex: 'operator_name',
      key: 'operator_name',
      width: 120,
      render: (val: string) => (
        <Text style={{ color: '#F8FAFC', fontWeight: 500 }}>{val}</Text>
      ),
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 80,
      render: (val: string) => (
        <Text style={{ color: '#F8FAFC' }}>{val}</Text>
      ),
    },
    {
      title: '目标类型',
      dataIndex: 'target_type',
      key: 'target_type',
      width: 100,
      render: (val: string) => (
        <Text style={{ color: '#CBD5E1' }}>{val}</Text>
      ),
    },
    {
      title: '目标ID',
      dataIndex: 'target_id',
      key: 'target_id',
      width: 120,
      render: (val: string) => (
        <Text style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {val}
        </Text>
      ),
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 130,
      render: (val: string) => (
        <Text style={{ color: '#94A3B8', fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {val}
        </Text>
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
              background: 'rgba(15, 23, 42, 0.6)',
              borderRadius: 6,
              padding: '4px 8px',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <Text
              copyable
              style={{
                color: '#94A3B8',
                fontFamily: "'Space Grotesk', monospace",
                fontSize: 11,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {json}
            </Text>
          </div>
        )
      },
    },
  ]

  return (
    <div>
      <Card
        style={{
          background: 'rgba(30, 41, 59, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 12,
          marginBottom: 16,
        }}
        styles={{ body: { padding: '16px 20px' } }}
      >
        <Space wrap align="center" size={12}>
          <Input
            placeholder="关键字搜索"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 180, borderRadius: 8 }}
            allowClear
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
          background: 'rgba(30, 41, 59, 0.6)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          borderRadius: 12,
        }}
        styles={{ body: { padding: '0 20px 20px' } }}
      >
        <Table
          dataSource={data}
          columns={columns}
          rowKey="log_id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: handlePageChange,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
          scroll={{ x: 900 }}
        />
      </Card>
    </div>
  )
}

export default OperationLogsPage
