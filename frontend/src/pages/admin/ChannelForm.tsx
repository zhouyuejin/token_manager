import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMessage } from '../../utils/message'
import {
  Card, Button, Space, Form, Input, InputNumber, Select, Row, Col,
  Collapse, Typography, Alert
} from 'antd'
import { ArrowLeftOutlined, ApiOutlined, SaveOutlined } from '@ant-design/icons'
import {
  getChannel, createChannel, updateChannel, testChannelConnection
} from '../../api/channels'
import { prepareChannelPayload } from '../../utils/channelForm'

const { Title } = Typography

const ChannelForm: React.FC = () => {
  const { channelId } = useParams<{ channelId?: string }>()
  const navigate = useNavigate()
  const message = useMessage()
  const [form] = Form.useForm()
  const [submitLoading, setSubmitLoading] = useState(false)
  const [fetchLoading, setFetchLoading] = useState(false)
  const [testLoading, setTestLoading] = useState(false)

  const isEdit = !!channelId
  const [extraKeyMasks, setExtraKeyMasks] = useState<string[]>([])
  const mainKeyAction = Form.useWatch('main_key_action', form)
  const extraKeysAction = Form.useWatch('extra_keys_action', form)

  useEffect(() => {
    if (!isEdit) return
    const loadChannel = async () => {
      setFetchLoading(true)
      try {
        const ch = await getChannel(channelId)
        // api_key 不回填，保证安全
        form.setFieldsValue({
          ...ch,
          api_key: '',
        })
        setExtraKeyMasks(ch.extra_keys || [])
        form.setFieldsValue({ main_key_action: 'keep', extra_keys_action: 'keep', extra_keys: '', extra_key_edits: (ch.extra_keys || []).map(() => ({ action: 'keep', value: '' })) })
        if (ch.auth_headers != null) {
          form.setFieldValue('auth_headers', JSON.stringify(ch.auth_headers))
        }
      } catch {
        message.error('加载渠道信息失败')
        navigate('/admin/channels')
      } finally {
        setFetchLoading(false)
      }
    }
    loadChannel()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelId, isEdit])

  const handleCreate = async (values: any) => {
    try {
      const payload = prepareChannelPayload(values, false)
      await createChannel(payload)
      message.success('创建成功')
      navigate('/admin/channels')
    } catch {
      /* error already displayed by parseExtraKeys / parseAuthHeaders */
    }
  }

  const handleUpdate = async (values: any) => {
    if (!channelId) return
    try {
      const payload = prepareChannelPayload(values, true)
      await updateChannel(channelId, payload)
      message.success('更新成功')
      navigate('/admin/channels')
    } catch {
      /* error already displayed */
    }
  }

  const handleSubmit = async () => {
    setSubmitLoading(true)
    try {
      await form.validateFields()
      const values = form.getFieldsValue()
      if (isEdit) {
        await handleUpdate(values)
      } else {
        await handleCreate(values)
      }
    } catch {
      /* validation error shown by form */
    } finally {
      setSubmitLoading(false)
    }
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
                {isEdit ? '编辑渠道' : '新建渠道'}
              </Title>
            </Space>
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={submitLoading}
              onClick={handleSubmit}
            >
              保存
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 表单内容 */}
      <Card loading={fetchLoading}>
        <Form form={form} onFinish={isEdit ? handleUpdate : handleCreate} layout="vertical">

          {isEdit && <Form.Item name="extra_keys_revision" hidden><Input /></Form.Item>}
          {/* 名称 + 类型 */}
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="名称" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
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

          <Form.Item name="endpoint" label="API 端点">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          {isEdit && <Form.Item name="main_key_action" label="主 Key 操作" initialValue="keep">
            <Select options={[{ value: 'keep', label: '保持原 Key' }, { value: 'replace', label: '替换 Key' }]} />
          </Form.Item>}
          {(!isEdit || mainKeyAction === 'replace') && <Form.Item
            label="API Key"
            required={!isEdit}
            tooltip={isEdit ? '替换后无法重新查看完整明文' : undefined}
          >
            <Row gutter={8}>
              <Col flex="auto">
                <Form.Item
                  name="api_key"
                  noStyle
                  rules={[{ required: true, message: '请输入新的真实 API Key' }]}
                >
                  <Input.Password placeholder={isEdit ? '请输入替换用的新 Key' : 'sk-...'} />
                </Form.Item>
              </Col>
              <Col>
                <Button icon={<ApiOutlined />} loading={testLoading} onClick={handleTestConnection}>
                  测试连接
                </Button>
              </Col>
            </Row>
          </Form.Item>}

          {isEdit && <Form.Item name="extra_keys_action" label={`额外 Key 操作（当前 ${extraKeyMasks.length} 个）`} initialValue="keep">
            <Select options={[{ value: 'keep', label: '保持全部原 Key' }, { value: 'edit', label: '逐项替换或移除' }, { value: 'replace', label: '整体替换' }, { value: 'clear', label: '清空全部额外 Key' }]} />
          </Form.Item>}
          {isEdit && extraKeysAction === 'clear' && <Alert type="warning" showIcon message="保存后将移除全部额外 Key。" style={{ marginBottom: 16 }} />}
          {isEdit && extraKeysAction === 'edit' && <Form.List name="extra_key_edits">
            {fields => fields.length ? fields.map(field => <Row key={field.key} gutter={8}>
              <Col span={10}><Form.Item name={[field.name, 'action']} label={`额外 Key ${field.name + 1}（已配置）`}>
                <Select options={[{ value: 'keep', label: '保持原 Key' }, { value: 'replace', label: '替换 Key' }, { value: 'remove', label: '移除此 Key' }]} />
              </Form.Item></Col>
              <Col span={14}><Form.Item noStyle shouldUpdate>
                {() => form.getFieldValue(['extra_key_edits', field.name, 'action']) === 'replace' && <Form.Item name={[field.name, 'value']} label="新 Key" rules={[{ required: true, whitespace: true, message: '请输入真实 Key' }]}>
                  <Input.Password autoComplete="new-password" placeholder="请输入新 Key" />
                </Form.Item>}
              </Form.Item></Col>
            </Row>) : <Alert type="info" message="暂无额外 Key，可选择整体替换添加。" style={{ marginBottom: 16 }} />}
          </Form.List>}
          {(!isEdit || extraKeysAction === 'replace') && <Form.Item
            name="extra_keys"
            label="额外 Keys (JSON 数组)"
            tooltip={'["sk-xxx1", "sk-xxx2"]'}
          >
            <Input.TextArea rows={2} placeholder={isEdit ? '输入完整的新 Key 数组，保存后替换全部额外 Key' : '["sk-xxx1", "sk-xxx2"]'} />
          </Form.Item>}

          {/* key_strategy + priority + timeout */}
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
              <Form.Item name="priority" label="优先级" initialValue={0}>
                <InputNumber style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="timeout" label="超时(秒)" initialValue={60}>
                <InputNumber style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {/* 编辑模式显示状态切换 */}
          {isEdit && (
            <Form.Item name="status" label="状态">
              <Select>
                <Select.Option value="active">启用</Select.Option>
                <Select.Option value="disabled">禁用</Select.Option>
              </Select>
            </Form.Item>
          )}

          <Collapse
            ghost
            items={[
              {
                key: 'advanced',
                label: '高级选项（一般无需修改）',
                children: (
                  <>
                    <Form.Item
                      name="upstream_format"
                      label="上游 API 格式"
                      initialValue="auto"
                      tooltip="默认自动即可。Anthropic 官方API选 anthropic，GCP Gemini 选 gemini。"
                    >
                      <Select>
                        <Select.Option value="auto">自动</Select.Option>
                        <Select.Option value="chat">Chat Completions</Select.Option>
                        <Select.Option value="anthropic">Anthropic Messages</Select.Option>
                        <Select.Option value="gemini">Gemini generateContent</Select.Option>
                        <Select.Option value="responses">OpenAI Responses</Select.Option>
                        <Select.Option value="custom">自定义</Select.Option>
                      </Select>
                    </Form.Item>

                    <Form.Item
                      name="auth_type"
                      label="认证方式"
                      initialValue="auto"
                      tooltip="默认自动已覆盖大多数场景"
                    >
                      <Select>
                        <Select.Option value="auto">自动</Select.Option>
                        <Select.Option value="bearer">Bearer</Select.Option>
                        <Select.Option value="api_key">API Key (x-api-key)</Select.Option>
                        <Select.Option value="azure_api_key">Azure API Key</Select.Option>
                        <Select.Option value="query_key">Query Parameter</Select.Option>
                      </Select>
                    </Form.Item>

                    <Form.Item
                      name="auth_headers"
                      label="额外请求头 (JSON)"
                      tooltip='例如 Anthropic 需要 {"anthropic-version": "2023-06-01"}'
                    >
                      <Input.TextArea rows={3} placeholder={'{"anthropic-version": "2023-06-01"}'} />
                    </Form.Item>
                  </>
                ),
              },
            ]}
          />

        </Form>
      </Card>
    </div>
  )
}

export default ChannelForm
