import { useState } from 'react'
import { Card, Form, Input, Button, message, Divider, Switch } from 'antd'
import { useAuthStore } from '../store/auth'

const SettingsPage = () => {
  const { user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [notifySettings, setNotifySettings] = useState({
    quota_low_alert: true,
    quota_change_alert: true,
    daily_report: false,
  })

  const onPasswordChange = async (values: any) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      // TODO: 调用修改密码API
      message.success('密码修改成功')
    } catch (error) {
      console.error(error)
      message.error('密码修改失败')
    } finally {
      setLoading(false)
    }
  }

  const onNotifyChange = async (key: string, value: boolean) => {
    const newSettings = { ...notifySettings, [key]: value }
    setNotifySettings(newSettings)
    try {
      // TODO: 调用保存通知设置API
      message.success('通知设置已更新')
    } catch (error) {
      console.error(error)
      // 回滚状态
      setNotifySettings(notifySettings)
    }
  }

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>个人设置</h2>

      <Card title="账户信息" style={{ marginBottom: 24 }}>
        <Form layout="vertical">
          <Form.Item label="用户名">
            <Input value={user?.username} disabled />
          </Form.Item>
          <Form.Item label="邮箱">
            <Input value={user?.email} disabled />
          </Form.Item>
          <Form.Item label="用户ID">
            <Input value={user?.user_id} disabled />
          </Form.Item>
          <Form.Item label="注册时间">
            <Input value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '-'} disabled />
          </Form.Item>
        </Form>
      </Card>

      <Card title="修改密码" style={{ marginBottom: 24 }}>
        <Form layout="vertical" onFinish={onPasswordChange}>
          <Form.Item name="old_password" label="原密码" rules={[{ required: true, message: '请输入原密码' }]}>
            <Input.Password placeholder="请输入原密码" />
          </Form.Item>
          <Form.Item name="new_password" label="新密码" rules={[{ required: true, min: 8, message: '请输入至少8位的新密码' }]}>
            <Input.Password placeholder="请输入新密码（至少8位）" />
          </Form.Item>
          <Form.Item name="confirm_password" label="确认新密码" rules={[{ required: true, message: '请再次输入新密码' }]}>
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              保存修改
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="通知设置">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 500 }}>额度不足通知</div>
              <div style={{ color: '#8c8c8c', fontSize: 12 }}>当额度低于20%时发送邮件通知</div>
            </div>
            <Switch 
              checked={notifySettings.quota_low_alert}
              onChange={(checked) => onNotifyChange('quota_low_alert', checked)}
            />
          </div>
          <Divider style={{ margin: '8px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 500 }}>额度变动通知</div>
              <div style={{ color: '#8c8c8c', fontSize: 12 }}>额度增加或减少时发送邮件通知</div>
            </div>
            <Switch 
              checked={notifySettings.quota_change_alert}
              onChange={(checked) => onNotifyChange('quota_change_alert', checked)}
            />
          </div>
          <Divider style={{ margin: '8px 0' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 500 }}>每日用量报表</div>
              <div style={{ color: '#8c8c8c', fontSize: 12 }}>每天发送用量统计邮件</div>
            </div>
            <Switch 
              checked={notifySettings.daily_report}
              onChange={(checked) => onNotifyChange('daily_report', checked)}
            />
          </div>
        </div>
      </Card>
    </div>
  )
}

export default SettingsPage
