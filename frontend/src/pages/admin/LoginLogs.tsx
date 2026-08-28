import { useState, useEffect } from 'react'
import { Card, Table, Input, Select, Button, Space, Tag, DatePicker } from 'antd'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { getLoginLogs, LoginLog, LoginLogParams } from '../../api/logs'

const { RangePicker } = DatePicker

const STATUS_OPTIONS = [
  { label: '全部', value: '' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
  { label: '锁定', value: 'blocked' },
]

const STATUS_COLOR: Record<string, string> = {
  success: 'success',
  failed: 'error',
  blocked: 'warning',
}

const STATUS_LABEL: Record<string, string> = {
  success: '成功',
  failed: '失败',
  blocked: '锁定',
}

const LoginLogsPage = () => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<LoginLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState('')
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async (params?: Partial<LoginLogParams>) => {
    setLoading(true)
    try {
      const start_date = dateRange?.[0] ? dateRange[0].format('YYYY-MM-DD') : undefined
      const end_date = dateRange?.[1] ? dateRange[1].format('YYYY-MM-DD') : undefined
      const result = await getLoginLogs({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        status: status || undefined,
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
      status: '',
      start_date: undefined,
      end_date: undefined,
      page: 1,
    }
    setKeyword('')
    setStatus('')
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
        <span style={{ color: '#94A3B8', fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {dayjs(val).format('YYYY-MM-DD HH:mm:ss')}
        </span>
      ),
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (val: string) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{val}</span>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (val: string) => (
        <Tag
          color={STATUS_COLOR[val] || 'default'}
          style={{
            borderRadius: '6px',
            background: STATUS_COLOR[val]
              ? `rgba(${val === 'success' ? '34,197,94' : val === 'failed' ? '220,38,38' : '249,115,22'}, 0.15)`
              : 'rgba(100,116,139,0.15)',
            border: 'none',
          }}
        >
          {STATUS_LABEL[val] || val}
        </Tag>
      ),
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      render: (val: string) => (
        <span style={{ color: '#94A3B8', fontFamily: "'Space Grotesk', monospace", fontSize: 12 }}>
          {val}
        </span>
      ),
    },
    {
      title: 'User-Agent',
      dataIndex: 'user_agent',
      key: 'user_agent',
      render: (val: string) => (
        <span
          style={{
            color: '#94A3B8',
            fontFamily: "'Space Grotesk', monospace",
            fontSize: 11,
          }}
        >
          {val}
        </span>
      ),
    },
    {
      title: '失败原因',
      dataIndex: 'failure_reason',
      key: 'failure_reason',
      render: (val: string) => (
        <span style={{ color: '#F87171', fontSize: 12 }}>{val || '-'}</span>
      ),
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
        <Space wrap size={12}>
          <Input
            placeholder="用户名搜索"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 180, borderRadius: 10, height: 40 }}
          />
          <Select
            value={status}
            onChange={(val) => { setStatus(val); setPage(1) }}
            options={STATUS_OPTIONS}
            style={{ width: 120, height: 40 }}
          />
          <RangePicker
            value={dateRange}
            onChange={(vals) => setDateRange(vals as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            style={{ borderRadius: 10, height: 40 }}
          />
          <Button 
            icon={<SearchOutlined />} 
            onClick={handleSearch} 
            style={{ borderRadius: 10, height: 40 }}
          >
            查询
          </Button>
          <Button 
            icon={<ReloadOutlined />} 
            onClick={handleReset} 
            style={{ borderRadius: 10, height: 40 }}
          >
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
        />
      </Card>
    </div>
  )
}

export default LoginLogsPage
