import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, Popconfirm, Tabs, Card, Row, Col, InputNumber, Radio, Tooltip
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, DollarOutlined, SettingOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, ModelMapping } from '../../api/models'
import { getProviders, Provider } from '../../api/providers'

const ModelsPage = () => {
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<ModelMapping[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editModel, setEditModel] = useState<ModelMapping | null>(null)
  const [form] = Form.useForm()
  const [priceType, setPriceType] = useState<string>('token')
  const message = useMessage()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [modelsData, providersData] = await Promise.all([
        getModels(),
        getProviders()
      ])
      setModels(modelsData.items || [])
      setProviders(providersData.items || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createModel(values)
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      setPriceType('token')
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleUpdate = async (values: any) => {
    if (!editModel) return
    try {
      await updateModel(editModel.model_id, values)
      message.success('更新成功')
      setEditModel(null)
      form.resetFields()
      setPriceType('token')
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleDelete = async (modelId: string) => {
    try {
      await deleteModel(modelId)
      message.success('删除成功')
      fetchData()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const openEditModal = (model: ModelMapping) => {
    setEditModel(model)
    setPriceType(model.price_type || 'token')
    form.setFieldsValue({
      ...model,
      aliases: typeof model.aliases === 'string' ? JSON.parse(model.aliases) : model.aliases
    })
  }

  const openCreateModal = () => {
    setEditModel(null)
    form.resetFields()
    setPriceType('token')
    setModalVisible(true)
  }

  // 获取供应商名称
  const getProviderName = (providerId: string) => {
    const provider = providers.find(p => p.provider_id === providerId)
    return provider?.name || providerId
  }

  // 格式化价格显示
  const formatPrice = (model: ModelMapping) => {
    if (model.price_type === 'request') {
      return `¥${model.price_per_request}/次`
    }
    const inputPrice = model.price_per_1k_input || 0
    const outputPrice = model.price_per_1k_output || 0
    return `¥${inputPrice}/1K输入 · ¥${outputPrice}/1K输出`
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
          <AppstoreOutlined style={{ marginRight: 12, color: '#3B82F6' }} />
          模型管理
        </h2>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={openCreateModal}
          style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none', borderRadius: 10 }}
        >
          添加模型
        </Button>
      </div>

      {/* 模型列表 */}
      <div style={{
        background: 'rgba(17, 24, 39, 0.6)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        overflow: 'hidden',
      }}>
        <Table
          dataSource={models}
          columns={[
            { 
              title: '平台模型', 
              dataIndex: 'model_id', 
              key: 'model_id',
              render: (text: string, record: ModelMapping) => (
                <div>
                  <div style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</div>
                  <div style={{ color: '#64748B', fontSize: 12 }}>{record.display_name}</div>
                </div>
              )
            },
            { 
              title: '供应商', 
              dataIndex: 'provider_id', 
              key: 'provider_id',
              render: (id: string) => (
                <Tag color="blue" style={{ borderRadius: 6 }}>{getProviderName(id)}</Tag>
              )
            },
            { 
              title: '上游模型', 
              dataIndex: 'provider_model', 
              key: 'provider_model',
              render: (text: string) => <span style={{ color: '#10B981' }}>{text}</span>
            },
            { 
              title: '定价', 
              key: 'price',
              render: (_: any, record: ModelMapping) => (
                <Tooltip title={record.price_type === 'token' ? '每千token价格' : '每次请求价格'}>
                  <div style={{ display: 'flex', alignItems: 'center', color: '#F59E0B' }}>
                    <DollarOutlined style={{ marginRight: 4 }} />
                    {formatPrice(record)}
                  </div>
                </Tooltip>
              )
            },
            { 
              title: '状态', 
              dataIndex: 'status', 
              key: 'status',
              render: (status: string) => (
                <Tag 
                  color={status === 'active' ? 'success' : 'default'}
                  style={{ borderRadius: 6 }}
                >
                  {status === 'active' ? '启用' : '禁用'}
                </Tag>
              )
            },
            {
              title: '操作',
              key: 'action',
              render: (_: any, record: ModelMapping) => (
                <Space>
                  <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(record)} style={{ color: '#3B82F6' }}>编辑</Button>
                  <Popconfirm title="确认删除此模型？" onConfirm={() => handleDelete(record.model_id)}>
                    <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </Space>
              )
            }
          ]}
          rowKey="model_id"
          loading={loading}
          pagination={{ 
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个模型`
          }}
        />
      </div>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={
          <span style={{ color: '#F8FAFC' }}>
            <AppstoreOutlined style={{ marginRight: 8 }} />
            {editModel ? '编辑模型' : '添加模型'}
          </span>
        }
        open={modalVisible || !!editModel}
        onCancel={() => { setModalVisible(false); setEditModel(null); form.resetFields(); }}
        footer={null}
        width={640}
      >
        <Form 
          form={form} 
          onFinish={editModel ? handleUpdate : handleCreate}
          layout="vertical"
        >
          <Tabs 
            defaultActiveKey="basic" 
            items={[
              {
                key: 'basic',
                label: <span><SettingOutlined /> 基本信息</span>,
                children: (
                  <>
                    <Form.Item name="provider_id" label={<span style={{ color: '#94A3B8' }}>选择供应商</span>} rules={[{ required: true, message: '请选择供应商' }]}>
                      <Select placeholder="选择供应商">
                        {providers.map(p => (
                          <Select.Option key={p.provider_id} value={p.provider_id}>{p.name} ({p.type})</Select.Option>
                        ))}
                      </Select>
                    </Form.Item>

                    <Form.Item name="provider_model" label={<span style={{ color: '#94A3B8' }}>上游模型ID</span>} rules={[{ required: true, message: '请输入上游模型ID' }]}>
                      <Input placeholder="如: gpt-4o, claude-3-opus" />
                    </Form.Item>

                    <Form.Item name="display_name" label={<span style={{ color: '#94A3B8' }}>显示名称</span>} rules={[{ required: true, message: '请输入显示名称' }]}>
                      <Input placeholder="如: GPT-4o" />
                    </Form.Item>

                    <Form.Item name="description" label={<span style={{ color: '#94A3B8' }}>模型描述（可选）</span>}>
                      <Input.TextArea rows={2} placeholder="描述这个模型的用途和特点" />
                    </Form.Item>

                    <Form.Item name="aliases" label={<span style={{ color: '#94A3B8' }}>别名（可选，多个用逗号分隔）</span>}>
                      <Input placeholder="如: gpt4, gpt-4o" />
                    </Form.Item>

                    <Form.Item name="status" label={<span style={{ color: '#94A3B8' }}>状态</span>} initialValue="active">
                      <Radio.Group>
                        <Radio value="active">启用</Radio>
                        <Radio value="disabled">禁用</Radio>
                      </Radio.Group>
                    </Form.Item>
                  </>
                )
              },
              {
                key: 'pricing',
                label: <span><DollarOutlined /> 定价配置</span>,
                children: (
                  <>
                    <Form.Item name="price_type" label={<span style={{ color: '#94A3B8' }}>计费方式</span>} initialValue="token">
                      <Radio.Group onChange={(e) => setPriceType(e.target.value)}>
                        <Radio value="token">按Token计费</Radio>
                        <Radio value="request">按请求次数计费</Radio>
                      </Radio.Group>
                    </Form.Item>

                    {priceType === 'token' ? (
                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_input" label={<span style={{ color: '#94A3B8' }}>每千输入Token价格(元)</span>} initialValue={0}>
                            <InputNumber min={0} step={0.0001} precision={4} style={{ width: '100%' }} placeholder="0.001" />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_output" label={<span style={{ color: '#94A3B8' }}>每千输出Token价格(元)</span>} initialValue={0}>
                            <InputNumber min={0} step={0.0001} precision={4} style={{ width: '100%' }} placeholder="0.002" />
                          </Form.Item>
                        </Col>
                      </Row>
                    ) : (
                      <Form.Item name="price_per_request" label={<span style={{ color: '#94A3B8' }}>每次请求价格(元)</span>} initialValue={0}>
                        <InputNumber min={0} step={0.01} precision={2} style={{ width: '100%' }} placeholder="0.01" />
                      </Form.Item>
                    )}

                    <div style={{ padding: 16, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8, marginTop: 16 }}>
                      <div style={{ color: '#3B82F6', fontSize: 13, marginBottom: 8 }}>💡 计费说明</div>
                      <div style={{ color: '#94A3B8', fontSize: 12 }}>
                        {priceType === 'token' 
                          ? '按Token计费：根据实际消耗的输入和输出token数量分别计费'
                          : '按请求计费：每次API调用收取固定费用，不区分输入输出'
                        }
                      </div>
                    </div>
                  </>
                )
              }
            ]}
          />
          
          <Form.Item style={{ marginTop: 24, marginBottom: 0 }}>
            <Space>
              <Button onClick={() => { setModalVisible(false); setEditModel(null); form.resetFields(); }}>取消</Button>
              <Button type="primary" htmlType="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none' }}>
                {editModel ? '保存' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelsPage
