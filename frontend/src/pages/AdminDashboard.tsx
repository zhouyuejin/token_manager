import { useState, useEffect } from 'react'
import { Row, Col, Card, Table, Statistic, DatePicker, Typography } from 'antd'
import { 
  UserOutlined, 
  KeyOutlined, 
  CloudServerOutlined, 
  ApiOutlined,
  RiseOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { getAdminStats, AdminStats } from '../api/admin'

const { RangePicker } = DatePicker
const { Title, Text } = Typography

interface SystemStats {
  total_users?: number
  active_users?: number
  total_api_keys?: number
  active_api_keys?: number
  total_providers?: number
  active_providers?: number
}

const AdminDashboard: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [systemStats, setSystemStats] = useState<SystemStats>({})
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(30, 'day'),
    dayjs()
  ])

  useEffect(() => {
    fetchData()
  }, [dateRange])

  const fetchData = async () => {
    setLoading(true)
    try {
      const statsParams = {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      }
      
      const statsData = await getAdminStats(statsParams)
      setStats(statsData)
      
      // 获取系统概览数据
      // TODO: 等后端完善
      setSystemStats({
        total_users: statsData.by_user?.length || 0,
        total_api_keys: 0,
        total_providers: statsData.by_provider?.length || 0,
      })
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 计算最大值的辅助函数
  const maxTokens = stats?.by_model?.reduce((max, item) => 
    Math.max(max, item.tokens || 0), 0) || 1

  const maxUserTokens = stats?.by_user?.reduce((max, item) => 
    Math.max(max, item.tokens || 0), 0) || 1

  // 按用户统计表格列
  const userColumns = [
    { 
      title: '用户', 
      dataIndex: 'username', 
      key: 'username',
      render: (text: string, record: any) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text || record.user_id}</span>
      )
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
      title: '占比',
      key: 'percent',
      render: (_: any, record: any) => (
        <div style={{ width: 100 }}>
          <div style={{ 
            height: 6, 
            background: 'rgba(30, 41, 59, 0.8)', 
            borderRadius: 3,
            overflow: 'hidden',
          }}>
            <div style={{ 
              height: '100%', 
              width: `${(record.tokens / maxUserTokens) * 100}%`,
              background: 'linear-gradient(90deg, #3B82F6 0%, #60A5FA 100%)',
              borderRadius: 3,
            }} />
          </div>
        </div>
      )
    }
  ]

  // 按供应商统计表格列
  const providerColumns = [
    { 
      title: '供应商', 
      dataIndex: 'provider', 
      key: 'provider',
      render: (text: string) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
      )
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

  // 按模型统计表格列
  const modelColumns = [
    { 
      title: '模型', 
      dataIndex: 'model', 
      key: 'model',
      render: (text: string) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
      )
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

  // 每日趋势表格列
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
    <div style={{ padding: '0 24px 24px' }}>
      {/* 页面头部 */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={3} style={{ margin: 0, color: '#F8FAFC' }}>管理员仪表盘</Title>
          <Text style={{ color: 'rgba(148, 163, 184, 0.8)' }}>系统用量统计与监控</Text>
        </div>
        <RangePicker 
          value={dateRange}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([dates[0], dates[1]])
            }
          }}
          style={{ background: 'rgba(30, 41, 59, 0.6)' }}
        />
      </div>

      {/* 核心统计卡片 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            loading={loading}
            style={{ 
              background: 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>总Token消耗</span>}
              value={stats?.total_tokens || 0}
              suffix="tokens"
              valueStyle={{ color: '#3B82F6', fontFamily: "'JetBrains Mono', monospace" }}
              prefix={<BarChartOutlined style={{ color: '#3B82F6' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            loading={loading}
            style={{ 
              background: 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>总请求数</span>}
              value={stats?.total_requests || 0}
              valueStyle={{ color: '#10B981', fontFamily: "'JetBrains Mono', monospace" }}
              prefix={<ApiOutlined style={{ color: '#10B981' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            loading={loading}
            style={{ 
              background: 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>平均延迟</span>}
              value={stats?.avg_latency_ms || 0}
              suffix="ms"
              valueStyle={{ color: '#F59E0B', fontFamily: "'JetBrains Mono', monospace" }}
              prefix={<ClockCircleOutlined style={{ color: '#F59E0B' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card 
            loading={loading}
            style={{ 
              background: 'linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: 16,
            }}
          >
            <Statistic
              title={<span style={{ color: 'rgba(148, 163, 184, 0.8)' }}>成功率</span>}
              value={stats?.success_rate || 100}
              suffix="%"
              valueStyle={{ color: '#22C55E', fontFamily: "'JetBrains Mono', monospace" }}
              prefix={<CheckCircleOutlined style={{ color: '#22C55E' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* 按模型分布 - 图表式展示 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 20 }}>
        <Col xs={24}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <BarChartOutlined style={{ color: '#8B5CF6' }} />
                <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
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
            {stats?.by_model?.map((item, idx) => (
              <div key={item.model} style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ color: '#CBD5E1', fontWeight: 500, fontSize: 13 }}>
                    {item.model}
                  </span>
                  <span style={{ color: '#F8FAFC', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, fontSize: 13 }}>
                    {item.tokens?.toLocaleString()} tokens
                  </span>
                </div>
                <div style={{ height: 8, background: 'rgba(30, 41, 59, 0.8)', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${(item.tokens / maxTokens) * 100}%`,
                    background: `linear-gradient(90deg, ${['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'][idx % 5]} 0%, ${['#60A5FA', '#34D399', '#FBBF24', '#A78BFA', '#F472B6'][idx % 5]} 100%)`,
                    borderRadius: 4,
                    transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
                  }} />
                </div>
              </div>
            ))}
            {(!stats?.by_model || stats?.by_model?.length === 0) && (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'rgba(100, 116, 139, 0.6)' }}>
                暂无数据
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 按用户和供应商统计 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <UserOutlined style={{ color: '#3B82F6' }} />
                <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  按用户统计
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
              body: { padding: '16px', maxHeight: 400, overflow: 'auto' },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            <Table
              dataSource={stats?.by_user || []}
              columns={userColumns}
              rowKey="user_id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CloudServerOutlined style={{ color: '#10B981' }} />
                <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  按供应商统计
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
              body: { padding: '16px', maxHeight: 400, overflow: 'auto' },
              header: { borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }
            }}
          >
            <Table
              dataSource={stats?.by_provider || []}
              columns={providerColumns}
              rowKey="provider"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 按日趋势 */}
      <Row gutter={[20, 20]}>
        <Col xs={24}>
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <RiseOutlined style={{ color: '#F59E0B' }} />
                <span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600 }}>
                  每日趋势
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

export default AdminDashboard
