import { Form, Input, Modal, Typography } from 'antd'
import { useEffect } from 'react'
import { ApprovalRequest } from '../api/approvals'

interface Props {
  request: ApprovalRequest | null
  decision: 'approved' | 'rejected' | 'needs_info'
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
      title={decision === 'approved' ? '确认通过申请' : decision === 'rejected' ? '确认拒绝申请' : '要求补充说明'}
      okText={decision === 'approved' ? '确认通过' : decision === 'rejected' ? '确认拒绝' : '确认退回'}
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
        {decision === 'approved' ? '通过后将按申请内容立即生效。' : decision === 'rejected' ? '拒绝后申请不会生效。' : '申请将退回给申请人，补充后重新进入待审批。'}
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
