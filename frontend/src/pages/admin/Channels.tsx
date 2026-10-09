import { useEffect, useState } from 'react'
import { useSwrData } from '../../hooks/useSwr'
import { useNavigate } from 'react-router-dom'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal,
  Popconfirm, Progress, Tooltip
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, SettingOutlined } from '@ant-design/icons'
import { 
  getChannels, deleteChannel,
  syncChannelQuota, Channel,
  syncChannelModels, recoverChannelHealth, ChannelHealth
} from '../../api/channels'
import { Model, bindChannelToModel, unbindChannel } from '../../api/models'
import { WriteOnly } from '../../components/WriteOnly'

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
  const windows = quota.windows || [quota.hourly, quota.weekly].filter(Boolean)
  if (windows.length === 0) return null
  const fiveHour = windows.find((w: any) => w.type === 'five_hour') || quota.hourly
  const weekly = windows.find((w: any) => w.type === 'weekly') || quota.weekly
  return {
    hourlyUsedPercent: fiveHour?.percent || 0,
    hourlyTotal: fiveHour?.limit || 0,
    hourlyRemain: fiveHour?.remain || 0,
    hourlyRemainTime: (fiveHour?.reset_in_seconds || 0) * 1000,
    weeklyUsedPercent: weekly?.percent || 0,
    weeklyTotal: weekly?.limit || 0,
    weeklyRemain: weekly?.remain || 0,
    weeklyRemainTime: (weekly?.reset_in_seconds || 0) * 1000,
  }
}

const formatQuotaRemain = (remain: number, total: number, percent?: number) => {
  if (!total || total <= 0) {
    // 上游未返回总量，但可能有进度（percent）；用 percent/100 兜底，避免显示 0/0
    if (percent && percent > 0) return `剩余 ${Math.round(percent)}/100`
    return '剩余 0/0'
  }
  return `剩余 ${remain}/${total}`
}

const healthLabels: Record<string, string> = { healthy: '健康', degraded: '降级', unhealthy: '不健康' }

const ChannelsPage = () => {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const [modelModalVisible, setModelModalVisible] = useState(false)
  const [selectedChannelModels, setSelectedChannelModels] = useState<any[]>([])
  const [selectedChannel] = useState<Channel | null>(null)
  const message = useMessage()
  const { token } = useThemeToken()
  const [allModels, setAllModels] = useState<Model[]>([])
  const [bindLoading, setBindLoading] = useState(false)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  // 使用 SWR 获取数据
  const { data: channelsData, mutate: mutateChannels } = useSwrData<{total: number; items: Channel[]}>('/admin/channels')
  const { data: quotasData, mutate: mutateQuotas } = useSwrData<{total: number; items: any[]}>('/admin/channels/quotas')
  const { data: modelsData, mutate: mutateModels } = useSwrData<{total: number; items: Model[]}>('/admin/models')
  const { data: healthData, mutate: mutateHealth } = useSwrData<{items: ChannelHealth[]}>('/admin/health/channels')

  const channelsList = channelsData?.items || []
  const modelsList = modelsData?.items || []
  const healthMap = Object.fromEntries((healthData?.items || []).map(item => [item.channel_id, item]))

  // 将 quotas 转换为 map
  const quotasMap: Record<string, any> = {}
  if (quotasData?.items) {
    quotasData.items.forEach((item: any) => { quotasMap[item.channel_id] = item })
  }

  const fetchData = async () => {
    mutateChannels()
    mutateQuotas()
    mutateModels()
    mutateHealth()
  }

  const handleRecover = async (channelId: string) => {
    try {
      await recoverChannelHealth(channelId)
      message.success('cooldown 已恢复')
      mutateHealth()
      mutateChannels()
    } catch {
      message.error('恢复 cooldown 失败')
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

  const handleDelete = async (channelId: string) => {
    try {
      await deleteChannel(channelId)
      message.success('删除成功')
      fetchData()
    } catch {
      message.error('删除失败')
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
        <Tag color={status === 'active' ? 'green' : 'red'}>{({ active: '启用', disabled: '禁用' } as Record<string, string>)[status] || status}</Tag>
      )
    },
    { 
      title: '健康', dataIndex: 'health_status', key: 'health_status', width: 100,
      render: (h: string, record: Channel) => {
        h = healthMap[record.channel_id]?.health_status || h
        const colors = { healthy: 'green', degraded: 'orange', unhealthy: 'red' }
        return <Tag color={colors[h as keyof typeof colors] || 'default'}>{healthLabels[h] || h || '未知'}</Tag>
      }
    },
    {
      title: '上游格式', dataIndex: 'upstream_format', key: 'upstream_format', width: 150,
      render: (format?: string) => <Tag color="blue">{({ auto: '自动', chat: 'Chat', anthropic: 'Anthropic', gemini: 'Gemini', responses: 'Responses', custom: '供应商自定义' } as Record<string, string>)[format || 'auto'] || format || '自动'}</Tag>,
    },
    {
      title: 'Cooldown', key: 'cooldown', width: 180,
      render: (_: unknown, record: Channel) => {
        const health = healthMap[record.channel_id]
        const channelUntil = health?.cooldown.channel_until
        const keyCount = health?.cooldown.keys.length || 0
        if (!channelUntil && !keyCount) return <Tag color="green">未冷却</Tag>
        return <Space direction="vertical" size={0}>
          {channelUntil && <Tag title={new Date(channelUntil).toLocaleString()} color="orange">渠道剩余 {formatRemainTime(new Date(channelUntil).getTime() - now)}</Tag>}
          {keyCount > 0 && <span style={{ fontSize: 12, color: '#d97706' }}>{keyCount} 个 Key 冷却中</span>}
          <WriteOnly><Popconfirm title="确认恢复该渠道及其 Key 的 cooldown？" onConfirm={() => handleRecover(record.channel_id)}>
            <Button type="link" size="small" style={{ padding: 0 }}>手动恢复</Button>
          </Popconfirm></WriteOnly>
        </Space>
      }
    },
    { title: '密钥', key: 'keys', width: 130, render: (_: unknown, record: Channel) => `主 Key ${record.api_key ? '已配置' : '未配置'} · 额外 ${record.extra_keys?.length || 0} 个` },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
    { 
      title: '配额', key: 'quota', width: 200,
      render: (_: any, record: Channel) => {
        const quota = quotasMap[record.channel_id]
        const scriptedBalance = record.quota_config?.query_mode === 'script' && quota?.windows?.find((window: any) => window.raw_data?.provider === 'script' && window.raw_data?.window?.raw_data?.balance)?.raw_data?.window?.raw_data?.balance
        if (scriptedBalance) return <span>余额: {scriptedBalance.total_balance} {scriptedBalance.currency}</span>
        const balanceWindow = quota?.windows?.find((window: any) =>
          window.raw_data?.provider === 'deepseek' && window.type === 'custom'
        )
        const balanceData = balanceWindow?.raw_data?.window?.raw_data
        if (balanceData?.balance_infos) return (
          <div style={{ fontSize: 12 }}>
            {balanceData.balance_infos.map((balance: any) => (
              <div key={balance.currency}>
                <div>余额: {balance.total_balance} {balance.currency}</div>
                <div style={{ color: '#666' }}>赠送: {balance.granted_balance} · 充值: {balance.topped_up_balance}</div>
              </div>
            ))}
            {balanceData.is_available === false && <Tag color="red">余额不可用</Tag>}
          </div>
        )
        const stats = calcQuotaStats(quota)
        if (!stats) return <span style={{ color: '#999' }}>未配置</span>
        if (record.quota_config?.query_mode === 'script' && quota.windows?.some((window: any) => window.raw_data?.provider === 'script')) return (
          <div style={{ fontSize: 12 }}>{quota.windows.filter((window: any) => window.raw_data?.provider === 'script').map((window: any) => (
            <div key={window.type}>
              {window.label || window.type}: 已用 {window.used} · 剩余 {window.remain}/{window.limit}
              <Progress percent={Math.round(window.percent)} size="small" />
              {window.reset_in_seconds != null && <span>{formatRemainTime(window.reset_in_seconds * 1000)}重置</span>}
            </div>
          ))}</div>
        )
        return (
          <div style={{ fontSize: 12 }}>
            <div>5小时: <Progress percent={Math.round(stats.hourlyUsedPercent)} size="small" style={{ width: 100, display: 'inline' }} /></div>
            <div style={{ color: '#666' }}>
              {formatQuotaRemain(stats.hourlyRemain, stats.hourlyTotal, stats.hourlyUsedPercent)} · {formatRemainTime(stats.hourlyRemainTime)}重置
            </div>
            <div>周: <Progress percent={Math.round(stats.weeklyUsedPercent)} size="small" style={{ width: 100, display: 'inline' }} /></div>
            <div style={{ color: '#666' }}>
              {formatQuotaRemain(stats.weeklyRemain, stats.weeklyTotal, stats.weeklyUsedPercent)} · {formatRemainTime(stats.weeklyRemainTime)}重置
            </div>
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
      title: '操作', key: 'action', width: 192, fixed: 'right' as const,
      render: (_: any, record: Channel) => (
        <WriteOnly><Space>
          <Tooltip title="编辑"><Button size="small" icon={<EditOutlined />} onClick={() => navigate(`/admin/channels/${record.channel_id}/edit`)} /></Tooltip>
          <Tooltip title="同步配额"><Button size="small" icon={<SyncOutlined />} onClick={() => handleSync(record.channel_id)} /></Tooltip>
          <Tooltip title="配额配置"><Button size="small" icon={<SettingOutlined />} onClick={() => navigate(`/admin/channels/${record.channel_id}/quota`)} /></Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.channel_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space></WriteOnly>
      )
    }
  ]

return (
  <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h2>渠道管理</h2>
        <WriteOnly><Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/admin/channels/new')}>新建渠道</Button></WriteOnly>
      </div>

      <Table columns={columns} dataSource={channelsList} rowKey="channel_id" loading={loading}
          scroll={{ x: 1500, y: "calc(100vh - 320px)" }} />


      {/* 模型绑定 Modal */}
      <Modal title={`${selectedChannel?.name} - 绑定模型`} open={modelModalVisible} onCancel={() => setModelModalVisible(false)} footer={null} width={800}>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <WriteOnly><Button icon={<SyncOutlined />} onClick={handleSyncModels}>同步模型</Button></WriteOnly>
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
                <WriteOnly>
                <Popconfirm title="确认解绑？" onConfirm={() => handleUnbindModel(record.model_id)}>
                  <Button size="small" danger>解绑</Button>
                </Popconfirm>
                </WriteOnly>
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
