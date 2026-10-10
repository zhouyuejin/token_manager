import { useEffect, useState } from 'react'
import { Alert, Button, DatePicker, Form, Input, InputNumber, Modal, Select, Typography } from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import { ApprovalRequest, ApprovalType, ModelGroupApplicationOption, ProjectAccessOption, createApiKeyApplication, createModelGroupApplication, createProjectAccessApplication, createQuotaApplication } from '../api/approvals'
import { Project } from '../api/projects'
import { useAuthStore } from '../store/auth'
import { useSwrData } from '../hooks/useSwr'
import { parseApiKeyWhitelist } from '../utils/apiKeyWhitelist'
import { useMessage } from '../utils/message'

type ApplicationValues = {
  request_type: ApprovalType
  project_id?: string
  name?: string
  ip_whitelist?: string
  expires_at?: Dayjs | null
  amount?: number
  group_id?: string
  reason: string
}

export default function ApplicationModal({ open, initialType = 'api_key', fixedType = false, onCancel, onSubmitted }: {
  open: boolean
  initialType?: ApprovalType
  fixedType?: boolean
  onCancel: () => void
  onSubmitted: (request: ApprovalRequest) => void | Promise<void>
}) {
  const [form] = Form.useForm<ApplicationValues>()
  const user = useAuthStore(state => state.user)
  const message = useMessage()
  const type = Form.useWatch('request_type', form) || initialType
  const quotaApplicationBlocked = type === 'quota' && !!user && user.quota < 0
  const [submitting, setSubmitting] = useState(false)
  const { data: projects, error: projectsError } = useSwrData<{ items: Project[] }>(open && type === 'api_key' ? '/projects' : null)
  const { data: accessOptions, error: accessOptionsError } = useSwrData<ProjectAccessOption[]>(open && type === 'project_access' ? '/approvals/project-access/options' : null)
  const { data: groupOptions, error: groupOptionsError } = useSwrData<ModelGroupApplicationOption[]>(open && type === 'model_group' ? '/approvals/model-group/options' : null)

  useEffect(() => {
    if (open) {
      form.resetFields()
      form.setFieldValue('request_type', initialType)
    }
  }, [form, open, initialType])

  useEffect(() => {
    form.resetFields(['project_id', 'name', 'ip_whitelist', 'expires_at', 'amount', 'group_id'])
  }, [form, type])

  const submitApplication = async (values: ApplicationValues) => {
    if (values.request_type === 'quota' && user && user.quota < 0) {
      message.info('当前账号为无限额度，无需提交额度申请。')
      return
    }
    setSubmitting(true)
    try {
      let request: ApprovalRequest
      if (values.request_type === 'api_key') {
        request = await createApiKeyApplication({
          project_id: values.project_id!, name: values.name!.trim(),
          ip_whitelist: parseApiKeyWhitelist(values.ip_whitelist || ''),
          expires_at: values.expires_at?.toISOString() || null, reason: values.reason.trim(),
        })
      } else if (values.request_type === 'quota') {
        request = await createQuotaApplication({ amount: values.amount!, reason: values.reason.trim() })
      } else if (values.request_type === 'model_group') {
        request = await createModelGroupApplication({ group_id: values.group_id!, reason: values.reason.trim() })
      } else {
        request = await createProjectAccessApplication({ project_id: values.project_id!, reason: values.reason.trim() })
      }
      message.success('申请已提交，审批通过前不会生效')
      await onSubmitted(request)
    } finally {
      setSubmitting(false)
    }
  }

  return <Modal title={fixedType ? 'API Key 申请' : '新建申请'} open={open} onCancel={submitting ? undefined : onCancel} maskClosable={!submitting} closable={!submitting} footer={null} forceRender width={640}>
    <Typography.Paragraph type="secondary">审批通过后生效。额度为个人账户 Token 额度；模型访问权限按模型分组授予。</Typography.Paragraph>
    {quotaApplicationBlocked && <Alert type="info" showIcon style={{ marginBottom: 16 }} message="当前账号为无限额度，无需提交额度申请。" />}
    <Form form={form} layout="vertical" initialValues={{ request_type: initialType }} onFinish={submitApplication}>
      <Form.Item hidden={fixedType} name="request_type" label="申请类型" rules={[{ required: true }]}>
        <Select options={[
          { value: 'api_key', label: 'API Key 申请' },
          { value: 'quota', label: user && user.quota < 0 ? '额度申请（当前账号为无限额度，无需申请）' : '额度申请', disabled: !user || user.quota < 0 },
          { value: 'model_group', label: '模型访问申请' },
          { value: 'project_access', label: '加入项目申请' },
        ]} />
      </Form.Item>
      {type === 'api_key' && <>
        <Form.Item name="project_id" label="项目" rules={[{ required: true, message: '请选择项目' }]}>
          <Select loading={!projects} options={(projects?.items || []).map(project => ({ value: project.project_id, label: `${project.department_name} / ${project.name}` }))} />
        </Form.Item>
        <Form.Item name="name" label="用途" rules={[{ required: true, whitespace: true, message: '请填写用途' }]}>
          <Input maxLength={100} placeholder="例如：生产环境服务" />
        </Form.Item>
        <Form.Item name="ip_whitelist" label="IP 白名单" extra="每行一个 IP，也可用逗号分隔；留空表示不限制。">
          <Input.TextArea rows={2} placeholder="203.0.113.10" />
        </Form.Item>
        <Form.Item name="expires_at" label="过期时间（可选）">
          <DatePicker showTime style={{ width: '100%' }} disabledDate={date => date.isBefore(dayjs().startOf('day'))} />
        </Form.Item>
      </>}
      {type === 'quota' && <Form.Item name="amount" label="申请增加的个人额度（tokens）" rules={[{ required: true, message: '请输入申请额度' }]}>
        <InputNumber min={1} precision={0} style={{ width: '100%' }} />
      </Form.Item>}
      {type === 'model_group' && <Form.Item name="group_id" label="模型分组" rules={[{ required: true, message: '请选择模型分组' }]}>
        <Select loading={!groupOptions} options={(groupOptions || []).map(group => ({ value: group.group_id, label: group.name }))} />
      </Form.Item>}
      {type === 'project_access' && <Form.Item name="project_id" label="申请加入的项目" rules={[{ required: true, message: '请选择项目' }]}>
        <Select loading={!accessOptions} options={(accessOptions || []).map(project => ({ value: project.project_id, label: `${project.department_name} / ${project.name}` }))} />
      </Form.Item>}
      {projectsError && type === 'api_key' && <Alert type="error" showIcon message="项目列表加载失败，请稍后重试。" />}
      {type === 'api_key' && projects && !projects.items.length && <Alert type="warning" showIcon message="暂无已授权项目，请先在“我的申请”中申请加入项目。" />}
      {accessOptionsError && type === 'project_access' && <Alert type="error" showIcon message="项目列表加载失败，请稍后重试。" />}
      {groupOptionsError && type === 'model_group' && <Alert type="error" showIcon message="模型分组加载失败，请稍后重试。" />}
      <Form.Item name="reason" label="申请理由" rules={[{ required: true, whitespace: true, message: '请填写申请理由' }]}>
        <Input.TextArea rows={3} maxLength={1000} showCount />
      </Form.Item>
      <Button type="primary" htmlType="submit" loading={submitting} disabled={quotaApplicationBlocked}>提交申请</Button>
    </Form>
  </Modal>
}
