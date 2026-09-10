import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, Popconfirm, Tabs, Row, Col, InputNumber, Radio, Checkbox,
  Drawer, Switch, Divider
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, DollarOutlined, SettingOutlined, CloudDownloadOutlined, LinkOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, ModelMapping, ModelChannel, getModelChannels, bindChannelToModel, unbindChannel, updateModelChannel } from '../../api/models'
import { useSwrData } from '../../hooks/useSwr'
import { getChannels, Channel, syncChannelModels } from '../../api/channels'

// 上游模型类型
interface UpstreamModel {
  model_id: string
  name?: string        // 旧格式
  owned_by?: string    // 旧格式
  model_name?: string  // 新格式
  display_name?: string // 新格式
}

const ModelsPage = () => {
  const [loading, setLoading] = useState(false)
    const [modalVisible, setModalVisible] = useState(false)
  const [editModel, setEditModel] = useState<ModelMapping | null>(null)
  const [form] = Form.useForm()
  const [priceType, setPriceType] = useState<string>('token')
  const message = useMessage()
  const { token, isDark } = useThemeToken()

  // 获取模型弹窗状态
  const [fetchModalVisible, setFetchModalVisible] = useState(false)
  const [selectedChannelId, setSelectedChannelId] = useState<string>('')
  const [upstreamModels, setUpstreamModels] = useState<UpstreamModel[]>([])
  const [fetchLoading, setFetchLoading] = useState(false)
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 })

  // 渠道绑定 Drawer 状态
  const [bindingsDrawerOpen, setBindingsDrawerOpen] = useState(false)
  const [bindingsTarget, setBindingsTarget] = useState<ModelMapping | null>(null)
  const [bindings, setBindings] = useState<ModelChannel[]>([])
  const [bindingsLoading, setBindingsLoading] = useState(false)
  const [bindingFormOpen, setBindingFormOpen] = useState(false)
  const [editingBinding, setEditingBinding] = useState<ModelChannel | null>(null)
  const [bindingForm] = Form.useForm()

  // 使用 SWR 获取数据和渠道
  const { data: modelsData, mutate: mutateModels } = useSwrData<{total: number; items: ModelMapping[]}>('/admin/models')
  const { data: channelsData, mutate: mutateChannels } = useSwrData<{total: number; items: Channel[]}>('/admin/channels')
  
  const modelsList = modelsData?.items || []
  const channelsList = channelsData?.items || []

  const fetchData = async () => {
    mutateModels()
    mutateChannels()
  }

  const handleCreate = async (values: any) => {
    try {
      await createModel(parseAliases(values))
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
      await updateModel(editModel.model_id, parseAliases(values))
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

  // aliases 表单上是逗号分隔字符串（如 "gpt4, gpt-4o"），后端 ModelCreate 要求 List[str]。
  // 空串 → 删字段；否则按逗号拆分并去空白；任一解析失败都抛错。
  const parseAliases = (values: any) => {
    const payload = { ...values }
    if (typeof payload.aliases !== 'string') return payload
    const trimmed = payload.aliases.trim()
    if (!trimmed) {
      delete payload.aliases
      return payload
    }
    const list = trimmed.split(',').map((s) => s.trim()).filter(Boolean)
    payload.aliases = list
    return payload
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

  // ===== 渠道绑定管理 =====
  const openBindingsDrawer = async (record: ModelMapping) => {
    setBindingsTarget(record)
    setBindingsDrawerOpen(true)
    setBindingsLoading(true)
    try {
      const list = await getModelChannels(record.model_id)
      setBindings(list)
    } catch (e) {
      message.error('加载绑定失败')
    } finally {
      setBindingsLoading(false)
    }
  }

  const closeBindingsDrawer = () => {
    setBindingsDrawerOpen(false)
    setBindingsTarget(null)
    setBindings([])
  }

  const reloadBindings = async () => {
    if (!bindingsTarget) return
    setBindingsLoading(true)
    try {
      const list = await getModelChannels(bindingsTarget.model_id)
      setBindings(list)
      fetchData() // 刷新列表中的 bound_channels_count
    } catch (e) {
      message.error('刷新失败')
    } finally {
      setBindingsLoading(false)
    }
  }

  const openAddBinding = () => {
    setEditingBinding(null)
    bindingForm.resetFields()
    bindingForm.setFieldsValue({ priority: 0, weight: 100, enabled: true })
    setBindingFormOpen(true)
  }

  const openEditBinding = (b: ModelChannel) => {
    setEditingBinding(b)
    bindingForm.setFieldsValue({
      channel_id: b.channel_id,
      upstream_model: b.upstream_model,
      priority: b.priority,
      weight: b.weight,
      enabled: b.enabled,
    })
    setBindingFormOpen(true)
  }

  const submitBinding = async () => {
    if (!bindingsTarget) return
    try {
      const values = await bindingForm.validateFields()
      if (editingBinding) {
        await updateModelChannel(bindingsTarget.model_id, editingBinding.channel_id, {
          upstream_model: values.upstream_model,
          priority: values.priority,
          weight: values.weight,
          enabled: values.enabled,
        })
        message.success('绑定已更新')
      } else {
        if (bindings.some(b => b.channel_id === values.channel_id)) {
          message.error('该渠道已绑定到此模型')
          return
        }
        await bindChannelToModel(bindingsTarget.model_id, values)
        message.success('绑定已添加')
      }
      setBindingFormOpen(false)
      reloadBindings()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e?.response?.data?.detail || '操作失败')
    }
  }

  const handleUnbind = async (b: ModelChannel) => {
    if (!bindingsTarget) return
    try {
      await unbindChannel(bindingsTarget.model_id, b.channel_id)
      message.success('已解绑')
      reloadBindings()
    } catch (e) {
      message.error('解绑失败')
    }
  }

  const handleToggleBinding = async (b: ModelChannel, enabled: boolean) => {
    if (!bindingsTarget) return
    try {
      await updateModelChannel(bindingsTarget.model_id, b.channel_id, { enabled })
      reloadBindings()
    } catch (e) {
      message.error('更新失败')
    }
  }


  // 获取渠道名称
  const getChannelName = (channelId: string) => {
    const channel = channelsList.find(p => p.channel_id === channelId)
    return channel?.name || channelId
  }

  // 格式化价格显示
  const formatPrice = (model: ModelMapping) => {
    if (model.price_type === 'request') {
      return `$${model.price_per_request}/次`
    }
    const inputPrice = model.price_per_1k_input || 0
    const outputPrice = model.price_per_1k_output || 0
    return `$${inputPrice}/1K输入 · $${outputPrice}/1K输出`
  }

  // 打开获取模型弹窗
  const openFetchModal = () => {
    setFetchModalVisible(true)
    setSelectedChannelId('')
    setUpstreamModels([])
    setSelectedModels([])
  }

  // 选择渠道后拉取上游模型
  const handleSelectChannel = async (channelId: string) => {
    setSelectedChannelId(channelId)
    setFetchLoading(true)
    setSelectedModels([])
    
    try {
      // 调用同步模型API
      const result = await syncChannelModels(channelId)
      if (result.success && result.models) {
        // 同步接口返回的 models 即为该渠道的上游模型列表
        setUpstreamModels(result.models)
        setPagination({ ...pagination, total: result.models.length })
        message.success(`成功获取 ${result.count} 个模型`)
      } else {
        message.error(result.message || '获取模型失败')
        setUpstreamModels([])
        setPagination({ ...pagination, total: 0 })
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

  // 批量创建模型 + 建立渠道绑定
  const handleBatchCreate = async () => {
    if (selectedModels.length === 0) {
      message.warning('请选择要添加的模型')
      return
    }

    const channel = channelsList.find(p => p.channel_id === selectedChannelId)
    if (!channel) {
      message.error('渠道不存在')
      return
    }

    let createdCount = 0
    let boundCount = 0
    const errors: string[] = []

    for (const upstreamModelId of selectedModels) {
      const upstreamModel = upstreamModels.find(m => m.model_id === upstreamModelId)
      if (!upstreamModel) continue

      // 平台模型 ID：以渠道类型为前缀，避免不同渠道上游模型名撞车
      const platformModelId = `${channel.type}-${upstreamModelId}`

      // 1) 确保 Model 记录存在
      let modelExists = modelsList.find(m => m.model_id === platformModelId)
      if (!modelExists) {
        try {
          const created = await createModel({
            // @ts-ignore
            model_id: platformModelId,
            display_name: upstreamModel.name || upstreamModelId,
            price_type: 'token',
            price_per_1k_input: 0,
            price_per_1k_output: 0,
            price_per_request: 0,
            status: 'active',
          })
          modelExists = created as ModelMapping
          createdCount++
        } catch (e: any) {
          // 已存在的话也会走 createModel 的 catch 路径，先跳过绑定
          errors.push(`创建 ${platformModelId} 失败: ${e?.response?.data?.detail || e?.message}`)
          continue
        }
      }

      // 2) 建立渠道绑定
      try {
        await bindChannelToModel(platformModelId, {
          channel_id: channel.channel_id,
          upstream_model: upstreamModelId,
          priority: 0,
          weight: 100,
          enabled: true,
        })
        boundCount++
      } catch (e: any) {
        // 已绑定会返回 4xx 错误，跳过即可
        const detail = e?.response?.data?.detail || ''
        if (!detail.includes('已绑定') && !detail.includes('duplicate')) {
          errors.push(`绑定 ${platformModelId} → ${channel.name}: ${detail || '失败'}`)
        }
      }
    }

    if (errors.length > 0) {
      message.warning(`新建 ${createdCount} 个、绑定 ${boundCount} 个；${errors.length} 个失败，详见控制台`)
      console.error('[批量导入] 错误明细:', errors)
    } else {
      message.success(`成功新建 ${createdCount} 个模型并绑定 ${boundCount} 个渠道`)
    }
    setFetchModalVisible(false)
    setSelectedModels([])
    fetchData()
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
          color: token.colorText,
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
            style={{ background: token.colorPrimary, border: 'none', borderRadius: 10 }}
          >
            添加模型
          </Button>
        </Space>
      </div>

      {/* 模型列表 */}
      <div style={{
        background: token.colorBgContainer,
        backdropFilter: 'blur(20px)',
        border: `1px solid ${token.colorBorder}`,
        borderRadius: 16,
        overflow: 'hidden',
      }}>
        <Table
          dataSource={modelsList}
          columns={[
            { 
              title: '平台模型', 
              dataIndex: 'model_id', 
              key: 'model_id',
              width: 200,
              render: (_: any, record: ModelMapping) => (
                <div>
                  
                  <div style={{ color: token.colorText, fontWeight: 500 }}>{record.display_name}</div>
                </div>
              )
            },
            {
              title: '绑定渠道',
              key: 'bound_channels_count',
              width: 110,
              render: (_: any, record: ModelMapping) => (
                <Button
                  type="link"
                  size="small"
                  icon={<LinkOutlined />}
                  onClick={() => openBindingsDrawer(record)}
                  style={{ padding: 0 }}
                >
                  {record.bound_channels_count ?? 0} 个
                </Button>
              )
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
              title: '所属分组', 
              key: 'model_groups',
              width: 200,
              render: (_: any, record: ModelMapping) => {
                const groups = record.model_groups || []
                if (groups.length === 0) {
                  return <Tag style={{ borderRadius: 6 }}>-</Tag>
                }
                // 最多显示2个，其余折叠
                const visible = groups.slice(0, 2)
                const remaining = groups.length - 2
                return (
                  <>
                    {visible.map((name, i) => (
                      <Tag key={i} color="purple" style={{ borderRadius: 6, marginBottom: 2 }}>{name}</Tag>
                    ))}
                    {remaining > 0 && <Tag style={{ borderRadius: 6 }}>+{remaining}</Tag>}
                  </>
                )
              }
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
        title={<span style={{ color: token.colorText }}>{editModel ? '编辑模型' : '创建模型'}</span>}
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
                    <Form.Item name="display_name" label={<span style={{ color: token.colorTextSecondary }}>显示名称</span>} rules={[{ required: true, message: '请输入显示名称' }]}>
                      <Input placeholder="如: GPT-4o" />
                    </Form.Item>

                    <Form.Item name="description" label={<span style={{ color: token.colorTextSecondary }}>模型描述（可选）</span>}>
                      <Input.TextArea rows={2} placeholder="描述这个模型的用途和特点" />
                    </Form.Item>

                    <Form.Item name="aliases" label={<span style={{ color: token.colorTextSecondary }}>别名（可选，多个用逗号分隔）</span>}>
                      <Input placeholder="如: gpt4, gpt-4o" />
                    </Form.Item>

                    <Form.Item name="status" label={<span style={{ color: token.colorTextSecondary }}>状态</span>}>
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
                    <Form.Item name="price_type" label={<span style={{ color: token.colorTextSecondary }}>计费方式</span>}>
                      <Radio.Group onChange={(e) => setPriceType(e.target.value)}>
                        <Radio value="token">按Token计费</Radio>
                        <Radio value="request">按请求次数计费</Radio>
                      </Radio.Group>
                    </Form.Item>

                    {priceType === 'token' ? (
                      <Row gutter={16}>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_input" label={<span style={{ color: token.colorTextSecondary }}>每千输入Token价格($)</span>}>
                            <InputNumber min={0} step={0.0001} precision={4}  placeholder="0.001" />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item name="price_per_1k_output" label={<span style={{ color: token.colorTextSecondary }}>每千输出Token价格($)</span>}>
                            <InputNumber min={0} step={0.0001} precision={4}  placeholder="0.002" />
                          </Form.Item>
                        </Col>
                      </Row>
                    ) : (
                      <Form.Item name="price_per_request" label={<span style={{ color: token.colorTextSecondary }}>每次请求价格($)</span>}>
                        <InputNumber min={0} step={0.01} precision={2}  placeholder="0.01" />
                      </Form.Item>
                    )}

                    <div style={{ padding: 16, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8, marginTop: 16 }}>
                      <div style={{ color: '#3B82F6', fontSize: 13, marginBottom: 8 }}>💡 计费说明</div>
                      <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>
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
              <Button type="primary" htmlType="submit" style={{ background: token.colorPrimary, border: 'none' }}>
                {editModel ? '保存' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 获取模型弹窗 */}
      <Modal
        title={<span style={{ color: token.colorText }}><CloudDownloadOutlined style={{ marginRight: 8 }} />获取模型</span>}
        open={fetchModalVisible}
        onCancel={() => { setFetchModalVisible(false); setSelectedChannelId(''); setUpstreamModels([]); setSelectedModels([]); }}
        footer={null}
        width={900}
      >
        <div style={{ marginBottom: 16 }}>
          <span style={{ color: token.colorTextSecondary, marginRight: 8 }}>选择渠道：</span>
          <Select
            style={{ width: 300 }}
            placeholder="请选择渠道"
            value={selectedChannelId || undefined}
            onChange={handleSelectChannel}
          >
            {channelsList.filter(p => p.status === 'active').map(p => (
              <Select.Option key={p.channel_id} value={p.channel_id}>
                {p.name} ({p.type})
              </Select.Option>
            ))}
          </Select>
          <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
            从上游拉取的模型将以 <code>{'{channel.type}'}-{'{model_id}'}</code> 为平台 ID 自动创建，并自动绑定到所选渠道
          </div>
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
                  render: (text: string) => <span style={{ color: token.colorText }}>{text}</span>
                },
                { 
                  title: '模型名称', 
                  dataIndex: 'name', 
                  key: 'name',
                  render: (text: string) => <span style={{ color: token.colorTextSecondary }}>{text || '-'}</span>
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
              <div style={{ color: token.colorTextSecondary }}>
                已选择 <span style={{ color: '#3B82F6', fontWeight: 600 }}>{selectedModels.length}</span> 个模型
              </div>
              <Space>
                <Button onClick={() => setFetchModalVisible(false)}>取消</Button>
                <Button 
                  type="primary" 
                  onClick={handleBatchCreate}
                  disabled={selectedModels.length === 0}
                  style={{ background: token.colorPrimary, border: 'none' }}
                >
                  导入并绑定 ({selectedModels.length})
                </Button>
              </Space>
            </div>
          </>
        ) : selectedChannelId && !fetchLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: token.colorTextSecondary }}>
            该渠道暂无模型，请确保渠道配置正确
          </div>
        ) : null}
      </Modal>

      {/* ===== 渠道绑定 Drawer ===== */}
      <Drawer
        title={
          bindingsTarget && (
            <Space>
              <LinkOutlined />
              <span>{bindingsTarget.display_name || bindingsTarget.model_id} · 渠道绑定</span>
              <Tag color="blue">{bindings.length} 个</Tag>
            </Space>
          )
        }
        open={bindingsDrawerOpen}
        onClose={closeBindingsDrawer}
        width={720}
        destroyOnHidden
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openAddBinding}>
            添加绑定
          </Button>
        }
      >
        <Table<ModelChannel>
          rowKey="id"
          size="small"
          loading={bindingsLoading}
          dataSource={bindings}
          pagination={false}
          locale={{ emptyText: '尚未绑定任何渠道，点击右上角"添加绑定"开始' }}
          columns={[
            {
              title: '渠道',
              dataIndex: 'channel_id',
              width: 200,
              render: (id: string) => {
                const ch = channelsList.find(c => c.channel_id === id)
                return (
                  <div>
                    <div style={{ fontWeight: 500 }}>{ch?.name || id}</div>
                    <Tag color="default" style={{ fontSize: 11 }}>{ch?.type || 'unknown'}</Tag>
                  </div>
                )
              },
            },
            {
              title: '上游模型名',
              dataIndex: 'upstream_model',
              render: (text: string) => (
                <span style={{ color: '#10B981', fontFamily: 'monospace' }}>{text}</span>
              ),
            },
            {
              title: '优先级',
              dataIndex: 'priority',
              width: 70,
              align: 'center',
            },
            {
              title: '权重',
              dataIndex: 'weight',
              width: 70,
              align: 'center',
            },
            {
              title: '启用',
              dataIndex: 'enabled',
              width: 70,
              align: 'center',
              render: (enabled: boolean, record: ModelChannel) => (
                <Switch
                  size="small"
                  checked={enabled}
                  onChange={(v) => handleToggleBinding(record, v)}
                />
              ),
            },
            {
              title: '操作',
              key: 'actions',
              width: 140,
              render: (_: any, record: ModelChannel) => (
                <Space size="small">
                  <Button
                    type="link"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => openEditBinding(record)}
                  >
                    编辑
                  </Button>
                  <Popconfirm
                    title="确认解绑？"
                    onConfirm={() => handleUnbind(record)}
                  >
                    <Button
                      type="link"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                    >
                      解绑
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Drawer>

      {/* ===== 添加/编辑绑定 Modal ===== */}
      <Modal
        title={editingBinding ? '编辑绑定' : '添加绑定'}
        open={bindingFormOpen}
        onCancel={() => setBindingFormOpen(false)}
        onOk={submitBinding}
        okText={editingBinding ? '保存' : '绑定'}
        destroyOnHidden
      >
        <Form form={bindingForm} layout="vertical" preserve={false}>
          <Form.Item
            name="channel_id"
            label="渠道"
            rules={[{ required: true, message: '请选择渠道' }]}
          >
            <Select
              placeholder="选择渠道"
              disabled={!!editingBinding}
              showSearch
              optionFilterProp="children"
            >
              {channelsList.map(c => (
                <Select.Option key={c.channel_id} value={c.channel_id}>
                  {c.name} ({c.type})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="upstream_model"
            label="上游模型名"
            rules={[{ required: true, message: '请填写上游模型名' }]}
            extra="该渠道上对应的上游模型 ID（如 gpt-4o、claude-3-opus-20240229）"
          >
            <Input placeholder="如: gpt-4o, claude-3-opus" />
          </Form.Item>
          <Divider style={{ margin: '12px 0' }} />
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="priority"
                label="优先级"
                extra="数值大者优先生效"
              >
                <InputNumber style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="weight"
                label="权重"
                extra="同优先级时按权重分配流量"
              >
                <InputNumber min={1} max={1000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelsPage
