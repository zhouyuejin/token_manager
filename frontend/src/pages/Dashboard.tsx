import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag } from 'antd'
import { ArrowUpOutlined, KeyOutlined, ApiOutlined } from '@ant-design/icons'
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
    { title: 'Key名称', dataIndex: 'name', key: 'name' },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    { 
      title: '今日使用', 
      dataIndex: 'daily_used', 
      key: 'daily_used',
      render: (val: number) => val?.toLocaleString() || '0'
    },
    { 
      title: '本月使用', 
      dataIndex: 'monthly_used', 
      key: 'monthly_used',
      render: (val: number) => val?.toLocaleString() || '0'
    },
  ]

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>
      
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月额度"
              value={stats?.total_tokens || 0}
              suffix="tokens"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已使用"
              value={stats?.total_requests || 0}
              suffix="次"
              prefix={<ArrowUpOutlined style={{ color: '#ff4d4f' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="API Key"
              value={keys.length}
              prefix={<KeyOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均延迟"
              value={stats?.avg_latency_ms || 0}
              suffix="ms"
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="模型使用分布" loading={loading}>
            {stats?.by_model?.map((item: any) => (
              <div key={item.model} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>{item.model}</span>
                  <span>{item.tokens?.toLocaleString()} tokens</span>
                </div>
                <div style={{ 
                  height: 8, 
                  background: '#f0f0f0', 
                  borderRadius: 4,
                  marginTop: 4 
                }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${(item.tokens / (stats?.total_tokens || 1)) * 100}%`,
                    background: '#1677FF',
                    borderRadius: 4
                  }} />
                </div>
              </div>
            ))}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="API Key" loading={loading}>
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
