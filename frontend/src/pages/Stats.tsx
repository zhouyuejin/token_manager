import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, DatePicker, Table, Button, Space } from 'antd'
import { DownloadOutlined, ApiOutlined, ThunderboltOutlined, ClockCircleOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { getUsageStats } from '../api/stats'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

const StatsPage = () => {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [dateRange, setDateRange] = useState<any>([
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
    { 
      title: '模型', 
      dataIndex: 'model', 
      key: 'model',
      render: (text: string) => <span style={{ color: '#F8FAFC' }}>{text}</span>
    },
    { 
      title: 'Token数', 
      dataIndex: 'tokens', 
      key: 'tokens', 
      render: (v: number) => (
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>
          {v?.toLocaleString()}
        </span>
      )
    },
    { 
      title: '请求数', 
      dataIndex: 'requests', 
      key: 'requests', 
      render: (v: number) => (
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>
          {v?.toLocaleString()}
        </span>
      )
    },
    { 
      title: '预估费用', 
      dataIndex: 'cost', 
      key: 'cost', 
      render: (v: number) => (
        <span style={{ 
          fontFamily: "'Space Grotesk', sans-serif", 
          color: v ? '#22C55E' : '#64748B' 
        }}>
          {v ? `$${v.toFixed(2)}` : '-'}
        </span>
      )
    },
  ]

  const dayColumns = [
    { 
      title: '日期', 
      dataIndex: 'date', 
      key: 'date',
      render: (text: string) => <span style={{ color: '#CBD5E1' }}>{text}</span>
    },
    { 
      title: 'Token数', 
      dataIndex: 'tokens', 
      key: 'tokens', 
      render: (v: number) => (
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>
          {v?.toLocaleString()}
        </span>
      )
    },
    { 
      title: '请求数', 
      dataIndex: 'requests', 
      key: 'requests', 
      render: (v: number) => (
        <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>
          {v?.toLocaleString()}
        </span>
      )
    },
  ]

  return (
    <div className="stagger-children">
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        marginBottom: 24,
        alignItems: 'center',
      }}>
        <h2 style={{ 
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 24,
          fontWeight: 600,
          color: '#F8FAFC',
          margin: 0,
        }}>
          用量统计
        </h2>
        <Space>
          <RangePicker 
            value={dateRange}
            onChange={(dates: any) => {
              if (dates && dates[0] && dates[1]) {
                setDateRange([dates[0], dates[1]])
              }
            }}
            style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 10,
            }}
          />
          <Button 
            icon={<DownloadOutlined />} 
            onClick={handleExport}
            style={{
              background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
              border: 'none',
              borderRadius: 10,
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          >
            导出
          </Button>
        </Space>
      </div>

      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
            <Statistic 
              title={<span style={{ color: '#94A3B8' }}>总调用次数</span>} 
              value={stats?.total_requests || 0}
              valueStyle={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}
              prefix={<ApiOutlined style={{ color: '#3B82F6' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
            <Statistic 
              title={<span style={{ color: '#94A3B8' }}>总Token数</span>} 
              value={stats?.total_tokens || 0}
              valueStyle={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}
              prefix={<ThunderboltOutlined style={{ color: '#22C55E' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
            <Statistic 
              title={<span style={{ color: '#94A3B8' }}>平均延迟</span>} 
              value={stats?.avg_latency_ms || 0}
              suffix="ms"
              valueStyle={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}
              prefix={<ClockCircleOutlined style={{ color: '#EA580C' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
            <Statistic 
              title={<span style={{ color: '#94A3B8' }}>成功率</span>} 
              value={stats?.success_rate || 100}
              suffix="%"
              valueStyle={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}
              prefix={<CheckCircleOutlined style={{ color: '#22C55E' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <span style={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}>
                按模型统计
              </span>
            }
            loading={loading}
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
            <Table
              dataSource={stats?.by_model || []}
              columns={modelColumns}
              rowKey="model"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <span style={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}>
                每日趋势
              </span>
            }
            loading={loading}
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
          >
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
