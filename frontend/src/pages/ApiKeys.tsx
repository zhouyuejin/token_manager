import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../utils/message'
import {
  Table, Button, Tag, Space, Modal, Form, Input, DatePicker, InputNumber,
  Popconfirm, Segmented, Select, Drawer, Descriptions, Alert
} from 'antd'
import { PlusOutlined, DeleteOutlined, CopyOutlined, SyncOutlined, StopOutlined } from '@ant-design/icons'
import { createApiKey, deleteApiKey, updateApiKey, updateAdminApiKey, revokeApiKey, rotateApiKey, unfreezeApiKey, updateApiKeyStatus, ApiKey } from '../api/apiKeys'
import { useAuthStore } from '../store/auth'
import { useSwrData } from '../hooks/useSwr'
import { formatApiKeyWhitelist, parseApiKeyWhitelist } from '../utils/apiKeyWhitelist'
import dayjs from 'dayjs'
import { getApiKeyStatus, maskKey } from '../utils/security'

const ApiKeysPage = () => {
  const isAdmin = useAuthStore(state => state.user?.role === 'admin')
  const [adminView, setAdminView] = useState(false)
  // 使用 SWR 获取 API Keys
  const { data: keysData, isLoading, error: keysError, mutate: mutateKeys } = useSwrData<{total: number; items: ApiKey[]}>(adminView && isAdmin ? '/api-keys/admin' : '/api-keys', { refreshInterval: 30000, revalidateOnFocus: true })
  const [userFilter, setUserFilter] = useState<string>()
  const [statusFilter, setStatusFilter] = useState<string>()
  const [detailKeyId, setDetailKeyId] = useState<string | null>(null)
  const allKeys = keysData?.items || []
  const keysList = allKeys.filter(key => !(adminView && isAdmin) ||
    ((!userFilter || key.user_id === userFilter) && (!statusFilter || getApiKeyStatus(key) === statusFilter)))
  const detailKey = allKeys.find(key => key.key_id === detailKeyId)
  const statusLabels: Record<string, string> = { active: '启用', disabled: '禁用', frozen: '自动冻结', revoked: '已吊销', expired: '已过期' }
  const formatTime = (value?: string | null) => value ? dayjs.utc(value).local().format('YYYY-MM-DD HH:mm:ss') : '—'

  const [modalVisible, setModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [newKeyTitle, setNewKeyTitle] = useState('创建 API Key')
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()
  const message = useMessage()
  const { token, isDark } = useThemeToken()

  const fetchKeys = async () => {
    mutateKeys()
  }

  const handleCreate = async (values: any) => {
    try {
      const result = await createApiKey({
        name: values.name,
        ip_whitelist: parseApiKeyWhitelist(values.ip_whitelist),
        expires_at: values.expires_at?.toISOString?.() || null,
        qps_limit: values.qps_limit ?? 0,
        rpm_limit: values.rpm_limit ?? 0,
        tpm_limit: values.tpm_limit ?? 0,
        concurrency_limit: values.concurrency_limit ?? 0,
      })
      setNewKeyTitle('创建 API Key')
      setNewKey(result.api_key)
      message.success('创建成功')
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleEdit = (record: ApiKey) => {
    setEditingKey(record)
    editForm.setFieldsValue({
      name: record.name,
      ip_whitelist: formatApiKeyWhitelist(record.ip_whitelist),
      expires_at: record.expires_at ? dayjs.utc(record.expires_at).local() : null,
      qps_limit: record.qps_limit,
      rpm_limit: record.rpm_limit,
      tpm_limit: record.tpm_limit,
      concurrency_limit: record.concurrency_limit,
    })
    setEditModalVisible(true)
  }

  const handleUpdate = async (values: any) => {
    if (!editingKey) return
    try {
      await (adminView && isAdmin ? updateAdminApiKey : updateApiKey)(editingKey.key_id, {
        name: values.name,
        ip_whitelist: parseApiKeyWhitelist(values.ip_whitelist),
        expires_at: values.expires_at?.toISOString?.() || null,
        qps_limit: values.qps_limit ?? 0,
        rpm_limit: values.rpm_limit ?? 0,
        tpm_limit: values.tpm_limit ?? 0,
        concurrency_limit: values.concurrency_limit ?? 0,
      })
      message.success('更新成功')
      setEditModalVisible(false)
      setEditingKey(null)
      editForm.resetFields()
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleDelete = async (keyId: string) => {
    try {
      await deleteApiKey(keyId)
      message.success('删除成功')
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleRevoke = async (keyId: string) => {
    try {
      await revokeApiKey(keyId, '用户手动吊销')
      message.success('吊销成功')
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleRotate = async (keyId: string) => {
    try {
      const result = await rotateApiKey(keyId)
      setNewKeyTitle('轮换 API Key')
      setNewKey(result.api_key)
      setModalVisible(true)
      message.success('轮换成功')
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleUnfreeze = async (keyId: string) => {
    try {
      await unfreezeApiKey(keyId)
      message.success('解除冻结成功')
      fetchKeys()
    } catch (error) {
      console.error(error)
    }
  }

  const handleStatusChange = async (record: ApiKey) => {
    try {
      await updateApiKeyStatus(record.key_id, record.status === 'active' ? 'disabled' : 'active')
      message.success('状态已更新')
      fetchKeys()
    } catch { /* 统一请求拦截器显示错误 */ }
  }

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key)
    message.success('已复制到剪贴板')
  }

  const getLifecycleStatus = getApiKeyStatus

  const renderRateLimits = (record: ApiKey) => {
    const limits = [
      ['QPS', record.qps_limit],
      ['RPM', record.rpm_limit],
      ['TPM', record.tpm_limit],
      ['并发', record.concurrency_limit],
    ].filter(([, value]) => Number(value) > 0)

    if (limits.length === 0) {
      return <span style={{ color: token.colorTextSecondary }}>不限制</span>
    }

    return (
      <Space size={[4, 4]} wrap>
        {limits.map(([label, value]) => (
          <Tag key={label} style={{ margin: 0, borderRadius: 6 }}>
            {label}: {value}
          </Tag>
        ))}
      </Space>
    )
  }

  const columns = [
    ...(adminView && isAdmin ? [{ title: '所属用户', dataIndex: 'user_id', key: 'user_id' }] : []),
    { 
      title: 'Key名称', 
      dataIndex: 'name', 
      key: 'name',
      render: (text: string) => (
        <span style={{ color: token.colorText, fontWeight: 500 }}>{text}</span>
      )
    },
    { 
      title: 'Key', 
      dataIndex: 'api_key', 
      key: 'api_key',
      render: (key: string) => (
        <span style={{ 
          fontFamily: "'Space Grotesk', sans-serif", 
          color: token.colorTextSecondary,
          fontSize: 13,
        }}>
          {maskKey(key)}
        </span>
      )
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (_: string, record: ApiKey) => {
        const status = getLifecycleStatus(record)
        const success = status === 'active'
        return (
          <Tag
            color={success ? 'success' : 'error'}
            style={{
              borderRadius: '6px',
              background: success ? 'rgba(34, 197, 94, 0.15)' : 'rgba(220, 38, 38, 0.15)',
              border: 'none',
            }}
          >
            {statusLabels[status] || status}
          </Tag>
        )
      }
    },
    {
      title: '安全原因',
      key: 'freeze_info',
      render: (_: unknown, record: ApiKey) => record.frozen_at ? (
        <Space direction="vertical" size={2}>
          <span>{record.frozen_reason || '异常调用'}</span>
          <span style={{ color: token.colorTextSecondary }}>
            {dayjs.utc(record.frozen_at).local().format('YYYY-MM-DD HH:mm:ss')}
          </span>
        </Space>
      ) : <span style={{ color: token.colorTextSecondary }}>{record.revoked_reason || (getLifecycleStatus(record) === 'expired' ? '已超过过期时间' : '—')}</span>
    },
    {
      title: 'IP白名单',
      dataIndex: 'ip_whitelist',
      key: 'ip_whitelist',
      render: (value?: string[]) => {
        const list = value || []
        if (list.length === 0) {
          return <span style={{ color: token.colorTextSecondary }}>不限制</span>
        }
        return (
          <Space size={[4, 4]} wrap>
            {list.slice(0, 3).map((item) => (
              <Tag key={item} style={{ margin: 0, borderRadius: 6 }}>{item}</Tag>
            ))}
            {list.length > 3 && <Tag style={{ margin: 0, borderRadius: 6 }}>+{list.length - 3}</Tag>}
          </Space>
        )
      }
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      render: (val?: string | null) => (
        <span style={{ color: token.colorTextSecondary }}>
          {val ? dayjs.utc(val).local().format('YYYY-MM-DD HH:mm') : '永不过期'}
        </span>
      )
    },
    {
      title: '限流',
      key: 'rate_limits',
      render: (_: unknown, record: ApiKey) => renderRateLimits(record)
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => (
        <span style={{ color: token.colorTextSecondary }}>
          {dayjs.utc(val).local().format('YYYY-MM-DD HH:mm')}
        </span>
      )
    },
    {
      title: '最近使用',
      key: 'last_used',
      render: (_: unknown, record: ApiKey) => <Space direction="vertical" size={2}><span>{formatTime(record.last_used_at)}</span><span>{record.last_used_ip || '—'}</span></Space>
    },
    {
      title: '详情',
      key: 'detail',
      render: (_: unknown, record: ApiKey) => <Button type="link" onClick={() => setDetailKeyId(record.key_id)}>查看详情</Button>
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ApiKey) => adminView && isAdmin ? (
        <Space><Button type="text" onClick={() => handleEdit(record)}>编辑安全配置</Button>
        {record.status === 'disabled' && record.frozen_at ? (
          <Popconfirm
            title="确认解除冻结？请先核查异常调用来源。"
            onConfirm={() => handleUnfreeze(record.key_id)}
          >
            <Button type="text">解除冻结</Button>
          </Popconfirm>
        ) : null}</Space>
      ) : (
        <Space>
          <Button 
            type="text" 
            onClick={() => handleEdit(record)}
            style={{ color: '#10B981' }}
          >
            编辑
          </Button>
          <Popconfirm title={record.status === 'active' ? '确认禁用此 Key？' : '确认启用此 Key？'} onConfirm={() => handleStatusChange(record)}>
            <Button type="text" disabled={!!record.frozen_at || getLifecycleStatus(record) === 'revoked'}>{record.status === 'active' ? '禁用' : '启用'}</Button>
          </Popconfirm>
          <Popconfirm
            title="确认轮换此Key？旧密钥会立即失效。"
            onConfirm={() => handleRotate(record.key_id)}
          >
            <Button type="text" disabled={!!record.frozen_at} icon={<SyncOutlined />} style={{ color: '#8B5CF6' }}>
              轮换
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确认吊销此Key？吊销后不能再调用代理。"
            onConfirm={() => handleRevoke(record.key_id)}
          >
            <Button type="text" disabled={getLifecycleStatus(record) === 'revoked'} icon={<StopOutlined />} danger>
              吊销
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确认删除此Key？"
            onConfirm={() => handleDelete(record.key_id)}
          >
            <Button type="text" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

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
          API Key 管理
        </h2>
        <Space>
          {isAdmin && (
            <Segmented
              options={['我的 Key', '全部 Key']}
              value={adminView ? '全部 Key' : '我的 Key'}
              onChange={value => setAdminView(value === '全部 Key')}
            />
          )}
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => { setNewKey(null); setNewKeyTitle('创建 API Key'); form.resetFields(); setModalVisible(true) }}
            style={{
              background: token.colorPrimary,
              border: 'none',
              borderRadius: 10,
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 500,
            }}
          >
            创建 API Key
          </Button>
        </Space>
      </div>

      {adminView && isAdmin && <Space wrap style={{ marginBottom: 16 }}>
        <Select allowClear showSearch placeholder="按所属用户筛选" style={{ width: 240 }} value={userFilter} onChange={setUserFilter}
          options={[...new Set(allKeys.map(key => key.user_id))].map(id => ({ label: id, value: id }))} />
        <Select allowClear placeholder="按安全状态筛选" style={{ width: 180 }} value={statusFilter} onChange={setStatusFilter}
          options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
      </Space>}
      {keysError && <Alert type="error" showIcon message="API Key 列表加载失败" description={<Button onClick={() => mutateKeys()}>重新加载</Button>} style={{ marginBottom: 16 }} />}
      <Table
        scroll={{ x: 'max-content' }}
        columns={columns}
        dataSource={keysList}
        rowKey="key_id"
        loading={isLoading}
        style={{ 
          background: token.colorBgContainer,
          borderRadius: 12,
          overflow: 'hidden',
        }}
      />

      <Drawer title="API Key 安全详情" open={!!detailKeyId} onClose={() => setDetailKeyId(null)} width={560}>
        {detailKey && <>
          {detailKey.frozen_at && <Alert type="error" showIcon message={detailKey.frozen_reason || '异常调用自动冻结'} description="请核查调用来源和客户端凭证，联系管理员解除冻结。" style={{ marginBottom: 16 }} />}
          <Descriptions column={1} bordered>
            <Descriptions.Item label="名称">{detailKey.name}</Descriptions.Item>
            <Descriptions.Item label="Key ID">{detailKey.key_id}</Descriptions.Item>
            <Descriptions.Item label="Key">{maskKey(detailKey.api_key)}</Descriptions.Item>
            <Descriptions.Item label="所属用户">{detailKey.user_id}</Descriptions.Item>
            <Descriptions.Item label="状态">{statusLabels[getLifecycleStatus(detailKey)] || detailKey.status}</Descriptions.Item>
            <Descriptions.Item label="IP 白名单">{formatApiKeyWhitelist(detailKey.ip_whitelist) || '不限制'}</Descriptions.Item>
            <Descriptions.Item label="过期时间">{detailKey.expires_at ? formatTime(detailKey.expires_at) : '永不过期'}</Descriptions.Item>
            <Descriptions.Item label="吊销时间">{formatTime(detailKey.revoked_at)}</Descriptions.Item>
            <Descriptions.Item label="吊销原因">{detailKey.revoked_reason || '—'}</Descriptions.Item>
            <Descriptions.Item label="冻结时间">{formatTime(detailKey.frozen_at)}</Descriptions.Item>
            <Descriptions.Item label="冻结原因">{detailKey.frozen_reason || '—'}</Descriptions.Item>
            <Descriptions.Item label="最后使用时间">{formatTime(detailKey.last_used_at)}</Descriptions.Item>
            <Descriptions.Item label="最后使用 IP">{detailKey.last_used_ip || '—'}</Descriptions.Item>
            <Descriptions.Item label="User-Agent">{detailKey.last_used_user_agent || '—'}</Descriptions.Item>
            {(['qps_limit', 'rpm_limit', 'tpm_limit', 'concurrency_limit'] as const).map((field, i) =>
              <Descriptions.Item key={field} label={['QPS', 'RPM', 'TPM（估算 Token）', '并发'][i]}>{detailKey[field] || '不限制'}</Descriptions.Item>)}
          </Descriptions>
        </>}
      </Drawer>
      {/* 创建Key弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: token.colorText,
          }}>
            {newKeyTitle}
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setNewKey(null)
          form.resetFields()
        }}
        footer={newKey ? null : [
          <Button key="cancel" onClick={() => setModalVisible(false)}>
            取消
          </Button>,
          <Button 
            key="submit" 
            type="primary"
            onClick={() => form.submit()}
            style={{
              background: token.colorPrimary,
              border: 'none',
              borderRadius: 10,
            }}
          >
            创建
          </Button>,
        ]}
        style={{ top: 100 }}
      >
        {newKey ? (
          <div>
            <div style={{
              padding: '12px 16px',
              background: 'rgba(234, 88, 12, 0.15)',
              borderRadius: 10,
              marginBottom: 20,
              border: '1px solid rgba(234, 88, 12, 0.3)',
            }}>
              <p style={{ 
                color: '#F59E0B', 
                margin: 0,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                ⚠️ 请立即复制并保存！此Key只显示一次，后续无法查看。
              </p>
            </div>
            <Space.Compact block>
              <Input 
                value={newKey} 
                readOnly 
                style={{
                  fontFamily: "'Space Grotesk', monospace",
                  background: token.colorBgContainer,
                  border: `1px solid ${token.colorBorder}`,
                  borderRight: 'none',
                  borderTopRightRadius: 0,
                  borderBottomRightRadius: 0,
                }}
              />
              <Button
                type="text"
                icon={<CopyOutlined style={{ color: '#3B82F6' }} />}
                onClick={() => copyKey(newKey)}
                style={{
                  border: `1px solid ${token.colorBorder}`,
                  borderLeft: 'none',
                  borderTopLeftRadius: 0,
                  borderBottomLeftRadius: 0,
                }}
              />
            </Space.Compact>
            <Button 
              type="primary" 
              block 
              style={{ 
                marginTop: 20,
                height: 40,
                borderRadius: 10,
                background: token.colorPrimary,
                border: 'none',
                fontFamily: "'Space Grotesk', sans-serif",
              }}
              onClick={() => {
                setNewKey(null)
                setModalVisible(false)
                form.resetFields()
              }}
            >
              我已保存
            </Button>
          </div>
        ) : (
          <Form form={form} onFinish={handleCreate} layout="vertical">
            <Form.Item
              name="name"
              label={<span style={{ color: token.colorText }}>Key名称</span>}
              rules={[{ required: true, message: '请输入Key名称' }]}
            >
              <Input
                placeholder="请输入Key名称"
                style={{
                  height: 40,
                  background: token.colorBgContainer,
                  border: `1px solid ${token.colorBorder}`,
                  borderRadius: 10,
                }}
              />
            </Form.Item>
            <Form.Item
              name="ip_whitelist"
              label={<span style={{ color: token.colorText }}>IP白名单</span>}
              extra="每行或逗号分隔一个 IP/CIDR，留空表示不限制。"
            >
              <Input.TextArea
                placeholder={'例如：\n10.0.0.1\n10.0.0.0/8'}
                autoSize={{ minRows: 3, maxRows: 6 }}
                style={{
                  background: token.colorBgContainer,
                  border: `1px solid ${token.colorBorder}`,
                  borderRadius: 10,
                }}
              />
            </Form.Item>
            <Form.Item
              name="expires_at"
              label={<span style={{ color: token.colorText }}>过期时间</span>}
              extra="留空表示永不过期。"
            >
              <DatePicker
                showTime
                style={{ width: '100%', height: 40, borderRadius: 10 }}
                placeholder="请选择过期时间"
              />
            </Form.Item>
            <Space size={12} style={{ width: '100%' }} wrap>
              <Form.Item
                name="qps_limit"
                label={<span style={{ color: token.colorText }}>QPS</span>}
                extra="0 表示不限制。"
                initialValue={0}
              >
                <InputNumber min={0} precision={0} style={{ width: 120 }} />
              </Form.Item>
              <Form.Item
                name="rpm_limit"
                label={<span style={{ color: token.colorText }}>RPM</span>}
                extra="0 表示不限制。"
                initialValue={0}
              >
                <InputNumber min={0} precision={0} style={{ width: 120 }} />
              </Form.Item>
              <Form.Item
                name="tpm_limit"
                label={<span style={{ color: token.colorText }}>TPM</span>}
                extra="0 表示不限制。"
                initialValue={0}
              >
                <InputNumber min={0} precision={0} style={{ width: 120 }} />
              </Form.Item>
              <Form.Item
                name="concurrency_limit"
                label={<span style={{ color: token.colorText }}>并发</span>}
                extra="0 表示不限制。"
                initialValue={0}
              >
                <InputNumber min={0} precision={0} style={{ width: 120 }} />
              </Form.Item>
            </Space>
          </Form>
        )}
      </Modal>

      {/* 编辑Key弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: token.colorText,
          }}>
            编辑 API Key
          </span>
        }
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          setEditingKey(null)
          editForm.resetFields()
        }}
        footer={null}
        style={{ top: 100 }}
      >
        <Form form={editForm} onFinish={handleUpdate} layout="vertical">
          <Form.Item
            name="name"
            label={<span style={{ color: token.colorText }}>Key名称</span>}
            rules={[{ required: true, message: '请输入Key名称' }]}
          >
            <Input
              placeholder="请输入Key名称"
              style={{
                height: 40,
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
              }}
            />
          </Form.Item>
          <Form.Item
            name="ip_whitelist"
            label={<span style={{ color: token.colorText }}>IP白名单</span>}
            extra="每行或逗号分隔一个 IP/CIDR，留空表示不限制。"
          >
            <Input.TextArea
              placeholder={'例如：\n10.0.0.1\n10.0.0.0/8'}
              autoSize={{ minRows: 3, maxRows: 6 }}
              style={{
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
              }}
            />
          </Form.Item>
          <Form.Item
            name="expires_at"
            label={<span style={{ color: token.colorText }}>过期时间</span>}
            extra="留空表示永不过期。"
          >
            <DatePicker
              showTime
              style={{ width: '100%', height: 40, borderRadius: 10 }}
              placeholder="请选择过期时间"
            />
          </Form.Item>
          <Space size={12} style={{ width: '100%' }} wrap>
            <Form.Item
              name="qps_limit"
              label={<span style={{ color: token.colorText }}>QPS</span>}
              extra="0 表示不限制。"
            >
              <InputNumber min={0} precision={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item
              name="rpm_limit"
              label={<span style={{ color: token.colorText }}>RPM</span>}
              extra="0 表示不限制。"
            >
              <InputNumber min={0} precision={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item
              name="tpm_limit"
              label={<span style={{ color: token.colorText }}>TPM</span>}
              extra="0 表示不限制。"
            >
              <InputNumber min={0} precision={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item
              name="concurrency_limit"
              label={<span style={{ color: token.colorText }}>并发</span>}
              extra="0 表示不限制。"
            >
              <InputNumber min={0} precision={0} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button
                onClick={() => setEditModalVisible(false)}
                style={{
                  borderRadius: 10,
                  border: `1px solid ${token.colorBorder}`,
                }}
              >
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                style={{
                  background: token.colorPrimary,
                  border: 'none',
                  borderRadius: 10,
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
              >
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ApiKeysPage
