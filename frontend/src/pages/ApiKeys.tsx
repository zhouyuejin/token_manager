import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../utils/message'
import {
  Table, Button, Tag, Space, Modal, Form, Input,
  Popconfirm
} from 'antd'
import { PlusOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'
import { createApiKey, deleteApiKey, updateApiKey, ApiKey } from '../api/apiKeys'
import { useSwrData } from '../hooks/useSwr'
import dayjs from 'dayjs'

const ApiKeysPage = () => {
  // 使用 SWR 获取 API Keys
  const { data: keysData, isLoading, mutate: mutateKeys } = useSwrData<{total: number; items: ApiKey[]}>('/api-keys')
  const keysList = keysData?.items || []
  const [modalVisible, setModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null)
  const [newKey, setNewKey] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [editForm] = Form.useForm()
  const message = useMessage()
  const { token, isDark } = useThemeToken()

  const fetchKeys = async () => {
    mutateKeys()
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

  const columns = [
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
          {key.substring(0, 10)}...{key.substring(key.length - 4)}
        </span>
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
          color: token.colorText,
          margin: 0,
        }}>
          API Key 管理
        </h2>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => setModalVisible(true)}
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
      </div>

      <Table
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

      {/* 创建Key弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: token.colorText,
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
