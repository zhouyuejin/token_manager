import { useState, useEffect } from 'react'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, InputNumber, 
  Select, message, Popconfirm 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, DollarOutlined } from '@ant-design/icons'
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
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    { 
      title: '角色', 
      dataIndex: 'role', 
      key: 'role',
      render: (role: string) => (
        <Tag color={role === 'admin' ? 'blue' : 'default'}>
          {role === 'admin' ? '管理员' : '用户'}
        </Tag>
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
      title: '额度', 
      dataIndex: 'quota', 
      key: 'quota',
      render: (quota: number, record: User) => (
        <Space>
          <span>
            {record.quota_used?.toLocaleString()} / {quota?.toLocaleString()}
          </span>
          <Button 
            type="link" 
            size="small" 
            icon={<DollarOutlined />}
            onClick={() => openQuotaModal(record)}
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
      render: (val: string) => dayjs(val).format('YYYY-MM-DD')
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />} 
            onClick={() => {
              setEditUser(record)
              form.setFieldsValue(record)
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此用户？"
            onConfirm={() => handleDelete(record.user_id)}
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
        <h2>用户管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          新建用户
        </Button>
      </div>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="user_id"
        loading={loading}
      />

      {/* 创建用户弹窗 */}
      <Modal
        title="新建用户"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 8 }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="user">
            <Select>
              <Select.Option value="user">用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="quota" label="初始额度">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑用户弹窗 */}
      <Modal
        title="编辑用户"
        open={!!editUser}
        onCancel={() => {
          setEditUser(null)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="role" label="角色">
            <Select>
              <Select.Option value="user">用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setEditUser(null)}>取消</Button>
              <Button type="primary" htmlType="submit">保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 调整额度弹窗 */}
      <Modal
        title={`调整用户额度 - ${quotaUser?.username}`}
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
            label="调整额度（正数增加，负数减少）"
            rules={[{ required: true, message: '请输入调整额度' }]}
          >
            <InputNumber 
              style={{ width: '100%' }} 
              placeholder="如：10000 或 -5000"
            />
          </Form.Item>
          <Form.Item 
            name="reason" 
            label="调整原因"
            rules={[{ required: true, message: '请输入调整原因' }]}
          >
            <Input.TextArea 
              rows={3} 
              placeholder="请输入调整原因，便于审计追溯" 
            />
          </Form.Item>
          {quotaUser && (
            <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
              <div>当前额度：{quotaUser.quota?.toLocaleString()}</div>
              <div>已使用：{quotaUser.quota_used?.toLocaleString()}</div>
            </div>
          )}
          <Form.Item>
            <Space>
              <Button onClick={() => setQuotaModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">确认调整</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default UsersPage
