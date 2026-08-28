import { useState, useEffect } from 'react'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, message, Popconfirm 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, getProviders, ModelMapping, Provider } from '../../api/models'

const ModelsPage = () => {
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<ModelMapping[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editModel, setEditModel] = useState<ModelMapping | null>(null)
  const [form] = Form.useForm()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [modelsData, providersData] = await Promise.all([
        getModels(),
        getProviders()
      ])
      setModels(modelsData.items || [])
      setProviders(providersData.items || [])
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await createModel(values)
      message.success('创建成功')
      setModalVisible(false)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleUpdate = async (values: any) => {
    if (!editModel) return
    try {
      await updateModel(editModel.model_id, values)
      message.success('更新成功')
      setEditModel(null)
      form.resetFields()
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const handleDelete = async (modelId: string) => {
    try {
      await deleteModel(modelId)
      message.success('删除成功')
      fetchData()
    } catch (error) {
      console.error(error)
    }
  }

  const openEditModal = (record: ModelMapping) => {
    setEditModel(record)
    form.setFieldsValue({
      ...record,
      aliases: record.aliases?.join(', '),
    })
  }

  const columns = [
    { title: '平台模型', dataIndex: 'model_id', key: 'model_id' },
    { title: '显示名称', dataIndex: 'display_name', key: 'display_name' },
    { 
      title: '供应商', 
      dataIndex: 'provider_id', 
      key: 'provider_id',
      render: (providerId: string) => {
        const provider = providers.find(p => p.provider_id === providerId)
        return provider?.name || providerId
      }
    },
    { title: '上游模型', dataIndex: 'provider_model', key: 'provider_model' },
    { title: '别名', dataIndex: 'aliases', key: 'aliases', render: (val: string[]) => val?.join(', ') },
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
      title: '操作',
      key: 'action',
      render: (_: any, record: ModelMapping) => (
        <Space>
          <Button 
            type="link" 
            icon={<EditOutlined />}
            onClick={() => openEditModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除此模型映射？"
            onConfirm={() => handleDelete(record.model_id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>模型映射管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>
          添加映射
        </Button>
      </div>

      <Table
        dataSource={models}
        columns={columns}
        rowKey="model_id"
        loading={loading}
      />

      {/* 添加模型映射弹窗 */}
      <Modal
        title="添加模型映射"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="model_id" label="平台模型ID" rules={[{ required: true }]}>
            <Input placeholder="如：gpt-4" />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="如：GPT-4" />
          </Form.Item>
          <Form.Item name="provider_id" label="供应商" rules={[{ required: true }]}>
            <Select placeholder="请选择供应商">
              {providers.map(p => (
                <Select.Option key={p.provider_id} value={p.provider_id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="provider_model" label="上游模型名" rules={[{ required: true }]}>
            <Input placeholder="如：gpt-4-0613" />
          </Form.Item>
          <Form.Item name="aliases" label="别名（逗号分隔）">
            <Input placeholder="如：gpt4,gpt-4-0613" />
          </Form.Item>
          <Form.Item name="status" label="状态" initialValue="active">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit">创建</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑模型映射弹窗 */}
      <Modal
        title="编辑模型映射"
        open={!!editModel}
        onCancel={() => {
          setEditModel(null)
          form.resetFields()
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="model_id" label="平台模型ID">
            <Input disabled />
          </Form.Item>
          <Form.Item name="display_name" label="显示名称">
            <Input placeholder="如：GPT-4" />
          </Form.Item>
          <Form.Item name="provider_id" label="供应商" rules={[{ required: true }]}>
            <Select placeholder="请选择供应商">
              {providers.map(p => (
                <Select.Option key={p.provider_id} value={p.provider_id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="provider_model" label="上游模型名" rules={[{ required: true }]}>
            <Input placeholder="如：gpt-4-0613" />
          </Form.Item>
          <Form.Item name="aliases" label="别名（逗号分隔）">
            <Input placeholder="如：gpt4,gpt-4-0613" />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setEditModel(null)}>取消</Button>
              <Button type="primary" htmlType="submit">保存</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelsPage
