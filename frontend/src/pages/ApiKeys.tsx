import { useState, useEffect } from 'react'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  InputNumber, message, Popconfirm 
} from 'antd'
import { PlusOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'
import { getApiKeys, createApiKey, deleteApiKey, ApiKey } from '../api/apiKeys'
import dayjs from 'dayjs'

const ApiKeysPage = () => {
  const [loading, setLoading] = useState(false)
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchKeys()
  }, [])

  const fetchKeys = async () => {
    setLoading(true)
    try {
      const data = await getApiKeys()
      setKeys(data.items || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      const result = await createApiKey(values)
      setNewKey(result.api_key)
      message.success('创建成功')
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

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key)
    message.success('已复制到剪贴板')
  }

  const columns = [
    { title: 'Key名称', dataIndex: 'name', key: 'name' },
    { 
      title: 'Key', 
      dataIndex: 'api_key', 
      key: 'api_key',
      render: (key: string) => (
        <span style={{ fontFamily: 'monospace' }}>
          {key.substring(0, 10)}...{key.substring(key.length - 4)}
        </span>
      )
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    { 
      title: '日限额', 
      dataIndex: 'daily_limit', 
      key: 'daily_limit',
      render: (val: number) => val > 0 ? val.toLocaleString() : '不限'
    },
    { 
      title: '月限额', 
      dataIndex: 'monthly_limit', 
      key: 'monthly_limit',
      render: (val: number) => val > 0 ? val.toLocaleString() : '不限'
    },
    { 
      title: '创建时间', 
      dataIndex: 'created_at', 
      key: 'created_at',
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm')
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ApiKey) => (
        <Space>
          <Button 
            type="link" 
            icon={<CopyOutlined />} 
            onClick={() => copyKey(record.api_key)}
          >
            复制
          </Button>
          <Popconfirm
            title="确认删除此Key？"
            onConfirm={() => handleDelete(record.key_id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>API Key 管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          创建 Key
        </Button>
      </div>

      <Table
        dataSource={keys}
        columns={columns}
        rowKey="key_id"
        loading={loading}
      />

      {/* 创建Key弹窗 */}
      <Modal
        title="创建 API Key"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setNewKey(null)
          form.resetFields()
        }}
        footer={newKey ? null : undefined}
      >
        {newKey ? (
          <div>
            <p style={{ color: '#faad14', marginBottom: 16 }}>
              ⚠️ 请立即复制并保存！此Key只显示一次，后续无法查看。
            </p>
            <Input 
              value={newKey} 
              readOnly 
              addonAfter={
                <CopyOutlined 
                  style={{ cursor: 'pointer' }} 
                  onClick={() => copyKey(newKey)} 
                />
              }
            />
            <Button 
              type="primary" 
              block 
              style={{ marginTop: 16 }}
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
            <Form.Item name="name" label="Key名称" rules={[{ required: true }]}>
              <Input placeholder="请输入Key名称" />
            </Form.Item>
            <Form.Item name="daily_limit" label="日限额">
              <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="monthly_limit" label="月限额">
              <InputNumber min={0} placeholder="0表示不限" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="qps_limit" label="QPS限制">
              <InputNumber min={1} max={100} defaultValue={10} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button onClick={() => setModalVisible(false)}>取消</Button>
                <Button type="primary" htmlType="submit">创建</Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  )
}

export default ApiKeysPage
