import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag } from 'antd'
import { ArrowUpOutlined, KeyOutlined, ThunderboltOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { getUsageStats } from '../api/stats'
import { getApiKeys } from '../api/apiKeys'
import dayjs from 'dayjs'

const Dashboard = () => {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [keys, setKeys] = useState<any[]>([])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const endDate = dayjs().format('YYYY-MM-DD')
      const startDate = dayjs().subtract(7, 'day').format('YYYY-MM-DD')
      
      const [statsData, keysData] = await Promise.all([
        getUsageStats({ start_date: startDate, end_date: endDate }),
        getApiKeys()
      ])
      
      setStats(statsData)
      setKeys(keysData.items || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const columns = [
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
        <span style={{ color: '#CBD5E1', fontFamily: "'Space Grotesk', sans-serif" }}>
          {val?.toLocaleString() || '0'}
        </span>
      )
    },
    { 
      title: '本月使用', 
      dataIndex: 'monthly_used', 
      key: 'monthly_used',
      render: (val: number) => (
        <span style={{ color: '#CBD5E1', fontFamily: "'Space Grotesk', sans-serif" }}>
          {val?.toLocaleString() || '0'}
        </span>
      )
    },
  ]

  const maxTokens = stats?.by_model?.reduce((max: number, item: any) => 
    Math.max(max, item.tokens || 0), 0) || 1

  return (
    <div className="stagger-children">
      <h2 style={{ 
        marginBottom: 24, 
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 24,
        fontWeight: 600,
        color: '#F8FAFC',
      }}>
        仪表盘
      </h2>
      
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            style={{ 
              background: 'rgba(17, 24, 39, 0.6)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 16,
            }}
            className="animate-fade-in-up"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <Statistic
                  title={<span style={{ color: '#94A3B8' }}>本月额度</span>}
                  value={stats?.total_tokens || 0}
                  suffix="tokens"
                  valueStyle={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontWeight: 600,
                  }}
                />
              </div>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.2) 0%, rgba(59, 130, 246, 0.1) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <ThunderboltOutlined style={{ fontSize: 24, color: '#3B82F6' }} />
              </div>
            </div>
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
            className="animate-fade-in-up"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <Statistic
                  title={<span style={{ color: '#94A3B8' }}>已使用</span>}
                  value={stats?.total_requests || 0}
                  suffix="次"
                  prefix={<ArrowUpOutlined style={{ color: '#DC2626' }} />}
                  valueStyle={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontWeight: 600,
                  }}
                />
              </div>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(220, 38, 38, 0.2) 0%, rgba(220, 38, 38, 0.1) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <ArrowUpOutlined style={{ fontSize: 24, color: '#DC2626' }} />
              </div>
            </div>
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
            className="animate-fade-in-up"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <Statistic
                  title={<span style={{ color: '#94A3B8' }}>API Key</span>}
                  value={keys.length}
                  valueStyle={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontWeight: 600,
                  }}
                />
              </div>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(34, 197, 94, 0.1) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <KeyOutlined style={{ fontSize: 24, color: '#22C55E' }} />
              </div>
            </div>
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
            className="animate-fade-in-up"
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div>
                <Statistic
                  title={<span style={{ color: '#94A3B8' }}>平均延迟</span>}
                  value={stats?.avg_latency_ms || 0}
                  suffix="ms"
                  valueStyle={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontWeight: 600,
                  }}
                />
              </div>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(234, 88, 12, 0.2) 0%, rgba(234, 88, 12, 0.1) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <ClockCircleOutlined style={{ fontSize: 24, color: '#EA580C' }} />
              </div>
            </div>
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
                模型使用分布
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
            {stats?.by_model?.map((item: any) => (
              <div key={item.model} style={{ marginBottom: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ color: '#CBD5E1', fontWeight: 500 }}>{item.model}</span>
                  <span style={{ 
                    color: '#F8FAFC', 
                    fontFamily: "'Space Grotesk', sans-serif",
                    fontWeight: 600 
                  }}>
                    {item.tokens?.toLocaleString()} tokens
                  </span>
                </div>
                <div style={{ 
                  height: 8, 
                  background: 'rgba(30, 41, 59, 0.8)', 
                  borderRadius: 4,
                  overflow: 'hidden',
                }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${(item.tokens / maxTokens) * 100}%`,
                    background: `linear-gradient(90deg, #2563EB 0%, #3B82F6 100%)`,
                    borderRadius: 4,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>
            ))}
            {(!stats?.by_model || stats?.by_model?.length === 0) && (
              <div style={{ 
                textAlign: 'center', 
                padding: '40px 0',
                color: '#64748B',
              }}>
                暂无数据
              </div>
            )}
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
                API Key
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
              dataSource={keys}
              columns={columns}
              rowKey="key_id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
