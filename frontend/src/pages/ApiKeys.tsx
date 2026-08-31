import { useState, useEffect } from 'react'
import { useMessage } from '../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  InputNumber, Popconfirm, Select 
} from 'antd'
import { PlusOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'
import { getApiKeys, createApiKey, deleteApiKey, updateApiKey, ApiKey } from '../api/apiKeys'
import { getModelGroups, ModelGroup } from '../api/modelGroups'
import dayjs from 'dayjs'

const ApiKeysPage = () => {
  const [loading, setLoading] = useState(false)
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [groups, setGroups] = useState<ModelGroup[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()
  const message = useMessage()

  useEffect(() => {
    fetchKeys()
    fetchGroups()
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

  const fetchGroups = async () => {
    try {
      const data = await getModelGroups()
      setGroups(data.items || [])
    } catch (error) {
      console.error(error)
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

  const handleEdit = (record: ApiKey) => {
    setEditingKey(record)
    editForm.setFieldsValue({
      name: record.name,
      daily_limit: record.daily_limit,
      monthly_limit: record.monthly_limit,
      qps_limit: record.qps_limit,
      model_group_ids: record.model_groups || []
    })
    setEditModalVisible(true)
  }

  const handleUpdate = async (values: any) => {
    if (!editingKey) return
    try {
      await updateApiKey(editingKey.key_id, values)
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

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key)
    message.success('已复制到剪贴板')
  }

  const getGroupNames = (groupIds: string[]) => {
    return groupIds.map(id => {
      const group = groups.find(g => g.group_id === id)
      return group?.name || id
    }).join(', ')
  }

  const columns = [
    { 
      title: 'Key名称', 
      dataIndex: 'name', 
      key: 'name',
      render: (text: string) => (
        <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
      )
    },
    { 
      title: 'Key', 
      dataIndex: 'api_key', 
      key: 'api_key',
      render: (key: string) => (
        <span style={{ 
          fontFamily: "'Space Grotesk', sans-serif", 
          color: '#94A3B8',
          fontSize: 13,
        }}>
          {key.substring(0, 10)}...{key.substring(key.length - 4)}
        </span>
      )
    },
    { 
      title: '模型分组', 
      dataIndex: 'model_groups', 
      key: 'model_groups',
      render: (groupIds: string[]) => (
        groupIds && groupIds.length > 0 ? (
          <Tag color="blue">{getGroupNames(groupIds)}</Tag>
        ) : (
          <Tag>未分组</Tag>
        )
      )
    },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag 
          color={status === 'active' ? 'success' : 'error'}
          style={{ 
            borderRadius: '6px',
            background: status === 'active' ? 'rgba(34, 197, 94, 0.15)' : 'rgba(220, 38, 38, 0.15)',
            border: 'none',
          }}
        >
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    { 
      title: '日限额', 
      dataIndex: 'daily_limit', 
      key: 'daily_limit',
      render: (val: number) => (
        <span style={{ 
          fontFamily: "'Space Grotesk', sans-serif", 
          color: '#CBD5E1' 
        }}>
          {val > 0 ? val.toLocaleString() : '不限'}
        </span>
      )
    },
    { 
      title: '月限额', 
      dataIndex: 'monthly_limit', 
      key: 'monthly_limit',
      render: (val: number) => (
        <span style={{ 
          fontFamily: "'Space Grotesk', sans-serif", 
          color: '#CBD5E1' 
        }}>
          {val > 0 ? val.toLocaleString() : '不限'}
        </span>
      )
    },
    { 
      title: '创建时间', 
      dataIndex: 'created_at', 
      key: 'created_at',
      render: (val: string) => (
        <span style={{ color: '#94A3B8' }}>
          {dayjs.utc(val).local().format('YYYY-MM-DD HH:mm')}
        </span>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ApiKey) => (
        <Space>
          <Button 
            type="text" 
            icon={<CopyOutlined />} 
            onClick={() => copyKey(record.api_key)}
            style={{ color: '#3B82F6' }}
          >
            复制
          </Button>
          <Button 
            type="text" 
            onClick={() => handleEdit(record)}
            style={{ color: '#10B981' }}
          >
            编辑
          </Button>
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
          color: '#F8FAFC',
          margin: 0,
        }}>
          API Key 管理
        </h2>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => setModalVisible(true)}
          style={{
            background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
            border: 'none',
            borderRadius: 10,
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 500,
          }}
        >
          创建 API Key
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={keys}
        rowKey="key_id"
        loading={loading}
        style={{ 
          background: 'rgba(30, 41, 59, 0.5)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      />

      {/* 创建Key弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            创建 API Key
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setNewKey(null)
          form.resetFields()
        }}
        footer={newKey ? null : undefined}
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
            <Input 
              value={newKey} 
              readOnly 
              style={{
                fontFamily: "'Space Grotesk', monospace",
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
              }}
              addonAfter={
                <CopyOutlined 
                  style={{ cursor: 'pointer', color: '#3B82F6' }} 
                  onClick={() => copyKey(newKey)} 
                />
              }
            />
            <Button 
              type="primary" 
              block 
              style={{ 
                marginTop: 20,
                height: 40,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
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
              label={<span style={{ color: '#CBD5E1' }}>Key名称</span>} 
              rules={[{ required: true, message: '请输入Key名称' }]}
            >
              <Input 
                placeholder="请输入Key名称" 
                style={{
                  height: 40,
                  background: 'rgba(30, 41, 59, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: 10,
                }}
              />
            </Form.Item>
            
            <Form.Item 
              name="model_group_ids" 
              label={<span style={{ color: '#CBD5E1' }}>模型分组</span>}
            >
              <Select
                mode="multiple"
                placeholder="选择可用的模型分组"
                allowClear
              >
                {groups.filter(g => g.status === 'active').map(g => (
                  <Select.Option key={g.group_id} value={g.group_id}>
                    {g.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item 
              name="daily_limit" 
              label={<span style={{ color: '#CBD5E1' }}>日限额</span>}
            >
              <InputNumber 
                min={0} 
                placeholder="0表示不限" 
                style={{ width: '100%', height: 40 }}
              />
            </Form.Item>
            <Form.Item 
              name="monthly_limit" 
              label={<span style={{ color: '#CBD5E1' }}>月限额</span>}
            >
              <InputNumber 
                min={0} 
                placeholder="0表示不限" 
                style={{ width: '100%', height: 40 }}
              />
            </Form.Item>
            <Form.Item 
              name="qps_limit" 
              label={<span style={{ color: '#CBD5E1' }}>QPS限制</span>}
            >
              <InputNumber 
                min={1} 
                max={100} 
                defaultValue={10} 
                style={{ width: '100%', height: 40 }}
              />
            </Form.Item>
            <Form.Item style={{ marginTop: 24 }}>
              <Space>
                <Button 
                  onClick={() => setModalVisible(false)}
                  style={{
                    borderRadius: 10,
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                  }}
                >
                  取消
                </Button>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  style={{
                    background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                    border: 'none',
                    borderRadius: 10,
                    fontFamily: "'Space Grotesk', sans-serif",
                  }}
                >
                  创建
                </Button>
              </Space>
            </Form.Item>
          </Form>
        )}
      </Modal>

      {/* 编辑Key弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
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
            label={<span style={{ color: '#CBD5E1' }}>Key名称</span>} 
            rules={[{ required: true, message: '请输入Key名称' }]}
          >
            <Input 
              placeholder="请输入Key名称" 
              style={{
                height: 40,
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 10,
              }}
            />
          </Form.Item>
          
          <Form.Item 
            name="model_group_ids" 
            label={<span style={{ color: '#CBD5E1' }}>模型分组</span>}
          >
            <Select
              mode="multiple"
              placeholder="选择可用的模型分组"
              allowClear
            >
              {groups.filter(g => g.status === 'active').map(g => (
                <Select.Option key={g.group_id} value={g.group_id}>
                  {g.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item 
            name="daily_limit" 
            label={<span style={{ color: '#CBD5E1' }}>日限额</span>}
          >
            <InputNumber 
              min={0} 
              placeholder="0表示不限" 
              style={{ width: '100%', height: 40 }}
            />
          </Form.Item>
          <Form.Item 
            name="monthly_limit" 
            label={<span style={{ color: '#CBD5E1' }}>月限额</span>}
          >
            <InputNumber 
              min={0} 
              placeholder="0表示不限" 
              style={{ width: '100%', height: 40 }}
            />
          </Form.Item>
          <Form.Item 
            name="qps_limit" 
            label={<span style={{ color: '#CBD5E1' }}>QPS限制</span>}
          >
            <InputNumber 
              min={1} 
              max={100} 
              style={{ width: '100%', height: 40 }}
            />
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button 
                onClick={() => setEditModalVisible(false)}
                style={{
                  borderRadius: 10,
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                }}
              >
                取消
              </Button>
              <Button 
                type="primary" 
                htmlType="submit"
                style={{
                  background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
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
