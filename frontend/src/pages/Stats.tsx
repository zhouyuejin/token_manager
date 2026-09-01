import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, DatePicker, Table, Button, Space, Tag } from 'antd'
import { DownloadOutlined, ApiOutlined, ThunderboltOutlined, ClockCircleOutlined, CheckCircleOutlined, TeamOutlined } from '@ant-design/icons'
import { getUsageStats, getAdminStats } from '../api/stats'
import { getApiKeys } from '../api/apiKeys'
import { useAuthStore } from '../store/auth'
import dayjs from 'dayjs'
import ReactECharts from 'echarts-for-react'

const { RangePicker } = DatePicker

const StatsPage = () => {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [keys, setKeys] = useState<any[]>([])
  const [dateRange, setDateRange] = useState<any>([
    dayjs().subtract(7, 'day'),
    dayjs()
  ])

  useEffect(() => {
    fetchData()
  }, [dateRange, isAdmin])

  const fetchData = async () => {
    setLoading(true)
    try {
      const statsParams = {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      }
      
      let statsData: any
      if (isAdmin) {
        // 管理员获取所有数据
        const [adminStats, myStats] = await Promise.all([
          getAdminStats(statsParams),
          getUsageStats(statsParams)
        ])
        // 合并数据：既有所有用户的统计，也有自己的详细统计
        statsData = {
          ...adminStats,
          by_model: myStats.by_model,
          by_day: myStats.by_day,
        }
      } else {
        statsData = await getUsageStats(statsParams)
      }
      
      const keysData = await getApiKeys()
      setStats(statsData)
      setKeys(keysData.items || [])
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

  // 模型使用分布的最大值
  const maxTokens = stats?.by_model?.reduce((max: number, item: any) => 
    Math.max(max, item.tokens || 0), 0) || 1

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

  // 管理员用 - 按用户统计列
  const userColumns = [
    { title: '用户', dataIndex: 'username', key: 'username',
      render: (text: string, record: any) => <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text || record.user_id}</span> },
    { title: 'Token数', dataIndex: 'tokens', key: 'tokens',
      render: (v: number) => <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>{v?.toLocaleString()}</span> },
  ]

  // 管理员用 - 按供应商统计列
  const providerColumns = [
    { title: '供应商', dataIndex: 'provider', key: 'provider',
      render: (text: string) => <span style={{ color: '#F8FAFC' }}>{text}</span> },
    { title: 'Token数', dataIndex: 'tokens', key: 'tokens',
      render: (v: number) => <span style={{ fontFamily: "'Space Grotesk', sans-serif", color: '#CBD5E1' }}>{v?.toLocaleString()}</span> },
  ]

  const keyColumns = [
    { 
      title: 'Key名称', 
      dataIndex: 'name', 
      key: 'name',
      render: (text: string) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
      )
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag 
          color={status === 'active' ? 'success' : 'error'}
          style={{ 
            borderRadius: '6px',
            background: status === 'active' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(220, 38, 38, 0.15)',
            border: 'none',
          }}
        >
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    { 
      title: '今日使用', 
      dataIndex: 'daily_used', 
      key: 'daily_used',
      render: (val: number) => (
        <span style={{ color: '#CBD5E1', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
          {val?.toLocaleString() || '0'}
        </span>
      )
    },
    { 
      title: '本月使用', 
      dataIndex: 'monthly_used', 
      key: 'monthly_used',
      render: (val: number) => (
        <span style={{ color: '#CBD5E1', fontFamily: "'JetBrains Mono', 'Fira Code', monospace" }}>
          {val?.toLocaleString() || '0'}
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
          仪表盘
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

      {/* 统计卡片 */}
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

      {/* 主要内容区：模型统计 + API Keys */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        {/* 模型使用分布 */}
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 10,
              }}>
                <div style={{
                  width: 4,
                  height: 16,
                  background: 'linear-gradient(180deg, #3B82F6 0%, #2563EB 100%)',
                  borderRadius: 2,
                }} />
                <span style={{ 
                  color: '#F8FAFC', 
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 600,
                  fontSize: 15,
                }}>
                  模型使用分布
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{
              body: { padding: '20px' },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            {stats?.by_model?.map((item: any, idx: number) => (
              <div key={item.model} style={{ marginBottom: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ 
                    color: '#CBD5E1', 
                    fontWeight: 500,
                    fontSize: 13,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}>
                    <span style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'][idx % 5],
                      boxShadow: `0 0 8px ${['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'][idx % 5]}40`,
                    }} />
                    {item.model}
                  </span>
                  <span style={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    fontWeight: 600,
                    fontSize: 13,
                  }}>
                    {item.tokens?.toLocaleString()} tokens
                  </span>
                </div>
                <div style={{ 
                  height: 8, 
                  background: 'rgba(30, 41, 59, 0.8)', 
                  borderRadius: 4,
                  overflow: 'hidden',
                  position: 'relative',
                }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${(item.tokens / maxTokens) * 100}%`,
                    background: `linear-gradient(90deg, ${['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'][idx % 5]} 0%, ${['#60A5FA', '#34D399', '#FBBF24', '#A78BFA', '#F472B6'][idx % 5]} 100%)`,
                    borderRadius: 4,
                    transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
                    boxShadow: `0 0 10px ${['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'][idx % 5]}40`,
                  }} />
                </div>
              </div>
            ))}
            {(!stats?.by_model || stats?.by_model?.length === 0) && (
              <div style={{ 
                textAlign: 'center', 
                padding: '40px 0',
                color: 'rgba(100, 116, 139, 0.6)',
              }}>
                <div style={{ 
                  fontSize: 48, 
                  marginBottom: 12,
                  opacity: 0.3,
                }}>📊</div>
                暂无数据
              </div>
            )}
          </Card>
        </Col>

        {/* API Key 列表 */}
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 10,
              }}>
                <div style={{
                  width: 4,
                  height: 16,
                  background: 'linear-gradient(180deg, #10B981 0%, #059669 100%)',
                  borderRadius: 2,
                }} />
                <span style={{ 
                  color: '#F8FAFC', 
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 600,
                  fontSize: 15,
                }}>
                  API Key
                </span>
              </div>
            }
            loading={loading}
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: 16,
            }}
            styles={{
              body: { padding: '16px' },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            <Table
              dataSource={keys}
              columns={keyColumns}
              rowKey="key_id"
              pagination={false}
              size="small"
              style={{ 
                background: 'transparent',
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* 管理员额外显示按用户/供应商统计 */}
      {isAdmin && (
        <Row gutter={[20, 20]} style={{ marginBottom: 20 }}>
          <Col xs={24} lg={12}>
            <Card 
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <TeamOutlined style={{ color: '#3B82F6' }} />
                  <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>按用户统计</span>
                </div>
              }
              loading={loading}
              style={{ background: 'rgba(17, 24, 39, 0.6)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 16 }}
            >
              <Table dataSource={stats?.by_user || []} columns={userColumns} rowKey="user_id" pagination={false} size="small" />
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card 
              title={
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <ApiOutlined style={{ color: '#10B981' }} />
                  <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>按供应商统计</span>
                </div>
              }
              loading={loading}
              style={{ background: 'rgba(17, 24, 39, 0.6)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: 16 }}
            >
              <Table dataSource={stats?.by_provider || []} columns={providerColumns} rowKey="provider" pagination={false} size="small" />
            </Card>
          </Col>
        </Row>
      )}

      {/* 按模型统计 + 每日趋势 */}
      <Row gutter={[20, 20]}>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <span style={{ 
                color: '#F8FAFC', 
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
              }}>
                模型成本分布
              </span>
            }
            loading={loading}
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
            styles={{ body: { padding: '16px' } }}
          >
            <ReactECharts
              style={{ height: 300 }}
              option={{
                tooltip: {
                  trigger: 'axis',
                  backgroundColor: 'rgba(17, 24, 39, 0.9)',
                  borderColor: 'rgba(255, 255, 255, 0.1)',
                  textStyle: { color: '#F8FAFC' },
                  axisPointer: { type: 'shadow' },
                  formatter: (params: any) => {
                    const item = params[0];
                    const value = item?.value ?? 0;
                    const displayValue = Number(value) < 0.01 
                      ? Number(value).toFixed(4) 
                      : Number(value).toFixed(2);
                    return (item?.name || '') + ': $' + displayValue;
                  }
                },
                grid: {
                  left: '3%',
                  right: '4%',
                  bottom: '3%',
                  top: '10%',
                  containLabel: true
                },
                xAxis: {
                  type: 'category',
                  data: (stats?.by_model || []).map((item: any) => item.model),
                  axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
                  axisLabel: { color: '#94A3B8', fontSize: 11, rotate: 45 }
                },
                yAxis: {
                  type: 'value',
                  name: 'Cost ($)',
                  nameTextStyle: { color: '#94A3B8', padding: [0, 0, 0, 10] },
                  axisLine: { show: false },
                  splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
                  axisLabel: { color: '#94A3B8' }
                },
                series: [
                  {
                    name: 'Cost',
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 8,
                    lineStyle: { color: '#10B981', width: 3 },
                    itemStyle: { color: '#10B981' },
                    areaStyle: {
                      color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                          { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                          { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
                        ]
                      }
                    },
                    data: (stats?.by_model || []).map((item: any) => item.cost || 0)
                  }
                ]
              }}
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
