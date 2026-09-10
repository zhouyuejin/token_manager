import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, Switch, 
  Select, Popconfirm, Row, Col, Progress, Collapse, Tooltip, Card
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CloudOutlined, SettingOutlined, ApiOutlined } from '@ant-design/icons'
import { 
  getChannels, createChannel, updateChannel, deleteChannel,
  getAllChannelQuotas, syncChannelQuota, updateChannelQuota, Channel, 
  getChannelModels, syncChannelModels, testChannelConnection
} from '../../api/channels'
import { getModels, Model, bindChannelToModel, unbindChannel, getModelChannels } from '../../api/models'

const { Panel } = Collapse

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

const calcQuotaStats = (quota: any) => {
  if (!quota) return null
  const modelRemains = quota.hourly?.raw_data?.model_remains || []
  if (modelRemains.length === 0) return null
  const m = modelRemains[0]
  return {
    hourlyUsedPercent: 100 - (m.current_interval_remaining_percent || 0),
    hourlyTotal: m.current_interval_total_count || 0,
    hourlyRemainPercent: m.current_interval_remaining_percent || 0,
    hourlyRemainTime: m.remains_time || 0,
    weeklyUsedPercent: 100 - (m.current_weekly_remaining_percent || 0),
    weeklyTotal: m.current_weekly_total_count || 0,
    weeklyRemainPercent: m.current_weekly_remaining_percent || 0,
    weeklyRemainTime: m.weekly_remains_time || 0,
  }
}

const ChannelsPage = () => {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const [channels, setChannels] = useState<Channel[]>([])
  const [quotas, setQuotas] = useState<Record<string, any>>({})
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [modelModalVisible, setModelModalVisible] = useState(false)
  const [selectedChannelModels, setSelectedChannelModels] = useState<any[]>([])
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null)
  const [form] = Form.useForm()
  const [configForm] = Form.useForm()
  const message = useMessage()
  const { token } = useThemeToken()
  const [allModels, setAllModels] = useState<Model[]>([])
  const [bindLoading, setBindLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [channelsRes, quotasRes, modelsRes] = await Promise.all([
        getChannels(),
        getAllChannelQuotas(),
        getModels()
      ])
      setAllModels(modelsRes.items || [])
      setChannels(channelsRes.items || [])
      const quotaMap: Record<string, any> = {}
      quotasRes.items?.forEach((item: any) => { quotaMap[item.channel_id] = item })
      setQuotas(quotaMap)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async (channelId: string) => {
    try {
      await syncChannelQuota(channelId)
      message.success('同步成功')
      fetchData()
    } catch {
      message.error('同步失败')
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createChannel(parseExtraKeys(values))
      message.success('创建成功')
      setCreateModalVisible(false)
      fetchData()
    } catch {
      message.error('创建失败')
    }
  }

  const handleUpdate = async (values: any) => {
    if (!selectedChannel) return
    try {
      await updateChannel(selectedChannel.channel_id, parseExtraKeys(values))
      message.success('更新成功')
      setEditModalVisible(false)
      fetchData()
    } catch {
      message.error('更新失败')
    }
  }

  // extra_keys 在表单上是 JSON 字符串，后端 ChannelCreate 要求 List[str]。
  // 空串 → 删字段；否则解析 JSON 数组，解析失败给出明确提示。
  const parseExtraKeys = (values: any) => {
    const payload = { ...values }
    if (typeof payload.extra_keys !== 'string') return payload
    const trimmed = payload.extra_keys.trim()
    if (!trimmed) {
      delete payload.extra_keys
      return payload
    }
    let parsed: unknown
    try {
      parsed = JSON.parse(trimmed)
    } catch {
      message.warning('额外 Keys 格式错误，需为 JSON 数组，例如 ["sk-1","sk-2"]')
      throw new Error('invalid extra_keys')
    }
    if (!Array.isArray(parsed) || !parsed.every((k) => typeof k === 'string')) {
      message.warning('额外 Keys 需为字符串数组')
      throw new Error('invalid extra_keys')
    }
    payload.extra_keys = parsed
    return payload
  }

  const handleTestConnection = async () => {
    const v = form.getFieldsValue(['type', 'endpoint', 'api_key'])
    if (!v.endpoint || !v.api_key) {
      message.warning('请先填写 API 端点和 API Key')
      return
    }
    const hide = message.loading('正在测试连接...', 0)
    setTestLoading(true)
    try {
      const res = await testChannelConnection({
        type: v.type || 'openai',
        endpoint: v.endpoint,
        api_key: v.api_key,
        timeout: 30,
      })
      hide()
      if (res.success) {
        const latency = res.latency_ms != null ? ` (${res.latency_ms}ms)` : ''
        message.success(`连接成功${latency}`)
      } else {
        const code = res.status_code != null ? ` (HTTP ${res.status_code})` : ''
        message.error(`${res.message}${code}`, 5)
      }
    } catch (e: any) {
      hide()
      const detail = e?.response?.data?.detail || e?.message || '请求失败'
      message.error(typeof detail === 'string' ? detail : '请求参数错误', 5)
    } finally {
      setTestLoading(false)
    }
  }

  const handleDelete = async (channelId: string) => {
    try {
      await deleteChannel(channelId)
      message.success('删除成功')
      fetchData()
    } catch {
      message.error('删除失败')
    }
  }

  const handleConfig = async (values: any) => {
    if (!selectedChannel) return
    try {
      await updateChannelQuota(selectedChannel.channel_id, values)
      message.success('配置更新成功')
      setConfigModalVisible(false)
      fetchData()
    } catch {
      message.error('配置更新失败')
    }
  }

  const openModelModal = (channel: Channel) => {
    navigate(`/admin/channels/${channel.channel_id}/bindings`)
  }

  const handleSyncModels = async () => {
    if (!selectedChannel) return
    try {
      await syncChannelModels(selectedChannel.channel_id)
      message.success('同步成功')
      await openModelModal(selectedChannel)
    } catch {
      message.error('同步失败')
    }
  }

  const handleBindModel = async (modelId: string, upstreamModel: string) => {
    if (!selectedChannel) return
    setBindLoading(true)
    try {
      await bindChannelToModel(selectedChannel.channel_id, {
        channel_id: selectedChannel.channel_id,
        upstream_model: upstreamModel || modelId
      })
      message.success('绑定成功')
      await openModelModal(selectedChannel)
    } catch {
      message.error('绑定失败')
    } finally {
      setBindLoading(false)
    }
  }

  const handleUnbindModel = async (modelId: string) => {
    if (!selectedChannel) return
    try {
      await unbindChannel(modelId, selectedChannel.channel_id)
      message.success('解绑成功')
      await openModelModal(selectedChannel)
    } catch {
      message.error('解绑失败')
    }
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { 
      title: '类型', dataIndex: 'type', key: 'type', width: 100,
      render: (type: string) => <Tag>{type}</Tag>
    },
    { 
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>{status}</Tag>
      )
    },
    { 
      title: '健康', dataIndex: 'health_status', key: 'health_status', width: 100,
      render: (h: string) => {
        const colors = { healthy: 'green', degraded: 'orange', unhealthy: 'red' }
        return <Tag color={colors[h as keyof typeof colors] || 'default'}>{h}</Tag>
      }
    },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
    { 
      title: '配额', key: 'quota', width: 200,
      render: (_: any, record: Channel) => {
        const quota = quotas[record.channel_id]
        const stats = calcQuotaStats(quota)
        if (!stats) return <span style={{ color: '#999' }}>未配置</span>
        return (
          <div style={{ fontSize: 12 }}>
            <div>小时: <Progress percent={Math.round(stats.hourlyUsedPercent)} size="small" style={{ width: 100, display: 'inline' }} /></div>
            <div>周: <Progress percent={Math.round(stats.weeklyUsedPercent)} size="small" style={{ width: 100, display: 'inline' }} /></div>
          </div>
        )
      }
    },
    { 
      title: '绑定模型', key: 'bound_models', width: 100,
      render: (_: any, record: Channel) => (
        <Button type="link" onClick={() => openModelModal(record)}>
          {record.bound_models_count || 0}
        </Button>
      )
    },
    {
      title: '操作', key: 'action', width: 200,
      render: (_: any, record: Channel) => (
        <Space>
          <Tooltip title="编辑"><Button size="small" icon={<EditOutlined />} onClick={() => {
            setSelectedChannel(record)
            form.setFieldsValue(record)
            setEditModalVisible(true)
          }} /></Tooltip>
          <Tooltip title="同步配额"><Button size="small" icon={<SyncOutlined />} onClick={() => handleSync(record.channel_id)} /></Tooltip>
          <Tooltip title="配置"><Button size="small" icon={<SettingOutlined />} onClick={() => {
            setSelectedChannel(record)
            configForm.setFieldsValue({
              quota_hourly: record.quota_hourly,
              quota_weekly: record.quota_weekly,
              sync_enabled: record.sync_enabled,
              sync_interval: record.sync_interval
            })
            setConfigModalVisible(true)
          }} /></Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.channel_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ]

return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>渠道管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          form.resetFields()
          setCreateModalVisible(true)
        }}>新建渠道</Button>
      </div>

      <Table columns={columns} dataSource={channels} rowKey="channel_id" loading={loading} />

      {/* 创建 Modal */}
      <Modal title="新建渠道" open={createModalVisible} onCancel={() => setCreateModalVisible(false)} onOk={() => form.submit()} width={600}>
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="type" label="类型" rules={[{ required: true }]}>
                <Select>
                  <Select.Option value="openai">OpenAI</Select.Option>
                  <Select.Option value="anthropic">Anthropic</Select.Option>
                  <Select.Option value="azure">Azure</Select.Option>
                  <Select.Option value="deepseek">DeepSeek</Select.Option>
                  <Select.Option value="minimax">MiniMax</Select.Option>
                  <Select.Option value="volcengine">火山引擎</Select.Option>
                  <Select.Option value="custom">自定义</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="endpoint" label="API 端点"><Input placeholder="https://api.openai.com/v1" /></Form.Item>
          <Form.Item label="API Key" required>
            <Row gutter={8}>
              <Col flex="auto">
                <Form.Item name="api_key" noStyle rules={[{ required: true, message: '请输入 API Key' }]}>
                  <Input.Password placeholder="sk-..." />
                </Form.Item>
              </Col>
              <Col>
                <Button icon={<ApiOutlined />} loading={testLoading} onClick={handleTestConnection}>
                  测试连接
                </Button>
              </Col>
            </Row>
          </Form.Item>
          <Form.Item name="extra_keys" label="额外 Keys (JSON 数组)"><Input.TextArea rows={2} placeholder='["sk-xxx1", "sk-xxx2"]' /></Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="key_strategy" label="Key 策略" initialValue="round_robin">
                <Select>
                  <Select.Option value="round_robin">轮询</Select.Option>
                  <Select.Option value="random">随机</Select.Option>
                  <Select.Option value="sequential">顺序</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="priority" label="优先级" initialValue={0}><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="timeout" label="超时(秒)" initialValue={60}><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 编辑 Modal */}
      <Modal title="编辑渠道" open={editModalVisible} onCancel={() => setEditModalVisible(false)} onOk={() => form.submit()} width={600}>
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="type" label="类型" rules={[{ required: true }]}>
                <Select>
                  <Select.Option value="openai">OpenAI</Select.Option>
                  <Select.Option value="anthropic">Anthropic</Select.Option>
                  <Select.Option value="azure">Azure</Select.Option>
                  <Select.Option value="deepseek">DeepSeek</Select.Option>
                  <Select.Option value="minimax">MiniMax</Select.Option>
                  <Select.Option value="volcengine">火山引擎</Select.Option>
                  <Select.Option value="custom">自定义</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="endpoint" label="API 端点"><Input /></Form.Item>
          <Form.Item label="API Key">
            <Row gutter={8}>
              <Col flex="auto">
                <Form.Item name="api_key" noStyle>
                  <Input.Password placeholder="不修改请留空" />
                </Form.Item>
              </Col>
              <Col>
                <Button icon={<ApiOutlined />} loading={testLoading} onClick={handleTestConnection}>
                  测试连接
                </Button>
              </Col>
            </Row>
          </Form.Item>
          <Form.Item name="extra_keys" label="额外 Keys"><Input.TextArea rows={2} /></Form.Item>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="key_strategy" label="Key 策略">
                <Select>
                  <Select.Option value="round_robin">轮询</Select.Option>
                  <Select.Option value="random">随机</Select.Option>
                  <Select.Option value="sequential">顺序</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="priority" label="优先级"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="timeout" label="超时(秒)"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
          </Row>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 配置 Modal */}
      <Modal title="配额配置" open={configModalVisible} onCancel={() => setConfigModalVisible(false)} onOk={() => configForm.submit()}>
        <Form form={configForm} onFinish={handleConfig} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="quota_hourly" label="小时配额"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="quota_weekly" label="周配额"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </Col>
          </Row>
          <Form.Item name="sync_enabled" label="自动同步" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="sync_interval" label="同步间隔(秒)">
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 模型绑定 Modal */}
      <Modal title={`${selectedChannel?.name} - 绑定模型`} open={modelModalVisible} onCancel={() => setModelModalVisible(false)} footer={null} width={800}>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button icon={<SyncOutlined />} onClick={handleSyncModels}>同步模型</Button>
          </Space>
        </div>
        <Table
          dataSource={selectedChannelModels}
          rowKey="model_id"
          columns={[
            { title: '平台模型', dataIndex: 'model_id', key: 'model_id' },
            { title: '上游模型', dataIndex: 'upstream_model', key: 'upstream_model' },
            { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
            { 
              title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80,
              render: (enabled: boolean) => <Tag color={enabled ? 'green' : 'red'}>{enabled ? '启用' : '禁用'}</Tag>
            },
            {
              title: '操作', key: 'action', width: 100,
              render: (_: any, record: any) => (
                <Popconfirm title="确认解绑？" onConfirm={() => handleUnbindModel(record.model_id)}>
                  <Button size="small" danger>解绑</Button>
                </Popconfirm>
              )
            }
          ]}
          pagination={false}
        />
        <div style={{ marginTop: 16 }}>
          <h4>添加绑定</h4>
          <Space wrap>
            {allModels.filter(m => !selectedChannelModels.find(sm => sm.model_id === m.model_id)).map(m => (
              <Tag key={m.model_id} style={{ cursor: 'pointer' }} onClick={() => handleBindModel(m.model_id, m.model_id)}>
                + {m.display_name || m.model_id}
              </Tag>
            ))}
          </Space>
        </div>
      </Modal>
    </div>
  )
}

export default ChannelsPage
