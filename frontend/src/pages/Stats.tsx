import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, DatePicker, Table, Button, Space } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { getUsageStats } from '../api/stats'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

const StatsPage = () => {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, 'day'),
    dayjs()
  ])

  useEffect(() => {
    fetchStats()
  }, [dateRange])

  const fetchStats = async () => {
    setLoading(true)
    try {
      const data = await getUsageStats({
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      })
      setStats(data)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = () => {
    // TODO: 实现导出功能
    const csvContent = [
      ['日期', 'Token数', '请求数'].join(','),
      ...(stats?.by_day || []).map((item: any) => 
        [item.date, item.tokens, item.requests].join(',')
      )
    ].join('\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `usage_stats_${dateRange[0].format('YYYY-MM-DD')}_${dateRange[1].format('YYYY-MM-DD')}.csv`
    link.click()
  }

  const modelColumns = [
    { title: '模型', dataIndex: 'model', key: 'model' },
    { title: 'Token数', dataIndex: 'tokens', key: 'tokens', render: (v: number) => v?.toLocaleString() },
    { title: '请求数', dataIndex: 'requests', key: 'requests', render: (v: number) => v?.toLocaleString() },
    { title: '预估费用', dataIndex: 'cost', key: 'cost', render: (v: number) => v ? `$${v.toFixed(2)}` : '-' },
  ]

  const dayColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: 'Token数', dataIndex: 'tokens', key: 'tokens', render: (v: number) => v?.toLocaleString() },
    { title: '请求数', dataIndex: 'requests', key: 'requests', render: (v: number) => v?.toLocaleString() },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>用量统计</h2>
        <Space>
          <RangePicker 
            value={dateRange}
            onChange={(dates) => {
              if (dates && dates[0] && dates[1]) {
                setDateRange([dates[0], dates[1]])
              }
            }} 
          />
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="总调用次数" value={stats?.total_requests || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总Token数" value={stats?.total_tokens || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="平均延迟" value={stats?.avg_latency_ms || 0} suffix="ms" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="成功率" value={stats?.success_rate || 100} suffix="%" />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="按模型统计" loading={loading}>
            <Table
              dataSource={stats?.by_model || []}
              columns={modelColumns}
              rowKey="model"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="每日趋势" loading={loading}>
            <Table
              dataSource={stats?.by_day || []}
              columns={dayColumns}
              rowKey="date"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default StatsPage
