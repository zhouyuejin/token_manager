import { useState, useEffect } from 'react'
import { useMessage } from '../../utils/message'
import { 
  Table, Button, Tag, Space, Modal, Form, Input, 
  Select, Popconfirm 
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined } from '@ant-design/icons'
import { getModels, createModel, updateModel, deleteModel, ModelMapping } from '../../api/models'
import { getProviders, Provider } from '../../api/providers'

const ModelsPage = () => {
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<ModelMapping[]>([])
  const [providers, setProviders] = useState<Provider[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editModel, setEditModel] = useState<ModelMapping | null>(null)
  const [form] = Form.useForm()
  const message = useMessage()

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

  const openEditModal = (model: ModelMapping) => {
    setEditModel(model)
    form.setFieldsValue(model)
  }

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
          <AppstoreOutlined style={{ marginRight: 12, color: '#3B82F6' }} />
          模型管理
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
          添加模型
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
          dataSource={models}
          rowKey="model_id"
          loading={loading}
          columns={[
            { 
              title: '模型ID', 
              dataIndex: 'model_id', 
              key: 'model_id',
              render: (text: string) => (
                <span style={{ 
                  fontFamily: "'Space Grotesk', monospace", 
                  color: '#F8FAFC',
                  fontSize: 13,
                }}>
                  {text}
                </span>
              )
            },
            { 
              title: '显示名称', 
              dataIndex: 'display_name', 
              key: 'display_name',
              render: (text: string) => <span style={{ color: '#F8FAFC', fontWeight: 500 }}>{text}</span>
            },
            { 
              title: '供应商', 
              dataIndex: 'provider_id', 
              key: 'provider_id',
              render: (text: string) => {
                const provider = providers.find(p => p.provider_id === text)
                return <span style={{ color: '#94A3B8' }}>{provider?.name || text}</span>
              }
            },
            { 
              title: '上游模型', 
              dataIndex: 'provider_model', 
              key: 'provider_model',
              render: (text: string) => (
                <span style={{ 
                  fontFamily: "'Space Grotesk', monospace", 
                  color: '#94A3B8',
                  fontSize: 12,
                }}>
                  {text}
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
              title: '操作',
              key: 'action',
              render: (_: any, record: ModelMapping) => (
                <Space>
                  <Button 
                    type="text" 
                    size="small" 
                    icon={<EditOutlined />} 
                    onClick={() => openEditModal(record)}
                    style={{ color: '#3B82F6' }}
                  />
                  <Popconfirm
                    title="确认删除？"
                    onConfirm={() => handleDelete(record.model_id)}
                  >
                    <Button 
                      type="text" 
                      size="small" 
                      icon={<DeleteOutlined />} 
                      danger 
                    />
                  </Popconfirm>
                </Space>
              )
            }
          ]}
        />
      </div>

      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            添加模型
          </span>
        }
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item name="display_name" label={<span style={{ color: '#94A3B8' }}>显示名称</span>} rules={[{ required: true }]}>
            <Input placeholder="如：GPT-4" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="provider_id" label={<span style={{ color: '#94A3B8' }}>供应商</span>} rules={[{ required: true }]}>
            <Select placeholder="选择供应商" style={{ borderRadius: 10 }}>
              {providers.map(p => (
                <Select.Option key={p.provider_id} value={p.provider_id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="provider_model" label={<span style={{ color: '#94A3B8' }}>上游模型名</span>} rules={[{ required: true }]}>
            <Input placeholder="如：gpt-4" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="aliases" label={<span style={{ color: '#94A3B8' }}>别名（逗号分隔）</span>}>
            <Input placeholder="gpt4, gpt-4-turbo" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="status" label={<span style={{ color: '#94A3B8' }}>状态</span>} initialValue="active">
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setModalVisible(false)} style={{ borderRadius: 10 }}>
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

      <Modal
        title={
          <span style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            color: '#F8FAFC',
          }}>
            编辑模型
          </span>
        }
        open={!!editModel}
        onCancel={() => {
          setEditModel(null)
          form.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form form={form} onFinish={handleUpdate} layout="vertical">
          <Form.Item name="display_name" label={<span style={{ color: '#94A3B8' }}>显示名称</span>} rules={[{ required: true }]}>
            <Input placeholder="如：GPT-4" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="provider_id" label={<span style={{ color: '#94A3B8' }}>供应商</span>} rules={[{ required: true }]}>
            <Select placeholder="选择供应商" style={{ borderRadius: 10 }}>
              {providers.map(p => (
                <Select.Option key={p.provider_id} value={p.provider_id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="provider_model" label={<span style={{ color: '#94A3B8' }}>上游模型名</span>} rules={[{ required: true }]}>
            <Input placeholder="如：gpt-4" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="aliases" label={<span style={{ color: '#94A3B8' }}>别名（逗号分隔）</span>}>
            <Input placeholder="gpt4, gpt-4-turbo" style={{ height: 40, borderRadius: 10 }} />
          </Form.Item>
          <Form.Item name="status" label={<span style={{ color: '#94A3B8' }}>状态</span>}>
            <Select style={{ borderRadius: 10 }}>
              <Select.Option value="active">启用</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button onClick={() => setEditModel(null)} style={{ borderRadius: 10 }}>
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
    </div>
  )
}

export default ModelsPage
