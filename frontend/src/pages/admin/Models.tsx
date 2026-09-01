import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, Popconfirm, Tabs, Row, Col, InputNumber, Radio, Checkbox
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, DollarOutlined, SettingOutlined, CloudDownloadOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, ModelMapping } from '../../api/models'
import { getProviders, Provider, syncProviderModels } from '../../api/providers'

// 上游模型类型
interface UpstreamModel {
  model_id: string
  name: string
  owned_by: string
}

const ModelsPage = () => {
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<ModelMapping[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editModel, setEditModel] = useState<ModelMapping | null>(null)
  const [form] = Form.useForm()
  const [priceType, setPriceType] = useState<string>('token')
  const message = useMessage()

  // 获取模型弹窗状态
  const [fetchModalVisible, setFetchModalVisible] = useState(false)
  const [selectedProviderId, setSelectedProviderId] = useState<string>('')
  const [upstreamModels, setUpstreamModels] = useState<UpstreamModel[]>([])
  const [fetchLoading, setFetchLoading] = useState(false)
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 })

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
      setModalVisible(false)
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
    setModalVisible(true)
    // 延迟设置表单值，确保 Modal 已打开
    setTimeout(() => {
      form.setFieldsValue({
        ...model,
        aliases: typeof model.aliases === 'string' ? JSON.parse(model.aliases) : model.aliases
      })
    }, 0)
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

  // 打开获取模型弹窗
  const openFetchModal = () => {
    setFetchModalVisible(true)
    setSelectedProviderId('')
    setUpstreamModels([])
    setSelectedModels([])
  }

  // 选择供应商后拉取上游模型
  const handleSelectProvider = async (providerId: string) => {
    setSelectedProviderId(providerId)
    setFetchLoading(true)
    setSelectedModels([])
    
    try {
      // 调用同步模型API
      const result = await syncProviderModels(providerId)
      if (result.success && result.models) {
        // 从Provider数据中获取模型列表
        const provider = providers.find(p => p.provider_id === providerId)
        if (provider && provider.models) {
          setUpstreamModels(provider.models)
          setPagination({ ...pagination, total: provider.models.length })
        } else {
          setUpstreamModels([])
          setPagination({ ...pagination, total: 0 })
        }
        message.success(`成功获取 ${result.count} 个模型`)
      } else {
        message.error(result.message || '获取模型失败')
        setUpstreamModels([])
      }
    } catch (error) {
      message.error('获取模型失败')
      setUpstreamModels([])
    } finally {
      setFetchLoading(false)
    }
  }

  // 分页变化
  const handlePageChange = (page: number, pageSize: number) => {
    setPagination({ ...pagination, current: page, pageSize })
  }

  // 选择模型
  const handleSelectModel = (modelId: string, checked: boolean) => {
    if (checked) {
      setSelectedModels([...selectedModels, modelId])
    } else {
      setSelectedModels(selectedModels.filter(id => id !== modelId))
    }
  }

  // 全选
  const handleSelectAll = (checked: boolean, currentPageModels: UpstreamModel[]) => {
    if (checked) {
      const allIds = currentPageModels.map(m => m.model_id)
      setSelectedModels([...new Set([...selectedModels, ...allIds])])
    } else {
      // 取消当前页的全选
      const currentPageIds = currentPageModels.map(m => m.model_id)
      setSelectedModels(selectedModels.filter(id => !currentPageIds.includes(id)))
    }
  }

  // 批量创建模型
  const handleBatchCreate = async () => {
    if (selectedModels.length === 0) {
      message.warning('请选择要添加的模型')
      return
    }

    const provider = providers.find(p => p.provider_id === selectedProviderId)
    if (!provider) {
      message.error('供应商不存在')
      return
    }

    try {
      let successCount = 0
      for (const modelId of selectedModels) {
        const model = upstreamModels.find(m => m.model_id === modelId)
        if (!model) continue

        // 生成平台模型ID
        const platformModelId = `${provider.type}-${modelId}`
        
        // 检查是否已存在
        const existing = models.find(m => m.model_id === platformModelId)
        if (existing) continue

        await createModel({
          // @ts-ignore
          model_id: platformModelId,
          display_name: model.name || modelId,
          provider_id: provider.provider_id,
          provider_model: modelId,
          price_type: 'token',
          price_per_1k_input: 0,
          price_per_1k_output: 0,
          price_per_request: 0,
          status: 'active'
        })
        successCount++
      }

      message.success(`成功添加 ${successCount} 个模型`)
      setFetchModalVisible(false)
      setSelectedModels([])
      fetchData()
    } catch (error) {
      message.error('批量创建失败')
    }
  }

  // 获取当前页的模型
  const getCurrentPageModels = () => {
    const start = (pagination.current - 1) * pagination.pageSize
    const end = start + pagination.pageSize
    return upstreamModels.slice(start, end)
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
        <Space>
          <Button 
            icon={<CloudDownloadOutlined />} 
            onClick={openFetchModal}
            style={{ borderRadius: 10 }}
          >
            获取模型
          </Button>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={openCreateModal}
            style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none', borderRadius: 10 }}
          >
            添加模型
          </Button>
        </Space>
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
              width: 200,
              render: (_: any, record: ModelMapping) => (
                <div>
                  
                  <div style={{ color: '#F8FAFC', fontWeight: 500 }}>{record.display_name}</div>
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
              width: 250,
              render: (_: any, record: ModelMapping) => (
                <div style={{ color: '#F59E0B' }}>
                  <DollarOutlined style={{ marginRight: 4 }} />
                  {formatPrice(record)}
                </div>
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
              width: 150,
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
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total: number) => `共 ${total} 条`,
            pageSize: 20
          }}
        />
      </div>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={<span style={{ color: '#F8FAFC' }}>{editModel ? '编辑模型' : '创建模型'}</span>}
        open={modalVisible}
        onCancel={() => { setModalVisible(false); setEditModel(null); form.resetFields(); }}
        footer={null}
        width={700}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={editModel ? handleUpdate : handleCreate}
          initialValues={{
            status: 'active',
            price_type: 'token',
            price_per_1k_input: 0,
            price_per_1k_output: 0,
            price_per_request: 0
          }}
        >
          <Tabs 
            defaultActiveKey="basic" 
            items={[
              {
                key: 'basic',
                label: <span><SettingOutlined /> 基本配置</span>,
                children: (
                  <>
                    <Form.Item name="provider_id" label={<span style={{ color: '#94A3B8' }}>供应商</span>} rules={[{ required: true, message: '请选择供应商' }]}>
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

                    <Form.Item name="status" label={<span style={{ color: '#94A3B8' }}>状态</span>}>
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
                    <Form.Item name="price_type" label={<span style={{ color: '#94A3B8' }}>计费方式</span>}>
                      <Radio.Group onChange={(e) => setPriceType(e.target.value)}>
                        <Radio value="token">按Token计费</Radio>
                        <Radio value="request">按请求次数计费</Radio>
                      </Radio.Group>
                    </Form.Item>

                    {priceType === 'token' ? (
                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_input" label={<span style={{ color: '#94A3B8' }}>每千输入Token价格(元)</span>}>
                            <InputNumber min={0} step={0.0001} precision={4} style={{ width: '100%' }} placeholder="0.001" />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_output" label={<span style={{ color: '#94A3B8' }}>每千输出Token价格(元)</span>}>
                            <InputNumber min={0} step={0.0001} precision={4} style={{ width: '100%' }} placeholder="0.002" />
                          </Form.Item>
                        </Col>
                      </Row>
                    ) : (
                      <Form.Item name="price_per_request" label={<span style={{ color: '#94A3B8' }}>每次请求价格(元)</span>}>
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

      {/* 获取模型弹窗 */}
      <Modal
        title={<span style={{ color: '#F8FAFC' }}><CloudDownloadOutlined style={{ marginRight: 8 }} />获取模型</span>}
        open={fetchModalVisible}
        onCancel={() => { setFetchModalVisible(false); setSelectedProviderId(''); setUpstreamModels([]); setSelectedModels([]); }}
        footer={null}
        width={900}
      >
        <div style={{ marginBottom: 16 }}>
          <span style={{ color: '#94A3B8', marginRight: 8 }}>选择供应商：</span>
          <Select 
            style={{ width: 300 }}
            placeholder="请选择供应商"
            value={selectedProviderId || undefined}
            onChange={handleSelectProvider}
          >
            {providers.filter(p => p.status === 'active').map(p => (
              <Select.Option key={p.provider_id} value={p.provider_id}>
                {p.name} ({p.type})
              </Select.Option>
            ))}
          </Select>
        </div>

        {upstreamModels.length > 0 ? (
          <>
            <Table
              dataSource={getCurrentPageModels()}
              columns={[
                {
                  title: <Checkbox 
                    onChange={(e) => handleSelectAll(e.target.checked, getCurrentPageModels())}
                    checked={getCurrentPageModels().every(m => selectedModels.includes(m.model_id))}
                    indeterminate={getCurrentPageModels().some(m => selectedModels.includes(m.model_id)) && !getCurrentPageModels().every(m => selectedModels.includes(m.model_id))}
                  />,
                  key: 'checkbox',
                  width: 50,
                  render: (_: any, record: UpstreamModel) => (
                    <Checkbox 
                      checked={selectedModels.includes(record.model_id)}
                      onChange={(e) => handleSelectModel(record.model_id, e.target.checked)}
                    />
                  )
                },
                { 
                  title: '模型ID', 
                  dataIndex: 'model_id', 
                  key: 'model_id',
                  render: (text: string) => <span style={{ color: '#F8FAFC' }}>{text}</span>
                },
                { 
                  title: '模型名称', 
                  dataIndex: 'name', 
                  key: 'name',
                  render: (text: string) => <span style={{ color: '#94A3B8' }}>{text || '-'}</span>
                },
              ]}
              rowKey="model_id"
              loading={fetchLoading}
              pagination={{
                current: pagination.current,
                pageSize: pagination.pageSize,
                total: pagination.total,
                onChange: handlePageChange,
                showSizeChanger: true,
                showTotal: (total: number) => `共 ${total} 个模型`
              }}
              size="small"
            />
            
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ color: '#94A3B8' }}>
                已选择 <span style={{ color: '#3B82F6', fontWeight: 600 }}>{selectedModels.length}</span> 个模型
              </div>
              <Space>
                <Button onClick={() => setFetchModalVisible(false)}>取消</Button>
                <Button 
                  type="primary" 
                  onClick={handleBatchCreate}
                  disabled={selectedModels.length === 0}
                  style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none' }}
                >
                  批量创建 ({selectedModels.length})
                </Button>
              </Space>
            </div>
          </>
        ) : selectedProviderId && !fetchLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#94A3B8' }}>
            该供应商暂无模型，请确保供应商配置正确
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#94A3B8' }}>
            请先选择供应商
          </div>
        )}
      </Modal>
    </div>
  )
}

export default ModelsPage
