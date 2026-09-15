import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMessage } from '../../utils/message'
import { Card, Button, Space, Form, Input, Select, Row, Col, Switch, Tag, Typography } from 'antd'
import { ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons'
import { getModelGroup, createModelGroup, updateModelGroup } from '../../api/modelGroups'
import { getModels, Model } from '../../api/models'

const { Title } = Typography
const { TextArea } = Input

const ModelGroupForm: React.FC = () => {
  const { groupId } = useParams<{ groupId?: string }>()
  const navigate = useNavigate()
  const message = useMessage()
  const [form] = Form.useForm()
  const [submitLoading, setSubmitLoading] = useState(false)
  const [fetchLoading, setFetchLoading] = useState(false)
  const [models, setModels] = useState<Model[]>([])

  const isEdit = !!groupId

  useEffect(() => {
    // 加载模型列表
    const loadModels = async () => {
      try {
        const res = await getModels()
        setModels(res.items || [])
      } catch {
        /* ignore - models list load failure is not critical */
      }
    }
    loadModels()
  }, [])

  useEffect(() => {
    if (!isEdit) return
    const loadGroup = async () => {
      setFetchLoading(true)
      try {
        const group = await getModelGroup(groupId)
        form.setFieldsValue({
          ...group,
          is_default: group.is_default === 1,
        })
      } catch {
        message.error('加载分组信息失败')
        navigate('/admin/model-groups')
      } finally {
        setFetchLoading(false)
      }
    }
    loadGroup()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupId, isEdit])

  const handleCreate = async (values: any) => {
    try {
      const setAsDefault = values.set_as_default === true
      const payload = {
        name: values.name,
        description: values.description,
        is_default: setAsDefault ? 1 : 0,
        model_ids: values.model_ids || [],
      }
      await createModelGroup(payload)
      message.success('创建成功')
      navigate('/admin/model-groups')
    } catch {
      /* error already displayed by interceptor */
    }
  }

  const handleUpdate = async (values: any) => {
    if (!groupId) return
    try {
      const payload = {
        name: values.name,
        description: values.description,
        is_default: values.is_default ? 1 : 0,
        model_ids: values.model_ids || [],
      }
      await updateModelGroup(groupId, payload)
      message.success('更新成功')
      navigate('/admin/model-groups')
    } catch {
      /* error already displayed by interceptor */
    }
  }

  const handleSubmit = async () => {
    setSubmitLoading(true)
    try {
      await form.validateFields()
      const values = form.getFieldsValue()
      if (isEdit) {
        await handleUpdate(values)
      } else {
        await handleCreate(values)
      }
    } catch {
      /* validation error shown by form */
    } finally {
      setSubmitLoading(false)
    }
  }

  return (
    <div style={{ padding: 24 }}>
      {/* 页面头部 */}
      <Card style={{ marginBottom: 16 }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Space>
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/model-groups')}>
                返回模型分组
              </Button>
              <Title level={4} style={{ margin: 0 }}>
                {isEdit ? '编辑分组' : '新建分组'}
              </Title>
            </Space>
          </Col>
          <Col>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={submitLoading}
              onClick={handleSubmit}
            >
              保存
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 表单内容 */}
      <Card loading={fetchLoading}>
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

          {!isEdit && (
            <Form.Item
              name="set_as_default"
              label="创建后立即设为默认"
              valuePropName="checked"
            >
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          )}

          {isEdit && (
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
      </Card>
    </div>
  )
}

export default ModelGroupForm
