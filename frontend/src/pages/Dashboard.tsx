import { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Table, Tag } from 'antd'
import {
  ThunderboltOutlined,
  ArrowUpOutlined,
  ClockCircleOutlined,
  ApiOutlined,
} from '@ant-design/icons'
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

  const maxTokens = stats?.by_model?.reduce((max: number, item: any) => 
    Math.max(max, item.tokens || 0), 0) || 1

  // 科技感渐变色配置
  const gradientPresets = [
    {
      bg: 'linear-gradient(135deg, rgba(37, 99, 235, 0.2) 0%, rgba(59, 130, 246, 0.1) 100%)',
      border: 'linear-gradient(135deg, rgba(37, 99, 235, 0.4) 0%, rgba(59, 130, 246, 0.2) 100%)',
      iconBg: 'linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(59, 130, 246, 0.15) 100%)',
      glow: 'rgba(37, 99, 235, 0.3)',
    },
    {
      bg: 'linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.1) 100%)',
      border: 'linear-gradient(135deg, rgba(16, 185, 129, 0.4) 0%, rgba(5, 150, 105, 0.2) 100%)',
      iconBg: 'linear-gradient(135deg, rgba(16, 185, 129, 0.3) 0%, rgba(5, 150, 105, 0.15) 100%)',
      glow: 'rgba(16, 185, 129, 0.3)',
    },
    {
      bg: 'linear-gradient(135deg, rgba(234, 88, 12, 0.2) 0%, rgba(217, 119, 6, 0.1) 100%)',
      border: 'linear-gradient(135deg, rgba(234, 88, 12, 0.4) 0%, rgba(217, 119, 6, 0.2) 100%)',
      iconBg: 'linear-gradient(135deg, rgba(234, 88, 12, 0.3) 0%, rgba(217, 119, 6, 0.15) 100%)',
      glow: 'rgba(234, 88, 12, 0.3)',
    },
    {
      bg: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(99, 102, 241, 0.1) 100%)',
      border: 'linear-gradient(135deg, rgba(139, 92, 246, 0.4) 0%, rgba(99, 102, 241, 0.2) 100%)',
      iconBg: 'linear-gradient(135deg, rgba(139, 92, 246, 0.3) 0%, rgba(99, 102, 241, 0.15) 100%)',
      glow: 'rgba(139, 92, 246, 0.3)',
    },
  ]

  const statCards = [
    {
      title: '本月额度',
      value: stats?.total_tokens || 0,
      suffix: 'tokens',
      icon: <ThunderboltOutlined />,
      color: '#3B82F6',
      prefix: null,
    },
    {
      title: '已使用',
      value: stats?.total_requests || 0,
      suffix: '次',
      icon: <ArrowUpOutlined />,
      color: '#10B981',
      prefix: <ArrowUpOutlined style={{ color: '#10B981' }} />,
    },
    {
      title: '平均延迟',
      value: stats?.avg_latency || 0,
      suffix: 'ms',
      icon: <ClockCircleOutlined />,
      color: '#F59E0B',
      prefix: null,
    },
    {
      title: 'API Keys',
      value: keys.length,
      suffix: '个',
      icon: <ApiOutlined />,
      color: '#8B5CF6',
      prefix: null,
    },
  ]

  return (
    <div className="stagger-children dashboard-container">
      {/* 页面标题区域 */}
      <div style={{ marginBottom: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ 
            marginBottom: 6, 
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 26,
            fontWeight: 700,
            background: 'linear-gradient(135deg, #F8FAFC 0%, #94A3B8 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            仪表盘
          </h2>
          <p style={{ 
            color: 'rgba(148, 163, 184, 0.7)', 
            fontSize: 13,
            margin: 0,
            fontFamily: "'DM Sans', sans-serif",
          }}>
            实时监控您的API使用情况
          </p>
        </div>
        <div style={{
          padding: '8px 16px',
          background: 'rgba(37, 99, 235, 0.1)',
          border: '1px solid rgba(37, 99, 235, 0.2)',
          borderRadius: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#10B981',
            boxShadow: '0 0 8px rgba(16, 185, 129, 0.6)',
            animation: 'pulse 2s infinite',
          }} />
          <span style={{ color: 'rgba(248, 250, 252, 0.8)', fontSize: 12 }}>
            系统正常运行
          </span>
        </div>
      </div>
      
      {/* 统计卡片区域 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        {statCards.map((stat, index) => (
          <Col xs={24} sm={12} lg={6} key={stat.title}>
            <Card 
              loading={loading}
              style={{ 
                background: gradientPresets[index].bg,
                backdropFilter: 'blur(20px)',
                border: '1px solid',
                borderImageSlice: 1,
                borderWidth: 1,
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: 16,
                overflow: 'hidden',
                position: 'relative',
              }}
              className="stat-card animate-fade-in-up"
              styles={{
                body: { padding: '20px' }
              }}
            >
              {/* 装饰性光效 */}
              <div style={{
                position: 'absolute',
                top: -50,
                right: -50,
                width: 120,
                height: 120,
                background: `radial-gradient(circle, ${gradientPresets[index].glow} 0%, transparent 70%)`,
                opacity: 0.5,
                pointerEvents: 'none',
              }} />
              
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', position: 'relative', zIndex: 1 }}>
                <div>
                  <Statistic
                    title={<span style={{ color: 'rgba(148, 163, 184, 0.8)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{stat.title}</span>}
                    value={stat.value}
                    suffix={stat.suffix}
                    prefix={stat.prefix}
                    valueStyle={{ 
                      color: '#F8FAFC', 
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                      fontWeight: 600,
                      fontSize: 26,
                      textShadow: `0 0 20px ${gradientPresets[index].glow}`,
                    }}
                  />
                </div>
                <div style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  background: gradientPresets[index].iconBg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  boxShadow: `0 4px 15px ${gradientPresets[index].glow}`,
                }}>
                  <span style={{ fontSize: 20, color: stat.color }}>{stat.icon}</span>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 图表和数据区域 */}
      <Row gutter={[20, 20]}>
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
                  background: 'linear-gradient(180deg, #3B82F6 0%, #8B5CF6 100%)',
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
              columns={columns}
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
    </div>
  )
}

export default Dashboard
