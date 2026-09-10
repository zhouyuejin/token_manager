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
import { getModels, ModelMapping } from '../../api/models'
import {
  useDefaultModelGroupWarning,
} from '../../hooks/useDefaultModelGroupWarning'

const { TextArea } = Input

const ModelGroups: React.FC = () => {
  const [loading, setLoading] = useState(false)
  const [groups, setGroups] = useState<ModelGroup[]>([])
  const [models, setModels] = useState<ModelMapping[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingGroup, setEditingGroup] = useState<ModelGroup | null>(null)
  const [form] = Form.useForm()
  const message = useMessage()
  const { token, isDark } = useThemeToken()
  const { needsAttention, refresh } = useDefaultModelGroupWarning()

  useEffect(() => {
    fetchGroups()
    fetchModels()
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

  const fetchModels = async () => {
    try {
      const res = await getModels()
      setModels(res.items || [])
    } catch (error) {
      console.error('获取模型失败', error)
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
      model_ids: record.model_ids
    })
    setModalVisible(true)
  }

  const handleDelete = async (groupId: string) => {
    try {
      await deleteModelGroup(groupId)
      message.success('删除成功')
      fetchGroups()
      refresh()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      if (typeof detail === 'string' && detail.includes('该分组已绑定')) {
        message.error('该分组已绑定模型，请先解除绑定后再删除')
      } else {
        message.error('删除失败')
      }
    }
  }

  const handleSetDefault = async (groupId: string) => {
    try {
      await setModelGroupDefault(groupId)
      message.success('已设为默认分组')
      fetchGroups()
      refresh()
    } catch (error) {
      message.error('设置失败')
    }
  }

  const handleUnsetDefault = async (groupId: string) => {
    try {
      await unsetModelGroupDefault(groupId)
      message.success('已取消默认分组')
      fetchGroups()
      refresh()
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
        model_ids: values.model_ids || []
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
      refresh()
    } catch (error) {
      console.error(error)
    }
  }

  const getModelNames = (modelIds: string[]) => {
    return modelIds.map(id => {
      const model = models.find(m => m.model_id === id)
      return model?.display_name || model?.model_id || id
    })
  }

  const noActiveDefault = needsAttention

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
      title: '关联模型',
      dataIndex: 'model_ids',
      key: 'model_ids',
      width: 250,
      render: (ids: string[]) => {
        const names = getModelNames(ids)
        if (!names.length) return <Tag>未关联</Tag>
        // 最多显示3个，其余折叠
        const visible = names.slice(0, 3)
        const remaining = names.length - 3
        return (
          <>
            {visible.map((name, i) => (
              <Tag key={i} color="blue">{name}</Tag>
            ))}
            {remaining > 0 && <Tag>+{remaining}个</Tag>}
          </>
        )
      }
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
          banner
          type="warning"
          showIcon
          message={
            <span>
              缺少已启用的默认模型分组，新用户将无法正常使用 API Key。
              {groups.length === 0 ? (
                <Button type="link" size="small" onClick={handleCreate}>
                  立即创建分组
                </Button>
              ) : (
                <span style={{ marginLeft: 8, color: 'rgba(0,0,0,0.45)' }}>
                  请在下方将一个分组设为默认。
                </span>
              )}
            </span>
          }
          style={{ marginBottom: 12, borderRadius: 8 }}
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
        width={700}
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
            name="model_ids"
            label="关联模型"
            tooltip="选择要绑定到该分组的模型。可同时选择多个模型。"
          >
            <Select
              mode="multiple"
              placeholder="请选择模型"
              showSearch
              filterOption={(input, option) =>
                String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              optionLabelProp="label"
            >
              {models.map(m => (
                <Select.Option 
                  key={m.model_id} 
                  value={m.model_id}
                  label={m.display_name || m.model_id}
                >
                  {m.display_name || m.model_id} 
                  <span style={{ color: '#999', marginLeft: 8 }}>
                    ({m.provider_id})
                  </span>
                  {m.status === 'disabled' && (
                    <Tag color="red" style={{ marginLeft: 8 }}>禁用</Tag>
                  )}
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
