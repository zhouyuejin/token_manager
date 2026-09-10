import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import {
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, Switch,
  Drawer, Row, Col, Card, Typography, Checkbox, Select, Tooltip, Empty, Popconfirm, message
} from 'antd'
import {
  ArrowLeftOutlined, SyncOutlined, ReloadOutlined, PlusOutlined,
  ArrowRightOutlined, DeleteOutlined, EditOutlined, DragOutlined,
  CheckOutlined, SearchOutlined
} from '@ant-design/icons'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  DragEndEvent
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  getChannel, getChannelModelBindings, bindModelToChannel, unbindModelFromChannel,
  updateChannelModelBinding, replaceChannelModelBindings, ChannelModelBinding
} from '../../api/channels'
import { getModels, Model } from '../../api/models'

// 获取模型显示名称的辅助函数
const getModelDisplayName = (binding: ChannelModelBinding, allModels: Model[]): string => {
  if (binding.model?.display_name) return binding.model.display_name
  const fallback = allModels.find(m => m.model_id === binding.model_id)
  return fallback?.display_name || fallback?.model_id || binding.model_id
}

const { Title, Text } = Typography

// 可排序行组件
interface SortableRowProps {
  id: string
  binding: ChannelModelBinding
  onEdit: (binding: ChannelModelBinding) => void
  onUnbind: (binding: ChannelModelBinding) => void
  selected: boolean
  onSelect: (checked: boolean) => void
  allModels: Model[]
}

const SortableRow: React.FC<SortableRowProps> = ({
  id, binding, onEdit, onUnbind, selected, onSelect, allModels
}) => {
  const {
    attributes, launchers, listeners, setNodeRef, transform, transition, isDragging
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    backgroundColor: selected ? '#e6f7ff' : 'transparent'
  }

  return (
    <div ref={setNodeRef} style={{ ...style, display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
      <Checkbox
        checked={selected}
        onChange={(e) => onSelect(e.target.checked)}
        style={{ marginRight: 12 }}
      />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 500 }}>{getModelDisplayName(binding, allModels)}</div>
        <Text type="secondary" style={{ fontSize: 12 }}>{binding.model_id}</Text>
      </div>
      <Tag color="blue" style={{ marginRight: 8 }}>{binding.upstream_model}</Tag>
      <Text type="secondary" style={{ marginRight: 8, width: 40, textAlign: 'center' }}>
        优先级: {binding.priority}
      </Text>
      <Text type="secondary" style={{ marginRight: 8, width: 40, textAlign: 'center' }}>
        权重: {binding.weight}
      </Text>
      <Switch
        size="small"
        checked={binding.enabled}
        style={{ marginRight: 8 }}
        onChange={(checked) => {
          // 启用/禁用单独处理，不影响选中状态
        }}
      />
      <Space size="small">
        <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(binding)} />
        <Popconfirm title="确认解绑？" onConfirm={() => onUnbind(binding)}>
          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
      <div
        {...attributes}
        {...listeners}
        style={{ cursor: 'grab', marginLeft: 8, padding: '4px 8px' }}
      >
        <DragOutlined />
      </div>
    </div>
  )
}

const ChannelBindingsPage: React.FC = () => {
  const { channelId } = useParams<{ channelId: string }>()
  const navigate = useNavigate()
  const message = useMessage()
  const { token } = useThemeToken()

  const [channel, setChannel] = useState<Channel | null>(null)
  const [allModels, setAllModels] = useState<Model[]>([])
  const [boundBindings, setBoundBindings] = useState<ChannelModelBinding[]>([])
  const [loading, setLoading] = useState(false)
  const [binding, setBinding] = useState<ChannelModelBinding | null>(null)
  const [selectedUnboundModels, setSelectedUnboundModels] = useState<Set<string>>(new Set())
  const [selectedBoundModels, setSelectedBoundModels] = useState<Set<string>>(new Set())

  // 搜索和筛选状态
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortOrder, setSortOrder] = useState<string>('name')

  // 绑定配置抽屉
  const [editDrawerVisible, setEditDrawerVisible] = useState(false)
  const [editForm] = Form.useForm()

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  useEffect(() => {
    if (channelId) {
      fetchData()
    }
  }, [channelId])

  // 完整刷新（页面加载时）
  const fetchData = async () => {
    if (!channelId) return
    setLoading(true)
    try {
      const [channelRes, modelsRes, bindingsRes] = await Promise.all([
        getChannel(channelId),
        getModels(),
        getChannelModelBindings(channelId)
      ])
      setChannel(channelRes)
      setAllModels(modelsRes.items || [])
      setBoundBindings(bindingsRes.items || [])
    } catch (error) {
      console.error(error)
      message.error('加载数据失败')
    } finally {
      setLoading(false)
    }
  }

  // 轻量刷新（绑定/解绑后，只刷新必要的接口）
  const refreshBindings = async () => {
    if (!channelId) return
    try {
      const bindingsRes = await getChannelModelBindings(channelId)
      setBoundBindings(bindingsRes.items || [])
    } catch (error) {
      console.error(error)
    }
  }

  // 计算未绑定模型
  const unboundModels = useMemo(() => {
    const boundModelIds = new Set(boundBindings.map(b => b.model_id))
    return allModels.filter(m => !boundModelIds.has(m.model_id))
  }, [allModels, boundBindings])

  // 筛选后的未绑定模型
  const filteredUnboundModels = useMemo(() => {
    let result = unboundModels

    // 搜索过滤
    if (searchText) {
      const lower = searchText.toLowerCase()
      result = result.filter(m =>
        (m.display_name || '').toLowerCase().includes(lower) ||
        m.model_id.toLowerCase().includes(lower)
      )
    }

    // 状态过滤
    if (statusFilter !== 'all') {
      result = result.filter(m => m.status === statusFilter)
    }

    // 排序
    if (sortOrder === 'name') {
      result = [...result].sort((a, b) =>
        (a.display_name || a.model_id).localeCompare(b.display_name || b.model_id)
      )
    }

    return result
  }, [unboundModels, searchText, statusFilter, sortOrder])

  // 筛选后的已绑定模型
  const filteredBoundBindings = useMemo(() => {
    let result = [...boundBindings]

    // 搜索过滤
    if (searchText) {
      const lower = searchText.toLowerCase()
      result = result.filter(b =>
        (b.model?.display_name || '').toLowerCase().includes(lower) ||
        b.model_id.toLowerCase().includes(lower) ||
        b.upstream_model.toLowerCase().includes(lower)
      )
    }

    // 状态过滤
    if (statusFilter !== 'all') {
      result = result.filter(b => (b.model?.status || '') === statusFilter)
    }

    // 排序
    if (sortOrder === 'name') {
      result = result.sort((a, b) =>
        (a.model?.display_name || a.model_id).localeCompare(b.model?.display_name || b.model_id)
      )
    } else if (sortOrder === 'priority') {
      result = result.sort((a, b) => b.priority - a.priority)
    } else if (sortOrder === 'created') {
      result = result.sort((a, b) =>
        new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
      )
    }

    return result
  }, [boundBindings, searchText, statusFilter, sortOrder])

  // 绑定模型（单个）
  const handleBind = async (model: Model) => {
    if (!channelId) return
    try {
      await bindModelToChannel(channelId, {
        model_id: model.model_id,
        upstream_model: model.model_id, // 默认使用 model_id 作为上游模型名
        priority: 0,
        weight: 100,
        enabled: true
      })
      message.success(`${model.display_name || model.model_id} 绑定成功`)
      setSelectedUnboundModels(prev => {
        const next = new Set(prev)
        next.delete(model.model_id)
        return next
      })
      await refreshBindings()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '绑定失败')
    }
  }

  // 批量绑定
  const handleBatchBind = async () => {
    if (!channelId || selectedUnboundModels.size === 0) return
    try {
      const promises = Array.from(selectedUnboundModels).map(modelId => {
        const model = allModels.find(m => m.model_id === modelId)!
        return bindModelToChannel(channelId, {
          model_id: modelId,
          upstream_model: model.model_id,
          priority: 0,
          weight: 100,
          enabled: true
        })
      })
      await Promise.all(promises)
      message.success(`${selectedUnboundModels.size} 个模型绑定成功`)
      setSelectedUnboundModels(new Set())
      await refreshBindings()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '批量绑定失败')
    }
  }

  // 解绑模型（单个）
  const handleUnbind = async (binding: ChannelModelBinding) => {
    if (!channelId) return
    try {
      await unbindModelFromChannel(channelId, binding.model_id)
      message.success('解绑成功')
      setSelectedBoundModels(prev => {
        const next = new Set(prev)
        next.delete(binding.model_id)
        return next
      })
      await refreshBindings()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '解绑失败')
    }
  }

  // 批量解绑
  const handleBatchUnbind = async () => {
    if (!channelId || selectedBoundModels.size === 0) return
    try {
      const promises = Array.from(selectedBoundModels).map(modelId =>
        unbindModelFromChannel(channelId, modelId)
      )
      await Promise.all(promises)
      message.success(`${selectedBoundModels.size} 个模型解绑成功`)
      setSelectedBoundModels(new Set())
      await refreshBindings()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '批量解绑失败')
    }
  }

  // 打开编辑抽屉
  const openEditDrawer = (binding: ChannelModelBinding) => {
    setBinding(binding)
    editForm.setFieldsValue({
      upstream_model: binding.upstream_model,
      priority: binding.priority,
      weight: binding.weight,
      enabled: binding.enabled
    })
    setEditDrawerVisible(true)
  }

  // 保存编辑
  const handleEditSave = async () => {
    if (!channelId || !binding) return
    try {
      const values = await editForm.validateFields()
      await updateChannelModelBinding(channelId, binding.model_id, values)
      message.success('更新成功')
      setEditDrawerVisible(false)
      await refreshBindings()
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '更新失败')
    }
  }

  // 拖拽结束
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !channelId) return

    const oldIndex = boundBindings.findIndex(b => b.model_id === active.id)
    const newIndex = boundBindings.findIndex(b => b.model_id === over.id)

    if (oldIndex === -1 || newIndex === -1) return

    const newBindings = arrayMove(boundBindings, oldIndex, newIndex)

    // 更新本地状态
    setBoundBindings(newBindings)

    // 重新计算优先级并保存
    const updateData = newBindings.map((b, index) => ({
      model_id: b.model_id,
      upstream_model: b.upstream_model,
      priority: index, // 拖拽顺序作为优先级
      weight: b.weight,
      enabled: b.enabled
    }))

    try {
      await replaceChannelModelBindings(channelId, updateData)
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '保存排序失败')
      await fetchData() // 失败则重新加载
    }
  }

  // 切换未绑定模型选中
  const toggleUnboundSelect = (modelId: string, checked: boolean) => {
    setSelectedUnboundModels(prev => {
      const next = new Set(prev)
      if (checked) {
        next.add(modelId)
      } else {
        next.delete(modelId)
      }
      return next
    })
  }

  // 切换已绑定模型选中
  const toggleBoundSelect = (modelId: string, checked: boolean) => {
    setSelectedBoundModels(prev => {
      const next = new Set(prev)
      if (checked) {
        next.add(modelId)
      } else {
        next.delete(modelId)
      }
      return next
    })
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面头部 */}
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/channels')}>
                返回渠道列表
              </Button>
              <Title level={4} style={{ margin: 0 }}>
                {channel?.name || '渠道名称'} - 绑定管理
              </Title>
              {channel && (
                <Tag color={channel.status === 'active' ? 'green' : 'red'}>
                  {channel.status === 'active' ? '正常' : '已禁用'}
                </Tag>
              )}
            </Space>
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                刷新
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 统计信息 */}
        <Row gutter={16} style={{ marginTop: 16 }}>
          <Col>
            <Text>已绑定: <Text strong>{boundBindings.length}</Text> 个</Text>
          </Col>
          <Col>
            <Text>未绑定: <Text strong>{unboundModels.length}</Text> 个</Text>
          </Col>
        </Row>
      </Card>

      {/* 搜索和筛选 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Input
              placeholder="搜索模型名称、ID 或上游模型名..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col>
            <Select value={statusFilter} onChange={setStatusFilter} style={{ width: 120 }}>
              <Select.Option value="all">全部状态</Select.Option>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Col>
          <Col>
            <Select value={sortOrder} onChange={setSortOrder} style={{ width: 120 }}>
              <Select.Option value="name">按名称</Select.Option>
              <Select.Option value="priority">按优先级</Select.Option>
              <Select.Option value="created">按时间</Select.Option>
            </Select>
          </Col>
        </Row>
      </Card>

      {/* 左右双栏布局 */}
      <Row gutter={16}>
        {/* 左侧 - 未绑定模型 */}
        <Col span={12}>
          <Card
            title="未绑定模型"
            extra={<Tag>{filteredUnboundModels.length}</Tag>}
            style={{ height: '100%' }}
          >
            {filteredUnboundModels.length === 0 ? (
              <Empty description="暂无未绑定模型" />
            ) : (
              <>
                <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                  {filteredUnboundModels.map(model => (
                    <div
                      key={model.model_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '8px 12px',
                        borderBottom: '1px solid #f0f0f0'
                      }}
                    >
                      <Checkbox
                        checked={selectedUnboundModels.has(model.model_id)}
                        onChange={(e) => toggleUnboundSelect(model.model_id, e.target.checked)}
                        style={{ marginRight: 12 }}
                      />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 500 }}>{model.display_name || model.model_id}</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>{model.model_id}</Text>
                      </div>
                      <Tag color={model.status === 'active' ? 'green' : 'red'}>
                        {model.status === 'active' ? '启用' : '禁用'}
                      </Tag>
                      <Button
                        type="text"
                        icon={<ArrowRightOutlined />}
                        onClick={() => handleBind(model)}
                        style={{ marginLeft: 8 }}
                      />
                    </div>
                  ))}
                </div>
                {selectedUnboundModels.size > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={handleBatchBind}
                    >
                      批量绑定 ({selectedUnboundModels.size})
                    </Button>
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>

        {/* 右侧 - 已绑定模型 */}
        <Col span={12}>
          <Card
            title="已绑定模型"
            extra={<Tag>{filteredBoundBindings.length}</Tag>}
            style={{ height: '100%' }}
          >
            {filteredBoundBindings.length === 0 ? (
              <Empty description="暂无已绑定模型" />
            ) : (
              <>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    items={filteredBoundBindings.map(b => b.model_id)}
                    strategy={verticalListSortingStrategy}
                  >
                    <div style={{ maxHeight: 500, overflowY: 'auto' }}>
                      {filteredBoundBindings.map(binding => (
                        <SortableRow
                          key={binding.model_id}
                          id={binding.model_id}
                          binding={binding}
                          onEdit={openEditDrawer}
                          onUnbind={handleUnbind}
                          selected={selectedBoundModels.has(binding.model_id)}
                          onSelect={(checked) => toggleBoundSelect(binding.model_id, checked)}
                          allModels={allModels}
                        />
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>
                {selectedBoundModels.size > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Popconfirm
                      title={`确认解绑 ${selectedBoundModels.size} 个模型？`}
                      onConfirm={handleBatchUnbind}
                    >
                      <Button danger icon={<DeleteOutlined />}>
                        批量解绑 ({selectedBoundModels.size})
                      </Button>
                    </Popconfirm>
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* 编辑绑定配置抽屉 */}
      <Drawer
        title="编辑绑定配置"
        placement="right"
        onClose={() => setEditDrawerVisible(false)}
        open={editDrawerVisible}
        width={400}
        extra={
          <Button type="primary" onClick={handleEditSave}>
            保存
          </Button>
        }
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="upstream_model" label="上游模型名" rules={[{ required: true, message: '请输入上游模型名' }]}>
            <Input placeholder="如: gpt-4o, claude-3-opus" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label="优先级" extra="数值大者优先">
                <InputNumber style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="weight" label="权重" extra="1-1000，同优先级按权重分配">
                <InputNumber min={1} max={1000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}

export default ChannelBindingsPage
