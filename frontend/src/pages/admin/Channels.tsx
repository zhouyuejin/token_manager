import { useState, useEffect } from 'react'
import { useSwrData } from '../../hooks/useSwr'
import { useNavigate } from 'react-router-dom'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, Switch, 
  Select, Popconfirm, Row, Col, Progress, Tooltip, Card
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CloudOutlined, SettingOutlined, ApiOutlined } from '@ant-design/icons'
import { 
  getChannels, deleteChannel,
  getAllChannelQuotas, syncChannelQuota, updateChannelQuota, Channel, 
  getChannelModels, syncChannelModels
} from '../../api/channels'
import { getModels, Model, bindChannelToModel, unbindChannel, getModelChannels } from '../../api/models'

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
      const [configModalVisible, setConfigModalVisible] = useState(false)
  const [modelModalVisible, setModelModalVisible] = useState(false)
  const [selectedChannelModels, setSelectedChannelModels] = useState<any[]>([])
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null)
  const [configForm] = Form.useForm()
  const message = useMessage()
  const { token } = useThemeToken()
  const [allModels, setAllModels] = useState<Model[]>([])
  const [bindLoading, setBindLoading] = useState(false)

  // 使用 SWR 获取数据
  const { data: channelsData, mutate: mutateChannels } = useSwrData<{total: number; items: Channel[]}>('/admin/channels')
  const { data: quotasData, mutate: mutateQuotas } = useSwrData<{total: number; items: any[]}>('/admin/channels/quotas')
  const { data: modelsData, mutate: mutateModels } = useSwrData<{total: number; items: Model[]}>('/admin/models')

  const channelsList = channelsData?.items || []
  const modelsList = modelsData?.items || []

  // 将 quotas 转换为 map
  const quotasMap: Record<string, any> = {}
  if (quotasData?.items) {
    quotasData.items.forEach((item: any) => { quotasMap[item.channel_id] = item })
  }

  const fetchData = async () => {
    mutateChannels()
    mutateQuotas()
    mutateModels()
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
        const quota = quotasMap[record.channel_id]
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
          <Tooltip title="编辑"><Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/admin/channels/${record.channel_id}/edit`)} /></Tooltip>
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
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/admin/channels/new')}>新建渠道</Button>
      </div>

      <Table columns={columns} dataSource={channelsList} rowKey="channel_id" loading={loading} />


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
