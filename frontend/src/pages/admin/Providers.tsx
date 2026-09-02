import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, Switch, 
  Select, Popconfirm, Row, Col, Progress, Collapse, Tooltip
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SyncOutlined, CloudOutlined, SettingOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { 
  getProviders, createProvider, updateProvider, deleteProvider,
  getAllProviderQuotas, syncProviderQuota, updateProviderQuota, Provider, 
  getProviderModels, syncProviderModels, syncAllProviderModels
} from '../../api/providers'
import { getModels, ModelMapping } from '../../api/models'


// 时间格式化
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

// 计算用量统计
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

const ProvidersPage = () => {
  const [loading, setLoading] = useState(false)
  const [providers, setProviders] = useState<Provider[]>([])
  const [quotas, setQuotas] = useState<Record<string, any>>({})
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [configModalVisible, setConfigModalVisible] = useState(false)
  const [syncLoading, setSyncLoading] = useState<string | null>(null)
  const [modelModalVisible, setModelModalVisible] = useState(false)
  const [selectedProviderModels, setSelectedProviderModels] = useState<any[]>([])
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null)
  const [modelPagination, setModelPagination] = useState({ current: 1, pageSize: 20, total: 0 })
  const [modelLoading, setModelLoading] = useState(false)
  const [allModels, setAllModels] = useState<ModelMapping[]>([])
  const [form] = Form.useForm()
  const [configForm] = Form.useForm()
  const message = useMessage()
  const { token, isDark } = useThemeToken()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [providersRes, quotasRes, modelsRes] = await Promise.all([
        getProviders(),
        getAllProviderQuotas(),
        getModels()
      ])
      setAllModels(modelsRes.items || [])
      setProviders(providersRes.items || [])
      
      const quotaMap: Record<string, any> = {}
      quotasRes.items?.forEach((item: any) => {
        quotaMap[item.provider_id] = item
      })
      setQuotas(quotaMap)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // 手动同步用量
  const handleSync = async (providerId: string) => {
    try {
      await syncProviderQuota(providerId)
      message.success('同步成功')
      fetchData()
    } catch (error) {
      message.error('同步失败')
    }
  }

  // 同步供应商模型
  const handleSyncModels = async (providerId: string) => {
    setSyncLoading(providerId)
    try {
      const result = await syncProviderModels(providerId)
      if (result.success) {
        message.success(`成功同步 ${result.count} 个模型`)
        fetchData()
      } else {
        message.error(result.message || '同步失败')
      }
    } catch (error) {
      message.error('同步失败')
    } finally {
      setSyncLoading(null)
    }
  }

  // 批量同步所有供应商模型
  const handleSyncAllModels = async () => {
    setSyncLoading('all')
    try {
      const result = await syncAllProviderModels()
      message.success(`成功同步 ${result.success} 个供应商，失败 ${result.failed} 个`)
      fetchData()
    } catch (error) {
      message.error('批量同步失败')
    } finally {
      setSyncLoading(null)
    }
  }

  // 查看供应商模型列表
  const handleViewModels = async (provider: Provider, page: number = 1) => {
    setModelLoading(true)
    try {
      const result = await getProviderModels(provider.provider_id, page, modelPagination.pageSize)
      setSelectedProviderModels(result.items || [])
      setSelectedProvider(provider)
      setModelPagination({
        current: result.page,
        pageSize: result.page_size,
        total: result.total
      })
      setModelModalVisible(true)
    } catch (error) {
      message.error('获取模型列表失败')
    } finally {
      setModelLoading(false)
    }
  }

  // 分页变化
  const handleModelPageChange = (page: number, pageSize: number) => {
    if (selectedProvider) {
      setModelPagination({ ...modelPagination, current: page, pageSize })
      handleViewModels(selectedProvider, page)
    }
  }

  // 创建供应商
  const handleCreate = async (values: any) => {
    try {
      await createProvider(values)
      message.success('创建成功')
      setCreateModalVisible(false)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  // 更新供应商
  const handleUpdate = async (values: any) => {
    if (!selectedProvider) return
    try {
      await updateProvider(selectedProvider.provider_id, values)
      message.success('更新成功')
      setEditModalVisible(false)
      setSelectedProvider(null)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  // 更新用量配置
  const handleQuotaUpdate = async (values: any) => {
    if (!selectedProvider) return
    try {
      await updateProviderQuota(selectedProvider.provider_id, {
        quota_hourly: values.quota_hourly,
        quota_weekly: values.quota_weekly,
        sync_enabled: values.sync_enabled,
        sync_interval: values.sync_interval ? values.sync_interval * 60 : 300,  // 分钟转秒
        quota_config: values.enable_custom_config ? {
          model_name: values.model_name || undefined,
          custom_api_path: values.custom_api_path || undefined,
        } : undefined,
      })
      message.success('配置更新成功')
      // 更新本地数据并关闭弹窗
      setSelectedProvider({ ...selectedProvider, ...values })
      setConfigModalVisible(false)
      fetchData()
    } catch (error) {
      message.error('更新失败')
    }
  }

  // 删除供应商
  const handleDelete = async (providerId: string) => {
    try {
      await deleteProvider(providerId)
      message.success('删除成功')
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  // 打开编辑弹窗
  const openEditModal = (provider: Provider) => {
    setSelectedProvider(provider)
    form.setFieldsValue({
      ...provider,
      enabled_models: provider.enabled_models || []
    })
    setEditModalVisible(true)
  }

  // 打开用量配置弹窗
  const openConfigModal = (provider: Provider) => {
    setSelectedProvider(provider)
    configForm.setFieldsValue({
      ...provider,
      quota_hourly: provider.quota_hourly,
      quota_weekly: provider.quota_weekly,
      sync_enabled: provider.sync_enabled,
      sync_interval: provider.sync_interval ? provider.sync_interval / 60 : 5,
      enable_custom_config: !!provider.quota_config,
      model_name: provider.quota_config?.model_name || '',
      custom_api_path: provider.quota_config?.custom_api_path || '',
    })
    setConfigModalVisible(true)
  }

  // 渲染用量进度条
  const renderQuotaProgress = (usedPercent: number, remainPercent: number, total: number, remainTime: number) => {
    if (usedPercent === 0 && remainPercent === 0 && total === 0) {
      return <span style={{ color: token.colorTextTertiary, fontSize: 12 }}>暂无数据</span>
    }
    return (
      <div style={{ minWidth: 180 }}>
        <Progress 
          percent={Math.round(remainPercent)} 
          size="small"
          status={remainPercent < 10 ? 'exception' : 'normal'}
          strokeColor={{ '0%': '#10B981', '100%': '#3B82F6' }}
          trailColor="rgba(30, 41, 59, 0.8)"
        />
        <div style={{ fontSize: 11, color: '#10B981', marginTop: 4 }}>
          剩余 {Math.round(remainPercent)}% · {formatRemainTime(remainTime)}
        </div>
      </div>
    )
  }

  // ========== 渲染页面 ==========
  return (
    <div className="stagger-children">
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24, alignItems: 'center' }}>
        <h2 style={{ fontSize: 24, fontWeight: 600, color: token.colorText, margin: 0 }}>
          <CloudOutlined style={{ marginRight: 12, color: '#3B82F6' }} />
          供应商管理
        </h2>
        <Space>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={() => setCreateModalVisible(true)}
            style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none', borderRadius: 10 }}
          >
            添加供应商
          </Button>
        </Space>
      </div>

      {/* 供应商列表 */}
      <div style={{
        background: token.colorBgContainer,
        backdropFilter: 'blur(20px)',
        border: `1px solid ${token.colorBorder}`,
        borderRadius: 16,
        overflow: 'hidden',
      }}>
        <Table
          dataSource={providers}
          columns={[
            { title: '供应商', dataIndex: 'name', key: 'name', render: (t: string) => <span style={{ color: token.colorText, fontWeight: 500 }}>{t}</span> },
            { title: '类型', dataIndex: 'type', key: 'type', render: (t: string) => <span style={{ color: token.colorTextSecondary }}>{t}</span> },
            { 
              title: '5小时用量', key: 'hourly',
              render: (_: any, record: Provider) => {
                const stats = calcQuotaStats(quotas[record.provider_id])
                if (!stats) return <span style={{ color: token.colorTextTertiary }}>-</span>
                return renderQuotaProgress(stats.hourlyUsedPercent, stats.hourlyRemainPercent, stats.hourlyTotal, stats.hourlyRemainTime)
              }
            },
            { 
              title: '周用量', key: 'weekly',
              render: (_: any, record: Provider) => {
                const stats = calcQuotaStats(quotas[record.provider_id])
                if (!stats) return <span style={{ color: token.colorTextTertiary }}>-</span>
                return renderQuotaProgress(stats.weeklyUsedPercent, stats.weeklyRemainPercent, stats.weeklyTotal, stats.weeklyRemainTime)
              }
            },
            { 
              title: '状态', dataIndex: 'status', key: 'status',
              render: (status: string) => (
                <Tag color={status === 'active' ? 'success' : 'error'} style={{ borderRadius: 6, background: status === 'active' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(220, 38, 38, 0.15)', border: 'none' }}>
                  {status === 'active' ? '启用' : '禁用'}
                </Tag>
              )
            },
            {
              title: '操作', key: 'action',
              render: (_: any, record: Provider) => (
                <Space>
                  <Button type="text" icon={<SettingOutlined />} onClick={() => openConfigModal(record)} style={{ color: '#10B981' }}>用量配置</Button>
                  <Button type="text" icon={<EditOutlined />} onClick={() => openEditModal(record)} style={{ color: '#3B82F6' }}>编辑</Button>
                  <Popconfirm title="确认删除此供应商？" onConfirm={() => handleDelete(record.provider_id)}>
                    <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
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

      {/* 用量配置弹窗 */}
      <Modal
        title={<span style={{ color: token.colorText }}><SettingOutlined style={{ marginRight: 8 }} />{selectedProvider?.name} - 用量配置</span>}
        open={configModalVisible}
        onCancel={() => { setConfigModalVisible(false); setSelectedProvider(null); }}
        footer={null}
        width={560}
      >
        <Form form={configForm} onFinish={handleQuotaUpdate} layout="vertical">
          {/* 额度配置 */}
          <div style={{ marginBottom: 20, padding: 16, background: 'rgba(15, 23, 42, 0.5)', borderRadius: 8 }}>
            <h4 style={{ color: token.colorText, marginBottom: 16 }}>额度设置</h4>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="quota_hourly" label={<span style={{ color: token.colorTextSecondary }}>5小时额度</span>}>
                  <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="quota_weekly" label={<span style={{ color: token.colorTextSecondary }}>周额度</span>}>
                  <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%', height: 40 }} />
                </Form.Item>
              </Col>
            </Row>
          </div>

          {/* 同步配置 */}
          <div style={{ marginBottom: 20, padding: 16, background: 'rgba(15, 23, 42, 0.5)', borderRadius: 8 }}>
            <h4 style={{ color: token.colorText, marginBottom: 16 }}>同步设置</h4>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item name="sync_enabled" label={<span style={{ color: token.colorTextSecondary }}>自动同步</span>} valuePropName="checked">
                  <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="sync_interval" label={<span style={{ color: token.colorTextSecondary }}>同步间隔(分钟)</span>}>
                  <InputNumber min={1} max={60} style={{ width: '100%', height: 40 }} />
                </Form.Item>
              </Col>
            </Row>
          </div>

          {/* 自定义查询配置 */}
          <div style={{ marginBottom: 20, padding: 16, background: 'rgba(15, 23, 42, 0.5)', borderRadius: 8 }}>
            <h4 style={{ color: token.colorText, marginBottom: 16 }}>
              <Space>自定义查询 <Tooltip title="不同供应商用量API不同，可自定义配置"><QuestionCircleOutlined style={{ color: token.colorTextTertiary }} /></Tooltip></Space>
            </h4>
            <Form.Item name="enable_custom_config" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
            <Collapse ghost items={[
              {
                key: 'advanced',
                label: '高级配置',
                children: (
                  <>
                    <Form.Item name="model_name" label={<span style={{ color: token.colorTextSecondary }}>模型名称</span>}>
                      <Input placeholder="如：gpt-4o、claude-3-opus" />
                    </Form.Item>
                    <Form.Item name="custom_api_path" label={<span style={{ color: token.colorTextSecondary }}>自定义API路径</span>}>
                      <Input placeholder="如：/v1/usage/custom" />
                    </Form.Item>
                  </>
                )
              }
            ]} />
          </div>

          {/* 当前用量状态 */}
          {selectedProvider && (() => {
            const stats = calcQuotaStats(quotas[selectedProvider.provider_id])
            if (!stats) return null
            return (
              <div style={{ marginBottom: 20, padding: 16, background: 'rgba(15, 23, 42, 0.5)', borderRadius: 8 }}>
                <h4 style={{ color: token.colorText, marginBottom: 16 }}>当前用量</h4>
                <Row gutter={16}>
                  <Col span={12}>
                    <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>5小时</div>
                    <div style={{ color: token.colorText, fontSize: 20, fontWeight: 600 }}>{Math.round(stats.hourlyUsedPercent)}%</div>
                    <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>已用 {stats.hourlyTotal} 次</div>
                  </Col>
                  <Col span={12}>
                    <div style={{ color: token.colorTextSecondary, fontSize: 12 }}>本周</div>
                    <div style={{ color: token.colorText, fontSize: 20, fontWeight: 600 }}>{Math.round(stats.weeklyUsedPercent)}%</div>
                    <div style={{ color: token.colorTextTertiary, fontSize: 12 }}>已用 {stats.weeklyTotal} 次</div>
                  </Col>
                </Row>
              </div>
            )
          })()}

          {/* 按钮 */}
          <Form.Item style={{ marginTop: 24, marginBottom: 0 }}>
            <Space>
              <Button icon={<SyncOutlined />} onClick={() => selectedProvider && handleSync(selectedProvider.provider_id)}>手动同步</Button>
              <Button type="primary" htmlType="submit" style={{ background: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)', border: 'none' }}>保存配置</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 添加供应商弹窗 */}
      <Modal
        title={<span style={{ color: token.colorText }}>添加供应商</span>}
        open={createModalVisible}
        onCancel={() => { setCreateModalVisible(false); form.resetFields(); }}
        footer={null}
        width={560}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="name" label={<span style={{ color: token.colorTextSecondary }}>供应商名称</span>} rules={[{ required: true }]}>
            <Input placeholder="如：火山方舟" />
          </Form.Item>
          <Form.Item name="type" label={<span style={{ color: token.colorTextSecondary }}>类型</span>} rules={[{ required: true }]}>
            <Select placeholder="请选择类型">
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="google">Google</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="minimax">MiniMax</Select.Option>
              <Select.Option value="deepseek">DeepSeek</Select.Option>
              <Select.Option value="zhipu">智谱清言</Select.Option>
              <Select.Option value="cohere">Cohere</Select.Option>
              <Select.Option value="mistral">Mistral</Select.Option>
              <Select.Option value="bedrock">AWS Bedrock</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label={<span style={{ color: token.colorTextSecondary }}>API端点</span>} rules={[{ required: true }]}>
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="api_key" label={<span style={{ color: token.colorTextSecondary }}>API Key</span>} rules={[{ required: true }]}>
            <Input.Password placeholder="请输入API Key" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label={<span style={{ color: token.colorTextSecondary }}>优先级</span>} initialValue={100}>
                <InputNumber min={1} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label={<span style={{ color: token.colorTextSecondary }}>超时(秒)</span>} initialValue={60}>
                <InputNumber min={10} max={300} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="enabled_models" label={<span style={{ color: token.colorTextSecondary }}>关联模型（可选）</span>}>
            <Select mode="multiple" placeholder="选择该供应商可用的模型" allowClear>
              {allModels.filter(m => m.status === 'active').map(m => (
                <Select.Option key={m.model_id} value={m.model_id}>
                  {m.display_name || m.model_id} ({m.provider_model})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <div style={{ padding: 12, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8, marginBottom: 16 }}>
            <div style={{ color: '#3B82F6', fontSize: 12 }}>💡 提示：创建供应商后可手动同步模型，然后在模型管理中添加定价</div>
          </div>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setCreateModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none' }}>创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑供应商弹窗 */}
      <Modal
        title={<span style={{ color: token.colorText }}>编辑供应商</span>}
        open={editModalVisible}
        onCancel={() => { setEditModalVisible(false); setSelectedProvider(null); form.resetFields(); }}
        footer={null}
        width={560}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="name" label={<span style={{ color: token.colorTextSecondary }}>供应商名称</span>} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label={<span style={{ color: token.colorTextSecondary }}>类型</span>} rules={[{ required: true }]}>
            <Select>
              <Select.Option value="openai">OpenAI</Select.Option>
              <Select.Option value="anthropic">Anthropic</Select.Option>
              <Select.Option value="google">Google</Select.Option>
              <Select.Option value="azure">Azure OpenAI</Select.Option>
              <Select.Option value="volcengine">火山方舟</Select.Option>
              <Select.Option value="moonshot">Moonshot</Select.Option>
              <Select.Option value="baidu">百度千帆</Select.Option>
              <Select.Option value="minimax">MiniMax</Select.Option>
              <Select.Option value="deepseek">DeepSeek</Select.Option>
              <Select.Option value="zhipu">智谱清言</Select.Option>
              <Select.Option value="cohere">Cohere</Select.Option>
              <Select.Option value="mistral">Mistral</Select.Option>
              <Select.Option value="bedrock">AWS Bedrock</Select.Option>
              <Select.Option value="custom">自定义</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="endpoint" label={<span style={{ color: token.colorTextSecondary }}>API端点</span>} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="api_key" label={<span style={{ color: token.colorTextSecondary }}>API Key（留空不修改）</span>}>
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="priority" label={<span style={{ color: token.colorTextSecondary }}>优先级</span>}>
                <InputNumber min={1} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="timeout" label={<span style={{ color: token.colorTextSecondary }}>超时(秒)</span>}>
                <InputNumber min={10} max={300} style={{ width: '100%', height: 40 }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="status" label={<span style={{ color: token.colorTextSecondary }}>状态</span>}>
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="enabled_models" label={<span style={{ color: token.colorTextSecondary }}>关联模型</span>}>
            <Select mode="multiple" placeholder="选择该供应商可用的模型" allowClear>
              {allModels.filter(m => m.status === 'active').map(m => (
                <Select.Option key={m.model_id} value={m.model_id}>
                  {m.display_name || m.model_id} ({m.provider_model})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <div style={{ padding: 12, background: 'rgba(59, 130, 246, 0.1)', borderRadius: 8, marginBottom: 16 }}>
            <SettingOutlined style={{ marginRight: 8, color: '#3B82F6' }} />
            <span style={{ color: '#3B82F6', fontSize: 13 }}>用量配置请到「用量配置」弹窗设置</span>
          </div>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setEditModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)', border: 'none' }}>保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 模型列表弹窗 */}
      <Modal
        title={<span style={{ color: token.colorText }}>{selectedProvider?.name} - 模型映射列表</span>}
        open={modelModalVisible}
        onCancel={() => { setModelModalVisible(false); setSelectedProvider(null); setSelectedProviderModels([]); }}
        footer={null}
        width={800}
      >
        {selectedProviderModels.length === 0 && !modelLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: token.colorTextSecondary }}>
            暂无可用模型，请先在模型映射中添加
          </div>
        ) : (
          <Table
            dataSource={selectedProviderModels}
            columns={[
              { title: '平台模型ID', dataIndex: 'model_id', key: 'model_id', render: (t: string) => <span style={{ color: token.colorText }}>{t}</span> },
              { title: '显示名称', dataIndex: 'display_name', key: 'display_name', render: (t: string) => <span style={{ color: token.colorTextSecondary }}>{t || '-'}</span> },
              { title: '上游模型', dataIndex: 'provider_model', key: 'provider_model', render: (t: string) => <span style={{ color: '#10B981' }}>{t}</span> },
              { 
                title: '状态', 
                dataIndex: 'status', 
                key: 'status',
                render: (status: string) => (
                  <Tag color={status === 'active' ? 'success' : 'default'} style={{ borderRadius: 6 }}>
                    {status === 'active' ? '启用' : '禁用'}
                  </Tag>
                )
              },
              { title: '创建时间', dataIndex: 'created_at', key: 'created_at', render: (t: string) => <span style={{ color: token.colorTextTertiary, fontSize: 12 }}>{t ? t.substring(0, 19) : '-'}</span> },
            ]}
            rowKey="model_id"
            loading={modelLoading}
            pagination={{
              current: modelPagination.current,
              pageSize: modelPagination.pageSize,
              total: modelPagination.total,
              onChange: handleModelPageChange,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total: number) => `共 ${total} 条`
            }}
          />
        )}
      </Modal>
    </div>
  )
}

export default ProvidersPage