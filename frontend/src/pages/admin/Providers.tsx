import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, 
  Select, Popconfirm, Card, Row, Col, Progress 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CloudOutlined } from '@ant-design/icons'
import { 
  getProviders, createProvider, updateProvider, deleteProvider,
  getAllProviderQuotas, syncProviderQuota, Provider, 
} from '../../api/providers'

const ProvidersPage = () => {
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [quotas, setQuotas] = useState<any>({})
  const [modalVisible, setModalVisible] = useState(false)
  const [editProvider, setEditProvider] = useState<Provider | null>(null)
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
      
      // 构建配额映射
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

  const cardStyle = {
    background: 'rgba(17, 24, 39, 0.6)',
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: 16,
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

      {/* 配额概览卡片 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 24 }}>
        {providers.map(provider => {
          const quota = quotas[provider.provider_id]
          return (
            <Col xs={24} lg={8} key={provider.provider_id}>
              <Card 
                title={
                  <Space>
                    <span style={{ color: '#F8FAFC', fontWeight: 600 }}>
                      {provider.name}
                    </span>
                    <Tag 
                      color={provider.status === 'active' ? 'success' : 'error'}
                      style={{ 
                        borderRadius: '6px',
                        background: provider.status === 'active' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(220, 38, 38, 0.15)',
                        border: 'none',
                      }}
                    >
                      {provider.status === 'active' ? '启用' : '禁用'}
                    </Tag>
                  </Space>
                }
                extra={
                  <Space>
                    <Button 
                      size="small" 
                      icon={<SyncOutlined />} 
                      onClick={() => handleSync(provider.provider_id)}
                      style={{ borderRadius: 6 }}
                    >
                      同步
                    </Button>
                  </Space>
                }
                style={cardStyle}
              >
                {quota ? (
                  <>
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ color: '#94A3B8', marginBottom: 8 }}>5小时用量</div>
                      <Progress 
                        percent={Math.round(quota.hourly?.percent || 0)} 
                        status={quota.hourly?.percent > 90 ? 'exception' : 'normal'}
                        strokeColor={{
                          '0%': '#2563EB',
                          '100%': '#3B82F6',
                        }}
                        trailColor="rgba(30, 41, 59, 0.8)"
                      />
                      <div style={{ fontSize: 13, color: '#94A3B8', marginTop: 8 }}>
                        {quota.hourly?.used?.toLocaleString()} / {quota.hourly?.limit?.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div style={{ color: '#94A3B8', marginBottom: 8 }}>周用量</div>
                      <Progress 
                        percent={Math.round(quota.weekly?.percent || 0)}
                        status={quota.weekly?.percent > 90 ? 'exception' : 'normal'}
                        strokeColor={{
                          '0%': '#2563EB',
                          '100%': '#3B82F6',
                        }}
                        trailColor="rgba(30, 41, 59, 0.8)"
                      />
                      <div style={{ fontSize: 13, color: '#94A3B8', marginTop: 8 }}>
                        {quota.weekly?.used?.toLocaleString()} / {quota.weekly?.limit?.toLocaleString()}
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ color: '#64748B', textAlign: 'center', padding: '20px 0' }}>
                    暂无配额信息
                  </div>
                )}
              </Card>
            </Col>
          )
        })}
      </Row>

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
              title: '端点', 
              dataIndex: 'endpoint', 
              key: 'endpoint',
              render: (text: string) => (
                <span style={{ 
                  fontFamily: "'Space Grotesk', monospace", 
                  fontSize: 12, 
                  color: '#64748B' 
                }}>
                  {text?.substring(0, 40)}...
                </span>
              )
            },
            { 
              title: '优先级', 
              dataIndex: 'priority', 
              key: 'priority',
              render: (val: number) => (
                <span style={{ 
                  fontFamily: "'Space Grotesk', sans-serif", 
                  color: '#CBD5E1' 
                }}>
                  {val}
                </span>
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
              title: '操作',
              key: 'action',
              render: (_: any, record: Provider) => (
                <Space>
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
