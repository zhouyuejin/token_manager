import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { Button, Card, Col, Form, Input, InputNumber, Result, Row, Select, Space, Spin, Switch } from 'antd'
import { ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons'
import { getChannel, updateChannelQuota, testChannelQuotaScript, Channel } from '../../api/channels'
import { WriteOnly } from '../../components/WriteOnly'
import { useMessage } from '../../utils/message'

const deepSeekScript = `const response = http.get('/user/balance', {
  headers: { Accept: 'application/json', Authorization: 'Bearer ' + apiKey }
});
const balance = response.data.balance_infos[0];
return { balance, raw_data: response.data };`

const ChannelQuotaPage = () => {
  const { channelId } = useParams<{ channelId: string }>()
  const navigate = useNavigate()
  const { mutate } = useSWRConfig()
  const message = useMessage()
  const [channel, setChannel] = useState<Channel | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [configForm] = Form.useForm()
  const queryMode = Form.useWatch('query_mode', configForm)
  const [scriptTesting, setScriptTesting] = useState(false)
  const [scriptResult, setScriptResult] = useState('')

  useEffect(() => {
    if (!channelId) return
    let active = true
    setLoading(true)
    setLoadError(false)
    setChannel(null)
    setScriptResult('')
    getChannel(channelId).then((data) => {
      if (!active) return
      setChannel(data)
      configForm.setFieldsValue({
        query_mode: data.quota_config?.query_mode === 'script' ? 'script' : 'default',
        script: data.quota_config?.script || '',
        quota_hourly: data.quota_hourly,
        quota_weekly: data.quota_weekly,
        sync_enabled: data.sync_enabled,
        sync_interval: data.sync_interval,
        quota_config: data.quota_config ? JSON.stringify(data.quota_config, null, 2) : '',
      })
    }).catch(() => {
      if (active) setLoadError(true)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [channelId, configForm])

  const handleConfig = async (values: any) => {
    if (!channel) return
    setSaving(true)
    try {
      const { query_mode, script, ...payload } = values
      if (query_mode === 'script') payload.quota_config = { query_mode, script }
      else if (typeof payload.quota_config === 'string') {
        payload.quota_config = payload.quota_config.trim()
          ? JSON.parse(payload.quota_config)
          : null
      }
      if (query_mode !== 'script' && payload.quota_config?.query_mode === 'script') payload.quota_config = null
      await updateChannelQuota(channel.channel_id, payload)
      message.success('配置更新成功')
      await mutate('/admin/channels')
      navigate('/admin/channels')
    } catch (e) {
      if (e instanceof SyntaxError) message.error('用量查询配置不是合法 JSON')
      else message.error('配置更新失败')
    } finally {
      setSaving(false)
    }
  }

  const handleTestScript = async () => {
    if (!channel) return
    setScriptTesting(true)
    setScriptResult('')
    try {
      const result = await testChannelQuotaScript(channel.channel_id, configForm.getFieldValue('script') || '')
      setScriptResult(JSON.stringify(result, null, 2))
    } catch (error: any) {
      setScriptResult(error?.response?.data?.detail || '试运行失败')
    } finally {
      setScriptTesting(false)
    }
  }

  if (loadError) return <Result status="error" title="加载渠道信息失败" extra={<Button onClick={() => navigate('/admin/channels')}>返回渠道列表</Button>} />

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/channels')}>返回</Button>
        <h2 style={{ margin: 0 }}>{channel ? `${channel.name} - 配额配置` : '配额配置'}</h2>
      </Space>
      <Spin spinning={loading}>
        <Card>
          <Form form={configForm} onFinish={handleConfig} layout="vertical" disabled={loading || saving}>
            <Form.Item name="query_mode" label="查询方式">
              <Select options={[{ value: 'default', label: '内置查询 / JSON 配置' }, { value: 'script', label: '自定义 JavaScript' }]} />
            </Form.Item>
            {queryMode === 'script' && <>
              <p>可用变量：endpoint、apiKey。http.get(url, options) / http.post(url, data, options) 同步返回 {'{status, data}'}，支持 headers、params。同源请求最多 3 次，总执行时间 15 秒；不支持 require、系统命令或文件访问。</p>
              <Form.Item name="script" label="查询脚本" rules={[{ required: true, whitespace: true, message: '请输入查询脚本' }]}>
                <Input.TextArea rows={16} maxLength={32768} style={{ fontFamily: 'monospace' }} />
              </Form.Item>
              <p>返回 {'{balance: {currency: "CNY", total_balance: "12.3456"}}'}，或 {'{windows: [{type: "daily", label: "每日", limit: 100, used: 20}]}'}。type 支持 hourly、five_hour、weekly、daily、monthly、custom。</p>
              <WriteOnly><Space style={{ marginBottom: 16 }}>
                <Button onClick={() => { configForm.setFieldValue('script', deepSeekScript); setScriptResult('') }}>填入 DeepSeek 示例</Button>
                <Button loading={scriptTesting} onClick={handleTestScript}>试运行（不保存）</Button>
              </Space></WriteOnly>
              {scriptResult && <pre style={{ maxHeight: 240, overflow: 'auto', whiteSpace: 'pre-wrap' }}>{scriptResult}</pre>}
            </>}
            {channel?.type === 'deepseek' && queryMode !== 'script' && (
              <p>DeepSeek 使用渠道 Key 查询 /user/balance，显示账户余额；无需填写小时、周配额或查询配置。查询配置留空即可自动查询。</p>
            )}
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
            <Form.Item
              name="quota_config"
              hidden={queryMode === 'script'}
              label="用量查询配置(JSON)"
              tooltip='手动模式示例: {"query_mode":"manual","windows":[{"type":"five_hour","label":"5小时","limit":100,"remain":80,"reset_at":"2026-09-14T15:00:00Z"}]}'
            >
              <Input.TextArea rows={6} />
            </Form.Item>
            <Space>
              <WriteOnly><Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving} disabled={!channel}>保存配置</Button></WriteOnly>
              <Button onClick={() => navigate('/admin/channels')}>返回渠道列表</Button>
            </Space>
          </Form>
        </Card>
      </Spin>
    </div>
  )
}

export default ChannelQuotaPage
