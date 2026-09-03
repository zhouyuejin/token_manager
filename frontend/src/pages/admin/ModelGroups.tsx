import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, Select, 
  Popconfirm, Card, Switch, Alert 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { 
  getModelGroups, createModelGroup, updateModelGroup, 
  deleteModelGroup, setModelGroupDefault, unsetModelGroupDefault,
  ModelGroup 
} from '../../api/modelGroups'
import { getProviders, Provider } from '../../api/providers'

const { TextArea } = Input

const ModelGroups: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [groups, setGroups] = useState<ModelGroup[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ModelGroup | null>(null)
  const [form] = Form.useForm()
  const message = useMessage()
  const { token, isDark } = useThemeToken()

  useEffect(() => {
    fetchGroups()
    fetchProviders()
  }, [])

  const fetchGroups = async () => {
    setLoading(true)
    try {
      const res = await getModelGroups()
      setGroups(res.items || [])
    } catch (error) {
      message.error('获取分组失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchProviders = async () => {
    try {
      const res = await getProviders()
      setProviders(res.items || [])
    } catch (error) {
      console.error('获取供应商失败', error)
    }
  }

  const handleCreate = () => {
    setEditingGroup(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record: ModelGroup) => {
    setEditingGroup(record)
    form.setFieldsValue({
      name: record.name,
      description: record.description,
      is_default: record.is_default === 1,
      provider_ids: record.provider_ids
    })
    setModalVisible(true)
  }

  const handleDelete = async (groupId: string) => {
    try {
      await deleteModelGroup(groupId)
      message.success('删除成功')
      fetchGroups()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleSetDefault = async (groupId: string) => {
    try {
      await setModelGroupDefault(groupId)
      message.success('已设为默认分组')
      fetchGroups()
    } catch (error) {
      message.error('设置失败')
    }
  }

  const handleUnsetDefault = async (groupId: string) => {
    try {
      await unsetModelGroupDefault(groupId)
      message.success('已取消默认分组')
      fetchGroups()
    } catch (error) {
      message.error('取消失败')
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      const setAsDefault = values.set_as_default === true
      const data = {
        name: values.name,
        description: values.description,
        is_default: (values.is_default || setAsDefault) ? 1 : 0,
        provider_ids: values.provider_ids || []
      }

      if (editingGroup) {
        await updateModelGroup(editingGroup.group_id, data)
        message.success('更新成功')
      } else {
        await createModelGroup(data)
        message.success('创建成功')
      }
      
      setModalVisible(false)
      fetchGroups()
    } catch (error) {
      console.error(error)
    }
  }

  const getProviderNames = (providerIds: string[]) => {
    return providerIds.map(id => {
      const provider = providers.find(p => p.provider_id === id)
      return provider?.name || id
    }).join(', ')
  }

  const hasActiveDefault = groups.some(g => g.is_default === 1 && g.status === 'active')
  const noActiveDefault = !hasActiveDefault

  const columns = [
    {
      title: '分组ID',
      dataIndex: 'group_id',
      key: 'group_id',
      width: 180
    },
    {
      title: '分组名称',
      dataIndex: 'name',
      key: 'name',
      width: 150
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200
    },
    {
      title: '关联供应商',
      dataIndex: 'provider_ids',
      key: 'provider_ids',
      width: 200,
      render: (ids: string[]) => (
        <Tag color="blue">{getProviderNames(ids) || '未关联'}</Tag>
      )
    },
    {
      title: '默认分组',
      dataIndex: 'is_default',
      key: 'is_default',
      width: 100,
      render: (isDefault: number) => (
        isDefault === 1 ? <Tag color="green">是</Tag> : <Tag>否</Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '启用' : '禁用'}
        </Tag>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: ModelGroup) => {
        const isDefault = record.is_default === 1
        const isActive = record.status === 'active'
        const useDanger = noActiveDefault && !isDefault && isActive

        return (
          <Space size="small">
            {isActive && (
              isDefault ? (
                <Popconfirm
                  title="确认取消默认分组？"
                  onConfirm={() => handleUnsetDefault(record.group_id)}
                >
                  <Button type="link" danger size="small" style={{ padding: '4px 8px' }}>
                    取消默认
                  </Button>
                </Popconfirm>
              ) : (
                <Button
                  type="link"
                  size="small"
                  danger={useDanger}
                  onClick={() => handleSetDefault(record.group_id)}
                  style={{ padding: '4px 8px' }}
                >
                  设为默认
                </Button>
              )
            )}
            <Button 
              type="link" 
              icon={<EditOutlined />} 
              onClick={() => handleEdit(record)}
              style={{ padding: '4px 8px' }}
            >
              编辑
            </Button>
            <Popconfirm 
              title="确认删除此分组？" 
              onConfirm={() => handleDelete(record.group_id)}
            >
              <Button type="link" danger icon={<DeleteOutlined />} style={{ padding: '4px 8px' }}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        )
      }
    }
  ]

  return (
    <div style={{ padding: '24px' }}>
      {noActiveDefault && (
        <Alert
          type="error"
          showIcon
          message="当前没有已启用的默认模型分组，新用户将无法正常使用 API Key。"
          description={
            groups.length === 0 ? (
              <Button
                type="primary"
                danger
                onClick={handleCreate}
                style={{ marginTop: 8 }}
              >
                立即创建分组
              </Button>
            ) : (
              <span style={{ color: 'rgba(0,0,0,0.45)' }}>
                请在下方列表中设置一个分组为默认分组，或创建一个新分组并设为默认。
              </span>
            )
          }
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      )}

      <Card 
        title="模型分组管理" 
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleCreate}
          >
            新建分组
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="group_id"
          loading={loading}
          pagination={false}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Modal
        title={editingGroup ? '编辑分组' : '新建分组'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="分组名称"
            rules={[{ required: true, message: '请输入分组名称' }]}
          >
            <Input placeholder="如：VIP-高级模型" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={3} placeholder="分组描述" />
          </Form.Item>

          {!editingGroup && (
            <Form.Item
              name="set_as_default"
              label="创建后立即设为默认"
              valuePropName="checked"
            >
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          )}

          {editingGroup && (
            <Form.Item
              name="is_default"
              label="设为默认分组"
              valuePropName="checked"
            >
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          )}

          <Form.Item
            name="provider_ids"
            label="关联供应商"
          >
            <Select
              mode="multiple"
              placeholder="选择供应商"
              optionLabelProp="label"
            >
              {providers.map(p => (
                <Select.Option 
                  key={p.provider_id} 
                  value={p.provider_id}
                  label={p.name}
                >
                  {p.name} ({p.type})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelGroups
