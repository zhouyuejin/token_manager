import { useState, useEffect, useMemo } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, Popconfirm, Tabs, Row, Col, InputNumber, Radio, Checkbox,
  Drawer, Switch, Divider, Tooltip
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, DollarOutlined, SettingOutlined, CloudDownloadOutlined, LinkOutlined, SearchOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, syncModelPricing, ModelMapping, ModelChannel, getModelChannels, bindChannelToModel, unbindChannel, updateModelChannel } from '../../api/models'
import { useSwrData } from '../../hooks/useSwr'
import { getChannels, Channel, syncChannelModels, batchBindModelsToChannel } from '../../api/channels'

const routeStrategyLabels: Record<string, string> = {
  priority: '优先级',
  weight: '权重',
  lowest_cost: '最低成本',
  lowest_latency: '最低延迟',
}

// 上游模型类型
interface UpstreamModel {
  model_id: string
  name?: string        // 旧格式
  owned_by?: string    // 旧格式
  model_name?: string  // 新格式
  display_name?: string // 新格式
}


// 导入结果明细 Modal 的小卡片
const Stat = ({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'success' | 'muted' | 'danger' }) => {
  const { token } = useThemeToken()
  const color =
    tone === 'success' ? token.colorSuccess :
    tone === 'danger' ? token.colorError :
    tone === 'muted' ? token.colorTextTertiary :
    token.colorText
  return (
    <div style={{ padding: '8px 12px', borderRadius: 8, background: token.colorFillTertiary }}>
      <div style={{ fontSize: 12, color: token.colorTextSecondary }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600, color, lineHeight: 1.4 }}>{value}</div>
    </div>
  )
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
  // 获取模型抽屉：搜索 / 仅看未导入 / 导入结果明细
  const [searchText, setSearchText] = useState('')
  const [onlyNew, setOnlyNew] = useState(false)
  const [importResult, setImportResult] = useState<{
    totalSelected: number
    preExisted: number
    created: number
    bound: number
    skipped: number
    errors: string[]
  } | null>(null)

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

  // 平台模型 ID 规则：${channel.type}-${upstream.model_id}（与 handleBatchCreate 中生成方式一致）
  // Set 用于「存在性」快查；Map 用于在 Drawer 行内拿到完整 Model 记录（bound_channel_ids）
  const existingModelIds = useMemo(
    () => new Set(modelsList.map(m => m.model_id)),
    [modelsList],
  )
  const existingModelsById = useMemo(
    () => new Map(modelsList.map(m => [m.model_id, m] as const)),
    [modelsList],
  )
  const selectedChannelType = useMemo(
    () => channelsList.find(c => c.channel_id === selectedChannelId)?.type,
    [channelsList, selectedChannelId],
  )
  // 当前渠道已绑定的 platformModelId 集合（驱动"已绑此渠道" 的不可勾状态）
  const alreadyBoundToCurrent = useMemo(() => {
    if (!selectedChannelId) return new Set<string>()
    const set = new Set<string>()
    modelsList.forEach(m => {
      if (m.bound_channel_ids?.includes(selectedChannelId)) set.add(m.model_id)
    })
    return set
  }, [modelsList, selectedChannelId])
  // 按搜索词 + 仅看未导入 过滤上游模型
  const filteredUpstreamModels = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return upstreamModels.filter(m => {
      // 「仅看可操作」: 排除已存在且已绑当前渠道的行（不可操作）
      if (onlyNew && existingModelIds.has(`${selectedChannelType}-${m.model_id}`) && alreadyBoundToCurrent.has(`${selectedChannelType}-${m.model_id}`)) return false
      if (!q) return true
      return [m.model_id, m.name, m.model_name, m.display_name, m.owned_by]
        .filter(Boolean)
        .some((s: any) => String(s).toLowerCase().includes(q))
    })
  }, [upstreamModels, searchText, onlyNew, existingModelIds, selectedChannelType])

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

  const handleSyncPricing = async () => {
    setLoading(true)
    try {
      const result = await syncModelPricing()
      message.success(`已同步 ${result.updated} 个模型价格，跳过 ${result.skipped} 个`)
      fetchData()
    } catch (error) {
      message.error('同步定价失败')
    } finally {
      setLoading(false)
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
    setSearchText('')
    setOnlyNew(false)

    try {
      // 调用同步模型API
      const result = await syncChannelModels(channelId)
      if (result.success && result.models) {
        // 同步接口返回的 models 即为该渠道的上游模型列表
        setUpstreamModels(result.models)
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

  // 选择模型
  const handleSelectModel = (modelId: string, checked: boolean) => {
    if (checked) {
      setSelectedModels([...selectedModels, modelId])
    } else {
      setSelectedModels(selectedModels.filter(id => id !== modelId))
    }
  }

  // 全选：仅勾选「可操作」的行——全新 + 已存在但未绑当前渠道。
  // 已存在且已绑当前渠道的行 disabled，不会被勾上。
  const handleSelectAll = (checked: boolean, currentPageModels: UpstreamModel[]) => {
    if (checked) {
      const eligible = currentPageModels
        .filter(m => {
          const pid = `${selectedChannelType}-${m.model_id}`
          if (!existingModelIds.has(pid)) return true             // 全新
          return !alreadyBoundToCurrent.has(pid)                  // 存在但未绑当前渠道
        })
        .map(m => m.model_id)
      setSelectedModels(prev => [...new Set([...prev, ...eligible])])
    } else {
      const currentPageIds = currentPageModels.map(m => m.model_id)
      setSelectedModels(prev => prev.filter(id => !currentPageIds.includes(id)))
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
    const errors: string[] = []
    const prepared: Array<{ upstreamModelId: string; platformModelId: string }> = []

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

      prepared.push({ upstreamModelId, platformModelId })
    }

    // 2) 批量绑定：一次 HTTP 调用替代原 N 次单条 POST
    let boundCount = 0
    let skippedCount = 0
    if (prepared.length > 0) {
      try {
        const result = await batchBindModelsToChannel(channel.channel_id, prepared.map(p => ({
          model_id: p.platformModelId,
          upstream_model: p.upstreamModelId,
          priority: 0,
          weight: 100,
          enabled: true,
        })))
        boundCount = result.added.length
        skippedCount = result.skipped.length
        // 后端 errors：model 不存在等，记录到统一错误列表
        for (const e of result.errors) errors.push(`绑定 ${channel.name}: ${e}`)
      } catch (e: any) {
        errors.push(`批量绑定失败: ${e?.response?.data?.detail || e?.message || '失败'}`)
      }
    }

    // 统计：selectedModels 里被前端内存差集跳过的（即「已存在」）
    const preExisted = selectedModels.filter(id => {
      const upstreamModel = upstreamModels.find(m => m.model_id === id)
      if (!upstreamModel) return false
      return existingModelIds.has(`${channel.type}-${id}`)
    }).length

    setImportResult({
      totalSelected: selectedModels.length,
      preExisted,
      created: createdCount,
      bound: boundCount,
      skipped: skippedCount,
      errors,
    })

    if (errors.length > 0) {
      console.error('[批量导入] 错误明细:', errors)
    }
    setSelectedModels([])
    fetchData()
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
            icon={<DollarOutlined />}
            onClick={handleSyncPricing}
            loading={loading}
            style={{ borderRadius: 10 }}
          >
            同步定价
          </Button>
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
              width: 280,
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
              title: '路由策略',
              key: 'route_strategy',
              width: 110,
              render: (_: any, record: ModelMapping) => <Tag color="blue">{routeStrategyLabels[record.route_strategy || 'priority'] || '优先级'}</Tag>,
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
              fixed: 'right',
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
          scroll={{ x: 'max-content', y: 'calc(100vh - 280px)' }}
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
            price_per_request: 0,
            route_strategy: 'priority'
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

                    <Form.Item name="route_strategy" label={<span style={{ color: token.colorTextSecondary }}>路由策略</span>}>
                      <Select options={[
                        { value: 'priority', label: '优先级（保持当前顺序）' },
                        { value: 'weight', label: '权重（按绑定权重随机）' },
                        { value: 'lowest_cost', label: '最低成本（近24小时历史成本）' },
                        { value: 'lowest_latency', label: '最低延迟（近24小时平均延迟）' },
                      ]} />
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

      {/* 获取模型抽屉 */}
      <Drawer
        title={<span style={{ color: token.colorText }}><CloudDownloadOutlined style={{ marginRight: 8 }} />从上游获取模型</span>}
        open={fetchModalVisible}
        onClose={() => {
          setFetchModalVisible(false)
          setSelectedChannelId('')
          setUpstreamModels([])
          setSelectedModels([])
          setSearchText('')
          setOnlyNew(false)
        }}
        placement="right"
        width={560}
        destroyOnHidden
        styles={{ body: { paddingTop: 12 } }}
        footer={
          upstreamModels.length > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>
                已选 <span style={{ color: token.colorPrimary, fontWeight: 600 }}>{selectedModels.length}</span>
                {' / '}
                过滤后 <span style={{ fontWeight: 600 }}>{filteredUpstreamModels.length}</span>
                {' / '}
                上游共 <span style={{ fontWeight: 600 }}>{upstreamModels.length}</span>
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
          )
        }
      >
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ color: token.colorTextSecondary, whiteSpace: 'nowrap' }}>渠道：</span>
            <Select
              style={{ flex: 1, minWidth: 200 }}
              placeholder="请选择渠道"
              value={
                selectedChannelId && channelsList.some(
                  p => p.channel_id === selectedChannelId && p.status === 'active'
                )
                  ? selectedChannelId
                  : undefined
              }
              onChange={handleSelectChannel}
            >
              {channelsList.filter(p => p.status === 'active').map(p => (
                <Select.Option key={p.channel_id} value={p.channel_id}>
                  {p.name} ({p.type})
                </Select.Option>
              ))}
            </Select>
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary, lineHeight: 1.6 }}>
            平台 ID 规则：<code>{'{channel.type}'}-{'{model_id}'}</code>；已存在的模型会自动标灰、不可勾选。
          </div>
        </div>

        {upstreamModels.length > 0 ? (
          <>
            <Input
              allowClear
              placeholder="搜索 model_id / name / display_name"
              prefix={<SearchOutlined style={{ color: token.colorTextSecondary }} />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Space size={4} wrap style={{ marginBottom: 8 }}>
              <Button size="small" onClick={() => handleSelectAll(true, filteredUpstreamModels)}>全选过滤结果</Button>
              <Button size="small" onClick={() => setSelectedModels([])}>清空选择</Button>
              <Checkbox checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)}>
                仅看可操作
              </Checkbox>
            </Space>

            <Table<UpstreamModel>
              dataSource={filteredUpstreamModels}
              rowKey="model_id"
              loading={fetchLoading}
              size="small"
              pagination={{
                pageSize: 50,
                showSizeChanger: true,
                pageSizeOptions: ['20', '50', '100'],
                showTotal: (total) => `共 ${total} 个`,
              }}
              scroll={{ y: 'calc(100vh - 460px)' }}
              columns={[
                {
                  title: (
                    <Checkbox
                      onChange={(e) => handleSelectAll(e.target.checked, filteredUpstreamModels)}
                      checked={filteredUpstreamModels.length > 0 && filteredUpstreamModels.every(m => selectedModels.includes(m.model_id))}
                      indeterminate={filteredUpstreamModels.some(m => selectedModels.includes(m.model_id)) && !filteredUpstreamModels.every(m => selectedModels.includes(m.model_id))}
                    />
                  ),
                  key: 'checkbox',
                  width: 44,
                  render: (_: any, record: UpstreamModel) => {
                    const platformModelId = `${selectedChannelType}-${record.model_id}`
                    const existed = existingModelIds.has(platformModelId)
                    const fullySkipped = existed && alreadyBoundToCurrent.has(platformModelId)
                    return (
                      <Checkbox
                        checked={selectedModels.includes(record.model_id)}
                        disabled={fullySkipped}
                        onChange={(e) => handleSelectModel(record.model_id, e.target.checked)}
                      />
                    )
                  },
                },
                {
                  title: '模型 ID',
                  dataIndex: 'model_id',
                  key: 'model_id',
                  width: 200,
                  render: (text: string) => (
                    <Tooltip title={text} placement="topLeft">
                      <span
                        style={{
                          color: token.colorText,
                          fontFamily: 'monospace',
                          display: 'inline-block',
                          maxWidth: 180,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          verticalAlign: 'middle',
                        }}
                      >
                        {text}
                      </span>
                    </Tooltip>
                  ),
                },
                {
                  title: '名称',
                  key: 'name',
                  render: (_: any, record: UpstreamModel) => {
                    const platformModelId = `${selectedChannelType}-${record.model_id}`
                    const existed = existingModelIds.has(platformModelId)
                    const boundToCurrent = existed && alreadyBoundToCurrent.has(platformModelId)
                    const existedModel = existed ? existingModelsById.get(platformModelId) : null
                    const boundIds = existedModel?.bound_channel_ids ?? []
                    const displayName = record.display_name || record.model_name || record.name || '-'
                    const boundIdsText = boundIds.length > 0
                      ? `已绑: ${boundIds.join(', ')}`
                      : null
                    return (
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space size={4}>
                          <Tooltip title={displayName} placement="topLeft">
                            <span
                              style={{
                                color: existed ? token.colorTextTertiary : token.colorTextSecondary,
                                maxWidth: 200,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                display: 'inline-block',
                                verticalAlign: 'middle',
                              }}
                            >
                              {displayName}
                            </span>
                          </Tooltip>
                          {boundToCurrent && <Tag style={{ marginInlineEnd: 0, flexShrink: 0 }}>已绑此渠道</Tag>}
                          {existed && !boundToCurrent && (
                            <Tag color="warning" style={{ marginInlineEnd: 0, flexShrink: 0 }}>可补绑定</Tag>
                          )}
                        </Space>
                        {existed && boundIdsText && (
                          <Tooltip title={boundIds.join(', ')} placement="bottomLeft">
                            <span
                              style={{
                                fontSize: 11,
                                color: token.colorTextTertiary,
                                fontFamily: 'monospace',
                                maxWidth: 200,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                display: 'inline-block',
                              }}
                            >
                              {boundIdsText}
                            </span>
                          </Tooltip>
                        )}
                      </Space>
                    )
                  },
                },
              ]}
            />
          </>
        ) : selectedChannelId && !fetchLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: token.colorTextSecondary }}>
            该渠道暂无模型，请确保渠道配置正确
          </div>
        ) : null}
      </Drawer>

      {/* 导入结果明细 */}
      <Modal
        title="导入结果"
        open={!!importResult}
        onCancel={() => { setImportResult(null); setFetchModalVisible(false) }}
        footer={
          <Button type="primary" onClick={() => { setImportResult(null); setFetchModalVisible(false) }}>
            关闭
          </Button>
        }
        width={520}
      >
        {importResult && (
          <div style={{ color: token.colorText }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <Stat label="本次选择" value={importResult.totalSelected} />
              <Stat label="已存在（未新建模型）" value={importResult.preExisted} tone="muted" />
              <Stat label="新建模型" value={importResult.created} tone="success" />
              <Stat label="新绑定数" value={importResult.bound} tone="success" />
              <Stat label="后端跳过" value={importResult.skipped} tone="muted" />
              <Stat label="失败" value={importResult.errors.length} tone={importResult.errors.length > 0 ? 'danger' : 'muted'} />
            </div>
            {importResult.errors.length > 0 && (
              <div>
                <div style={{ fontSize: 12, color: token.colorTextSecondary, marginBottom: 4 }}>
                  失败明细（同时写入 console.error）：
                </div>
                <ul style={{ paddingInlineStart: 18, margin: 0, maxHeight: 200, overflow: 'auto', fontSize: 12, color: token.colorError }}>
                  {importResult.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>



      {/* ===== 渠道绑定 Drawer ===== */}
      <Drawer
        title={
          bindingsTarget && (
            <Space>
              <LinkOutlined />
              <span>{bindingsTarget.display_name || bindingsTarget.model_id} · 渠道绑定</span>
              <Tag color="blue">{bindings.length} 个</Tag>
              <Tag color="purple">策略：{routeStrategyLabels[bindingsTarget.route_strategy || 'priority'] || '优先级'}</Tag>
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
