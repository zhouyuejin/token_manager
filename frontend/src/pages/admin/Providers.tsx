import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, 
  Select, Popconfirm, Row, Col, Progress, Descriptions 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CloudOutlined, BarChartOutlined } from '@ant-design/icons'
import { 
  getProviders, createProvider, updateProvider, deleteProvider,
  getAllProviderQuotas, syncProviderQuota, Provider, 
} from '../../api/providers'

// ISO 时间格式化为 YYYY-MM-DD HH:MM:SS
const formatDateTime = (iso: string): string => {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 时间格式化函数
const formatRemainTime = (ms: number): string => {
  if (!ms || ms <= 0) return '0秒'
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (days > 0) return `${days}天${hours % 24}小时`
  if (hours > 0) return `${hours}小时${minutes % 60}分`
  if (minutes > 0) return `${minutes}分${seconds % 60}秒`
  return `${seconds}秒`
}

// 计算用量数据
const calcQuotaStats = (quota: any) => {
  if (!quota) return null
  const modelRemains = quota.hourly?.raw_data?.model_remains || []
  if (modelRemains.length === 0) return null
  
  const hourlyTotal = modelRemains.reduce((sum: number, m: any) => sum + (m.current_interval_total_count || 0), 0)
  const hourlyRemainPercent = modelRemains.reduce((sum: number, m: any) => sum + (m.current_interval_remaining_percent || 0), 0) / modelRemains.length
  const hourlyUsedPercent = 100 - hourlyRemainPercent
  
  const weeklyTotal = modelRemains.reduce((sum: number, m: any) => sum + (m.current_weekly_total_count || 0), 0)
  const weeklyRemainPercent = modelRemains.reduce((sum: number, m: any) => sum + (m.current_weekly_remaining_percent || 0), 0) / modelRemains.length
  const weeklyUsedPercent = 100 - weeklyRemainPercent
  
  return {
    modelRemains,
    hourlyTotal,
    hourlyRemainPercent,
    hourlyUsedPercent,
    weeklyTotal,
    weeklyRemainPercent,
    weeklyUsedPercent
  }
}

const ProvidersPage = () => {
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [quotas, setQuotas] = useState<any>({})
  const [modalVisible, setModalVisible] = useState(false)
  const [editProvider, setEditProvider] = useState<Provider | null>(null)
  const [statsProvider, setStatsProvider] = useState<Provider | null>(null)
  const [form] = Form.useForm()
  const message = useMessage()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [providersData, quotasData] = await Promise.all([
        getProviders(),
        getAllProviderQuotas()
      ])
      setProviders(providersData.items || [])
      
      const quotaMap: any = {}
      quotasData.items?.forEach((item: any) => {
        quotaMap[item.provider_id] = item
      })
      setQuotas(quotaMap)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async (providerId: string) => {
    try {
      await syncProviderQuota(providerId)
      message.success('同步成功')
      fetchData()
    } catch (error) {
      console.error(error)
      message.error('同步失败')
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createProvider(values)
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleUpdate = async (values: any) => {
    if (!editProvider) return
    try {
      await updateProvider(editProvider.provider_id, values)
      message.success('更新成功')
      setEditProvider(null)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleDelete = async (providerId: string) => {
    try {
      await deleteProvider(providerId)
      message.success('删除成功')
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const openEditModal = (provider: Provider) => {
    setEditProvider(provider)
    form.setFieldsValue({
      ...provider,
      quota_hourly: provider.quota_hourly,
      quota_weekly: provider.quota_weekly,
    })
  }

  // 渲染用量进度条
  const renderQuotaProgress = (usedPercent: number, remainPercent: number, total: number) => {
    if (usedPercent === 0 && remainPercent === 0 && total === 0) {
      return <span style={{ color: '#64748B', fontSize: 12 }}>暂无数据</span>
    }
    return (
      <div style={{ minWidth: 180 }}>
        <Progress 
          percent={Math.round(usedPercent)} 
          size="small"
          status={usedPercent > 90 ? 'exception' : 'normal'}
          strokeColor={{
            '0%': '#2563EB',
            '100%': '#3B82F6',
          }}
          trailColor="rgba(30, 41, 59, 0.8)"
        />
        <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 4 }}>
          已用 {Math.round(usedPercent)}% · 剩余 {Math.round(remainPercent)}% · 共 {total} 次
        </div>
      </div>
    )
  }

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
          <CloudOutlined style={{ marginRight: 12, color: '#3B82F6' }} />
          供应商管理
        </h2>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => setModalVisible(true)}
          style={{
            background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
            border: 'none',
            borderRadius: 10,
            fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          添加供应商
        </Button>
      </div>

      {/* 供应商列表 */}
      <div style={{
        background: 'rgba(17, 24, 39, 0.6)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        overflow: 'hidden',
      }}>
        <Table
          dataSource={providers}
          columns={[
            { 
              title: '供应商', 
              dataIndex: 'name', 
              key: 'name',
              render: (text: string) => <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
            },
            { 
              title: '类型', 
              dataIndex: 'type', 
              key: 'type',
              render: (text: string) => <span style={{ color: '#94A3B8' }}>{text}</span>
            },
            { 
              title: '5小时用量', 
              key: 'hourly',
              render: (_: any, record: Provider) => {
                const stats = calcQuotaStats(quotas[record.provider_id])
                if (!stats) return <span style={{ color: '#64748B' }}>-</span>
                return renderQuotaProgress(stats.hourlyUsedPercent, stats.hourlyRemainPercent, stats.hourlyTotal)
              }
            },
            { 
              title: '周用量', 
              key: 'weekly',
              render: (_: any, record: Provider) => {
                const stats = calcQuotaStats(quotas[record.provider_id])
                if (!stats) return <span style={{ color: '#64748B' }}>-</span>
                return renderQuotaProgress(stats.weeklyUsedPercent, stats.weeklyRemainPercent, stats.weeklyTotal)
              }
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
              title: '操作',
              key: 'action',
              render: (_: any, record: Provider) => (
                <Space>
                  <Button 
                    type="text" 
                    icon={<BarChartOutlined />} 
                    onClick={() => setStatsProvider(record)}
                    style={{ color: '#10B981' }}
                  >
                    用量统计
                  </Button>
                  <Button 
                    type="text" 
                    icon={<SyncOutlined />} 
                    onClick={() => handleSync(record.provider_id)}
                    style={{ color: '#3B82F6' }}
                  >
                    同步
                  </Button>
                  <Button 
                    type="text" 
                    icon={<EditOutlined />} 
                    onClick={() => openEditModal(record)}
                    style={{ color: '#3B82F6' }}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认删除此供应商？"
                    onConfirm={() => handleDelete(record.provider_id)}
                  >
                    <Button type="text" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
          rowKey="provider_id"
          loading={loading}
          pagination={false}
        />
      </div>

      {/* 用量统计详情弹窗 */}
      <Modal
        title={
          <Space>
            <BarChartOutlined style={{ color: '#10B981' }} />
            <span style={{ color: '#F8FAFC' }}>
              {statsProvider?.name} - 用量详情
            </span>
          </Space>
        }
        open={!!statsProvider}
        onCancel={() => setStatsProvider(null)}
        footer={
          <Space>
            <Button 
              icon={<SyncOutlined />}
              onClick={() => statsProvider && handleSync(statsProvider.provider_id)}
            >
              同步数据
            </Button>
            <Button onClick={() => setStatsProvider(null)}>关闭</Button>
          </Space>
        }
        width={800}
      >
        {statsProvider && (() => {
          const quota = quotas[statsProvider.provider_id]
          const stats = calcQuotaStats(quota)
          
          if (!stats) {
            return (
              <div style={{ color: '#64748B', textAlign: 'center', padding: '40px 0' }}>
                暂无用量数据，请先同步
              </div>
            )
          }
          
          return (
            <div>
              {/* 汇总信息 */}
              <Descriptions
                title="汇总统计"
                bordered
                size="small"
                column={2}
                style={{ marginBottom: 24 }}
              >
                <Descriptions.Item label="5小时已用">
                  <span style={{ color: '#F8FAFC', fontWeight: 600 }}>
                    {Math.round(stats.hourlyUsedPercent)}%
                  </span>
                  （共 {stats.hourlyTotal} 次）
                </Descriptions.Item>
                <Descriptions.Item label="5小时剩余">
                  <span style={{ color: '#10B981' }}>{Math.round(stats.hourlyRemainPercent)}%</span>
                </Descriptions.Item>
                <Descriptions.Item label="本周已用">
                  <span style={{ color: '#F8FAFC', fontWeight: 600 }}>
                    {Math.round(stats.weeklyUsedPercent)}%
                  </span>
                  （共 {stats.weeklyTotal} 次）
                </Descriptions.Item>
                <Descriptions.Item label="本周剩余">
                  <span style={{ color: '#10B981' }}>{Math.round(stats.weeklyRemainPercent)}%</span>
                </Descriptions.Item>
              </Descriptions>

              {/* 每个模型的详情 */}
              <h4 style={{ color: '#F8FAFC', marginBottom: 16 }}>模型详情</h4>
              {stats.modelRemains.map((item: any, idx: number) => (
                <div 
                  key={idx}
                  style={{
                    marginBottom: 16,
                    padding: 16,
                    background: 'rgba(15, 23, 42, 0.5)',
                    borderRadius: 8,
                    border: '1px solid rgba(148, 163, 184, 0.2)',
                  }}
                >
                  <div style={{ 
                    color: '#3B82F6', 
                    fontWeight: 600, 
                    marginBottom: 12,
                    fontSize: 14 
                  }}>
                    模型: {item.model_name || 'unknown'}
                  </div>
                  
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="当前周期已用">
                      {item.current_interval_usage_count || 0}
                    </Descriptions.Item>
                    <Descriptions.Item label="当前周期总数">
                      {item.current_interval_total_count || 0}
                    </Descriptions.Item>
                    <Descriptions.Item label="当前周期剩余">
                      <span style={{ color: '#10B981' }}>
                        {item.current_interval_remaining_percent || 0}%
                      </span>
                    </Descriptions.Item>
                    <Descriptions.Item label="当前周期剩余时间">
                      {formatRemainTime(item.remains_time || 0)}
                    </Descriptions.Item>
                    <Descriptions.Item label="本周已用">
                      {item.current_weekly_usage_count || 0}
                    </Descriptions.Item>
                    <Descriptions.Item label="本周总数">
                      {item.current_weekly_total_count || 0}
                    </Descriptions.Item>
                    <Descriptions.Item label="本周剩余">
                      <span style={{ color: '#10B981' }}>
                        {item.current_weekly_remaining_percent || 0}%
                      </span>
                    </Descriptions.Item>
                    <Descriptions.Item label="本周剩余时间">
                      {formatRemainTime(item.weekly_remains_time || 0)}
                    </Descriptions.Item>
                  </Descriptions>
                </div>
              ))}
              
              {quota?.hourly?.last_sync && (
                <div style={{ color: '#64748B', fontSize: 12, marginTop: 16 }}>
                  最后同步时间: {formatDateTime(quota.hourly.last_sync)}
                </div>
              )}
            </div>
          )
        })()}
      </Modal>

      {/* 添加供应商弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            添加供应商
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label={<span style={{ color: '#94A3B8' }}>供应商名称</span>} rules={[{ required: true }]}>
            <Input placeholder="如：火山方舟" />
          </Form.Item>
          <Form.Item name="type" label={<span style={{ color: '#94A3B8' }}>类型</span>} rules={[{ required: true }]}>
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="google">Google</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="minimax">MiniMax 稀宇</Select.Option>
              <Select.Option value="deepseek">DeepSeek 深度求索</Select.Option>
              <Select.Option value="zhipu">智谱清言</Select.Option>
              <Select.Option value="cohere">Cohere</Select.Option>
              <Select.Option value="mistral">Mistral</Select.Option>
              <Select.Option value="bedrock">AWS Bedrock</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label={<span style={{ color: '#94A3B8' }}>API端点</span>} rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label={<span style={{ color: '#94A3B8' }}>API Key</span>} rules={[{ required: true }]}>
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label={<span style={{ color: '#94A3B8' }}>优先级</span>} initialValue={100}>
                <InputNumber min={1} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label={<span style={{ color: '#94A3B8' }}>超时时间(秒)</span>} initialValue={60}>
                <InputNumber min={10} max={300} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_hourly" label={<span style={{ color: '#94A3B8' }}>5小时额度</span>}>
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_weekly" label={<span style={{ color: '#94A3B8' }}>周额度</span>}>
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setModalVisible(false)} style={{ borderRadius: 10 }}>
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                style={{
                  background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                  border: 'none',
                  borderRadius: 10,
                }}
              >
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑供应商弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            编辑供应商
          </span>
        }
        open={!!editProvider}
        onCancel={() => {
          setEditProvider(null)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="name" label={<span style={{ color: '#94A3B8' }}>供应商名称</span>} rules={[{ required: true }]}>
            <Input placeholder="如：火山方舟" />
          </Form.Item>
          <Form.Item name="type" label={<span style={{ color: '#94A3B8' }}>类型</span>} rules={[{ required: true }]}>
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="google">Google</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="minimax">MiniMax 稀宇</Select.Option>
              <Select.Option value="deepseek">DeepSeek 深度求索</Select.Option>
              <Select.Option value="zhipu">智谱清言</Select.Option>
              <Select.Option value="cohere">Cohere</Select.Option>
              <Select.Option value="mistral">Mistral</Select.Option>
              <Select.Option value="bedrock">AWS Bedrock</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label={<span style={{ color: '#94A3B8' }}>API端点</span>} rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label={<span style={{ color: '#94A3B8' }}>API Key（留空则不修改）</span>}>
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label={<span style={{ color: '#94A3B8' }}>优先级</span>}>
                <InputNumber min={1} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label={<span style={{ color: '#94A3B8' }}>超时时间(秒)</span>}>
                <InputNumber min={10} max={300} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_hourly" label={<span style={{ color: '#94A3B8' }}>5小时额度</span>}>
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_weekly" label={<span style={{ color: '#94A3B8' }}>周额度</span>}>
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="status" label={<span style={{ color: '#94A3B8' }}>状态</span>}>
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="active">启用</Select.Option>
          <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setEditProvider(null)} style={{ borderRadius: 10 }}>
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                style={{
                  background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                  border: 'none',
                  borderRadius: 10,
                }}
              >
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ProvidersPage
