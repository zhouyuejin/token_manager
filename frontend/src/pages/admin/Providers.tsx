import { useState, useEffect } from 'react'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, 
  Select, message, Popconfirm, Card, Row, Col, Progress 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined } from '@ant-design/icons'
import { 
  getProviders, createProvider, updateProvider, deleteProvider,
  getAllProviderQuotas, syncProviderQuota, Provider, ProviderQuota 
} from '../../api/providers'

const ProvidersPage = () => {
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [quotas, setQuotas] = useState<any>({})
  const [modalVisible, setModalVisible] = useState(false)
  const [editProvider, setEditProvider] = useState<Provider | null>(null)
  const [form] = Form.useForm()

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

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy': return '#52c41a'
      case 'degraded': return '#faad14'
      case 'unhealthy': return '#ff4d4f'
      default: return '#8c8c8c'
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>供应商管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          添加供应商
        </Button>
      </div>

      {/* 配额概览卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {providers.map(provider => {
          const quota = quotas[provider.provider_id]
          return (
            <Col span={8} key={provider.provider_id}>
              <Card 
                title={
                  <Space>
                    {provider.name}
                    <Tag color={provider.status === 'active' ? 'green' : 'red'}>
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
                    >
                      同步
                    </Button>
                  </Space>
                }
              >
                {quota ? (
                  <>
                    <div style={{ marginBottom: 16 }}>
                      <div>5小时用量</div>
                      <Progress 
                        percent={Math.round(quota.hourly?.percent || 0)} 
                        status={quota.hourly?.percent > 90 ? 'exception' : 'normal'}
                      />
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                        {quota.hourly?.used?.toLocaleString()} / {quota.hourly?.limit?.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div>周用量</div>
                      <Progress 
                        percent={Math.round(quota.weekly?.percent || 0)}
                        status={quota.weekly?.percent > 90 ? 'exception' : 'normal'}
                      />
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                        {quota.weekly?.used?.toLocaleString()} / {quota.weekly?.limit?.toLocaleString()}
                      </div>
                    </div>
                  </>
                ) : (
                  <div style={{ color: '#8c8c8c' }}>未配置配额</div>
                )}
              </Card>
            </Col>
          )
        })}
      </Row>

      <Table
        dataSource={providers}
        columns={[
          { title: '供应商', dataIndex: 'name', key: 'name' },
          { title: '类型', dataIndex: 'type', key: 'type' },
          { title: '端点', dataIndex: 'endpoint', key: 'endpoint', ellipsis: true },
          { title: '优先级', dataIndex: 'priority', key: 'priority' },
          { 
            title: '健康状态', 
            dataIndex: 'health_status', 
            key: 'health_status',
            render: (status: string) => (
              <Tag color={getHealthColor(status)}>
                {status === 'healthy' ? '正常' : status === 'degraded' ? '降级' : '异常'}
              </Tag>
            )
          },
          {
            title: '操作',
            key: 'action',
            render: (_: any, record: Provider) => (
              <Space>
                <Button 
                  type="link" 
                  icon={<EditOutlined />}
                  onClick={() => openEditModal(record)}
                >
                  编辑
                </Button>
                <Popconfirm
                  title="确认删除此供应商？"
                  onConfirm={() => handleDelete(record.provider_id)}
                >
                  <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              </Space>
            )
          }
        ]}
        rowKey="provider_id"
        loading={loading}
      />

      {/* 添加供应商弹窗 */}
      <Modal
        title="添加供应商"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label="供应商名称" rules={[{ required: true }]}>
            <Input placeholder="如：火山方舟" />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label="API端点" rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label="优先级" initialValue={100}>
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label="超时时间(秒)" initialValue={60}>
                <InputNumber min={10} max={300} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_hourly" label="5小时额度">
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_weekly" label="周额度">
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item>
            <Space>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑供应商弹窗 */}
      <Modal
        title="编辑供应商"
        open={!!editProvider}
        onCancel={() => {
          setEditProvider(null)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="name" label="供应商名称" rules={[{ required: true }]}>
            <Input placeholder="如：火山方舟" />
          </Form.Item>
          <Form.Item name="type" label="类型" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label="API端点" rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key（留空则不修改）">
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label="优先级">
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label="超时时间(秒)">
                <InputNumber min={10} max={300} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_hourly" label="5小时额度">
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_weekly" label="周额度">
                <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setEditProvider(null)}>取消</Button>
              <Button type="primary" htmlType="submit">保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ProvidersPage
