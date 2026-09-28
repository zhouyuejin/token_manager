import { Form, Input, Modal, Typography } from 'antd'
import { useEffect } from 'react'
import { ApprovalRequest } from '../api/approvals'

interface Props {
  request: ApprovalRequest | null
  decision: 'approved' | 'rejected'
  onCancel: () => void
  onSubmit: (request: ApprovalRequest, comment: string) => Promise<void>
}

const ApprovalDecisionModal = ({ request, decision, onCancel, onSubmit }: Props) => {
  const [form] = Form.useForm<{ comment: string }>()

  useEffect(() => {
    form.resetFields()
  }, [form, request])

  return (
    <Modal
      open={!!request}
      title={decision === 'approved' ? '确认通过申请' : '确认拒绝申请'}
      okText={decision === 'approved' ? '确认通过' : '确认拒绝'}
      okButtonProps={{ danger: decision === 'rejected' }}
      cancelText="取消"
      onCancel={onCancel}
      onOk={async () => {
        if (!request) return
        const { comment } = await form.validateFields()
        await onSubmit(request, comment.trim())
      }}
      destroyOnClose
    >
      <Typography.Paragraph>
        {decision === 'approved' ? '通过后将按申请内容立即生效。' : '拒绝后申请不会生效。'}
      </Typography.Paragraph>
      <Form form={form} layout="vertical">
        <Form.Item
          name="comment"
          label="审批意见"
          rules={[{ required: true, whitespace: true, message: '请填写审批意见' }]}
        >
          <Input.TextArea rows={4} maxLength={1000} showCount placeholder="说明审批决定和处理结果" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default ApprovalDecisionModal
