import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, 
  Select, Popconfirm 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, DollarOutlined, TeamOutlined } from '@ant-design/icons'
import { getUsers, createUser, updateUser, deleteUser, adjustQuota, User } from '../../api/users'
import dayjs from 'dayjs'

const UsersPage = () => {
  const [loading, setLoading] = useState(false)
  const [users, setUsers] = useState<User[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [quotaModalVisible, setQuotaModalVisible] = useState(false)
  const [quotaUser, setQuotaUser] = useState<User | null>(null)
  const [form] = Form.useForm()
  const [quotaForm] = Form.useForm()
  const message = useMessage()

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    setLoading(true)
    try {
      const data = await getUsers()
      setUsers(data.items || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createUser(values)
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchUsers()
    } catch (error) {
      console.error(error)
    }
  }

  const handleUpdate = async (values: any) => {
    if (!editUser) return
    try {
      await updateUser(editUser.user_id, values)
      message.success('更新成功')
      setEditUser(null)
      form.resetFields()
      fetchUsers()
    } catch (error) {
      console.error(error)
    }
  }

  const handleDelete = async (userId: string) => {
    try {
      await deleteUser(userId)
      message.success('删除成功')
      fetchUsers()
    } catch (error) {
      console.error(error)
    }
  }

  const handleQuotaAdjust = async (values: { amount: number; reason: string }) => {
    if (!quotaUser) return
    try {
      await adjustQuota(quotaUser.user_id, values)
      message.success('额度调整成功')
      setQuotaModalVisible(false)
      quotaForm.resetFields()
      fetchUsers()
    } catch (error) {
      console.error(error)
    }
  }

  const openQuotaModal = (user: User) => {
    setQuotaUser(user)
    quotaForm.setFieldsValue({ amount: 0, reason: '' })
    setQuotaModalVisible(true)
  }

  const columns = [
    { 
      title: '用户名', 
      dataIndex: 'username', 
      key: 'username',
      render: (text: string) => <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
    },
    { 
      title: '邮箱', 
      dataIndex: 'email', 
      key: 'email',
      render: (text: string) => <span style={{ color: '#94A3B8' }}>{text}</span>
    },
    { 
      title: '角色', 
      dataIndex: 'role', 
      key: 'role',
      render: (role: string) => (
        <Tag 
          color={role === 'admin' ? 'blue' : 'default'}
          style={{ 
            borderRadius: '6px',
            background: role === 'admin' ? 'rgba(37, 99, 235, 0.15)' : 'rgba(100, 116, 139, 0.15)',
            border: 'none',
          }}
        >
          {role === 'admin' ? '管理员' : '用户'}
        </Tag>
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
      title: '额度', 
      dataIndex: 'quota', 
      key: 'quota',
      render: (quota: number, record: User) => (
        <Space>
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif", 
            color: '#CBD5E1' 
          }}>
            {record.quota_used?.toLocaleString()} / {quota?.toLocaleString()}
          </span>
          <Button 
            type="text" 
            size="small" 
            icon={<DollarOutlined />}
            onClick={() => openQuotaModal(record)}
            style={{ color: '#3B82F6' }}
          >
            调整
          </Button>
        </Space>
      )
    },
    { 
      title: '创建时间', 
      dataIndex: 'created_at', 
      key: 'created_at',
      render: (val: string) => <span style={{ color: '#94A3B8' }}>{dayjs(val).format('YYYY-MM-DD')}</span>
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space>
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => {
              if (record.role === 'admin') return
              setEditUser(record)
              form.setFieldsValue(record)
            }}
            disabled={record.role === 'admin'}
            style={{ color: record.role === 'admin' ? '#64748B' : '#3B82F6' }}
          >
            编辑
          </Button>
          <Popconfirm
            title={record.role === 'admin' ? "不能删除管理员用户" : "确认删除此用户？"}
            onConfirm={() => handleDelete(record.user_id)}
            disabled={record.role === 'admin'}
          >
            <Button 
              type="text" 
              danger 
              icon={<DeleteOutlined />}
              disabled={record.role === 'admin'}
            >
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
          <TeamOutlined style={{ marginRight: 12, color: '#3B82F6' }} />
          用户管理
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
          }}
        >
          新建用户
        </Button>
      </div>

      <div style={{
        background: 'rgba(17, 24, 39, 0.6)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 16,
        overflow: 'hidden',
      }}>
        <Table
          dataSource={users}
          columns={columns}
          rowKey="user_id"
          loading={loading}
        />
      </div>

      {/* 创建用户弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            新建用户
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item 
            name="username" 
            label={<span style={{ color: '#94A3B8' }}>用户名</span>} 
            rules={[{ required: true }]}
          >
            <Input 
              placeholder="请输入用户名"
              style={{ height: 40, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item 
            name="email" 
            label={<span style={{ color: '#94A3B8' }}>邮箱</span>} 
            rules={[{ required: true, type: 'email' }]}
          >
            <Input 
              placeholder="请输入邮箱"
              style={{ height: 40, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item 
            name="password" 
            label={<span style={{ color: '#94A3B8' }}>密码</span>} 
            rules={[{ required: true, min: 8 }]}
          >
            <Input.Password 
              placeholder="请输入密码"
              style={{ height: 40, borderRadius: 10 }}
            />
          </Form.Item>
          <Form.Item 
            name="role" 
            label={<span style={{ color: '#94A3B8' }}>角色</span>} 
            initialValue="user"
          >
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="user">用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item 
            name="quota" 
            label={<span style={{ color: '#94A3B8' }}>初始额度</span>}
          >
            <InputNumber 
              min={0} 
              style={{ width: '100%', height: 40 }} 
              placeholder="请输入初始额度"
            />
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button 
                onClick={() => setModalVisible(false)}
                style={{ borderRadius: 10 }}
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
                }}
              >
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑用户弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            编辑用户
          </span>
        }
        open={!!editUser}
        onCancel={() => {
          setEditUser(null)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item 
            name="role" 
            label={<span style={{ color: '#94A3B8' }}>角色</span>}
          >
            <Select>
              <Select.Option value="user">用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item 
            name="status" 
            label={<span style={{ color: '#94A3B8' }}>状态</span>}
          >
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button 
                onClick={() => setEditUser(null)}
                style={{ borderRadius: 10 }}
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
                }}
              >
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 调整额度弹窗 */}
      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            调整用户额度 - {quotaUser?.username}
          </span>
        }
        open={quotaModalVisible}
        onCancel={() => {
          setQuotaModalVisible(false)
          quotaForm.resetFields()
        }}
        footer={null}
      >
        <Form form={quotaForm} onFinish={handleQuotaAdjust} layout="vertical">
          <Form.Item 
            name="amount" 
            label={<span style={{ color: '#94A3B8' }}>调整额度（正数增加，负数减少）</span>}
            rules={[{ required: true, message: '请输入调整额度' }]}
          >
            <InputNumber 
              style={{ width: '100%', height: 40 }} 
              placeholder="如：10000 或 -5000"
            />
          </Form.Item>
          <Form.Item 
            name="reason" 
            label={<span style={{ color: '#94A3B8' }}>调整原因</span>}
            rules={[{ required: true, message: '请输入调整原因' }]}
          >
            <Input.TextArea 
              rows={3} 
              placeholder="请输入调整原因，便于审计追溯"
              style={{ borderRadius: 10 }}
            />
          </Form.Item>
          {quotaUser && (
            <div style={{ 
              marginBottom: 16, 
              padding: 16, 
              background: 'rgba(30, 41, 59, 0.8)', 
              borderRadius: 10,
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}>
              <div style={{ color: '#94A3B8', marginBottom: 8 }}>
                当前额度：<span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif" }}>
                  {quotaUser.quota?.toLocaleString()}
                </span>
              </div>
              <div style={{ color: '#94A3B8' }}>
                已使用：<span style={{ color: '#F8FAFC', fontFamily: "'Space Grotesk', sans-serif" }}>
                  {quotaUser.quota_used?.toLocaleString()}
                </span>
              </div>
            </div>
          )}
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button 
                onClick={() => setQuotaModalVisible(false)}
                style={{ borderRadius: 10 }}
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
                }}
              >
                确认调整
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UsersPage
