import { useState, useEffect } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Card, Form, Input, Button, Switch } from 'antd'
import { UserOutlined, MailOutlined, LockOutlined, BellOutlined } from '@ant-design/icons'
import { useAuthStore } from '../store/auth'
import { useMessage } from '../utils/message'
import { changePassword, getNotificationSettings, updateNotificationSettings, updateProfile } from '../api/users'
import { mutate } from 'swr'
import { getRequestErrorMessage } from '../utils/security'

const SettingsPage = () => {
  const { user } = useAuthStore()
  const [passwordForm] = Form.useForm()
  const [profileForm] = Form.useForm()
  const [profileLoading, setProfileLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [notifyLoading, setNotifyLoading] = useState(false)
  const message = useMessage()
  const { token, isDark } = useThemeToken()
  const [notifySettings, setNotifySettings] = useState({
    quota_low_alert: true,
    quota_change_alert: true,
    daily_report: false,
  })

  useEffect(() => {
    profileForm.setFieldsValue({ nickname: user?.nickname || '' })
  }, [profileForm, user?.nickname])

  const onProfileChange = async (values: { nickname?: string }) => {
    setProfileLoading(true)
    try {
      await updateProfile({ nickname: values.nickname?.trim() || null })
      await mutate('/users/me')
      message.success('昵称已更新')
    } catch (error) {
      console.error(error)
    } finally {
      setProfileLoading(false)
    }
  }

  // 页面加载时获取通知设置
  useEffect(() => {
    const fetchNotifySettings = async () => {
      try {
        const data = await getNotificationSettings()
        setNotifySettings({
          quota_low_alert: data.quota_low_alert,
          quota_change_alert: data.quota_change_alert,
          daily_report: data.daily_report,
        })
      } catch (error) {
        console.error('获取通知设置失败:', error)
      }
    }
    fetchNotifySettings()
  }, [])

  const onPasswordChange = async (values: any) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的密码不一致')
      return
    }
    setLoading(true)
    try {
      await changePassword(values)
      passwordForm.resetFields()
      message.success('密码修改成功')
    } catch (error) {
      message.error(getRequestErrorMessage((error as any)?.response?.data, '密码修改失败'))
    } finally {
      setLoading(false)
    }
  }

  const onNotifyChange = async (key: string, value: boolean) => {
    const newSettings = { ...notifySettings, [key]: value }
    setNotifySettings(newSettings)
    setNotifyLoading(true)
    try {
      await updateNotificationSettings(newSettings)
      message.success('通知设置已更新')
    } catch (error) {
      console.error(error)
      message.error('通知设置更新失败')
      // 回滚状态
      setNotifySettings(notifySettings)
    } finally {
      setNotifyLoading(false)
    }
  }

  const cardStyle = {
    background: token.colorBgContainer,
    backdropFilter: 'blur(20px)',
    border: `1px solid ${token.colorBorder}`,
    borderRadius: 16,
    marginBottom: 24,
  }

  return (
    <div className="stagger-children">
      <h2 style={{ 
        marginBottom: 24, 
        fontFamily: "'Space Grotesk', sans-serif",
        fontSize: 24,
        fontWeight: 600,
        color: token.colorText,
      }}>
        个人设置
      </h2>

      <Card 
        title={
          <span style={{ 
            color: token.colorText, 
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
          }}>
            <UserOutlined style={{ marginRight: 8, color: '#3B82F6' }} />
            账户信息
          </span>
        }
        style={cardStyle}
      >
        <Form form={profileForm} layout="vertical" onFinish={onProfileChange}>
          <Form.Item name="nickname" label={<span style={{ color: token.colorTextSecondary }}>昵称</span>} rules={[{ max: 50, message: '昵称最多50个字符' }]}>
            <Input maxLength={50} placeholder="选填，未填写时显示用户名" />
          </Form.Item>
          <Form.Item 
            label={<span style={{ color: token.colorTextSecondary }}>用户名</span>}
          >
            <Input 
              value={user?.username} 
              disabled 
              style={{
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
                color: token.colorText,
              }}
              prefix={<UserOutlined style={{ color: token.colorTextTertiary }} />}
            />
          </Form.Item>
          <Form.Item 
            label={<span style={{ color: token.colorTextSecondary }}>邮箱</span>}
          >
            <Input 
              value={user?.email} 
              disabled 
              style={{
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
                color: token.colorText,
              }}
              prefix={<MailOutlined style={{ color: token.colorTextTertiary }} />}
            />
          </Form.Item>
          <Form.Item 
            label={<span style={{ color: token.colorTextSecondary }}>用户ID</span>}
          >
            <Input 
              value={user?.user_id} 
              disabled 
              style={{
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
                color: token.colorText,
                fontFamily: "'Space Grotesk', sans-serif",
              }}
            />
          </Form.Item>
          <Form.Item 
            label={<span style={{ color: token.colorTextSecondary }}>注册时间</span>}
          >
            <Input 
              value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '-'} 
              disabled 
              style={{
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
                color: token.colorText,
              }}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={profileLoading}>保存昵称</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card 
        title={
          <span style={{ 
            color: token.colorText, 
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
          }}>
            <LockOutlined style={{ marginRight: 8, color: '#EA580C' }} />
            修改密码
          </span>
        }
        style={cardStyle}
      >
        <Form form={passwordForm} layout="vertical" onFinish={onPasswordChange}>
          <Form.Item 
            name="old_password" 
            label={<span style={{ color: token.colorTextSecondary }}>原密码</span>} 
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password 
              placeholder="请输入原密码" 
              style={{
                height: 44,
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
              }}
              prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />}
            />
          </Form.Item>
          <Form.Item 
            name="new_password" 
            label={<span style={{ color: token.colorTextSecondary }}>新密码</span>} 
            rules={[{ required: true, min: 8, message: '请输入至少8位的新密码' }]}
          >
            <Input.Password 
              placeholder="请输入新密码（至少8位）" 
              style={{
                height: 44,
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
              }}
              prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />}
            />
          </Form.Item>
          <Form.Item 
            name="confirm_password" 
            label={<span style={{ color: token.colorTextSecondary }}>确认新密码</span>} 
            rules={[{ required: true, message: '请再次输入新密码' }]}
          >
            <Input.Password 
              placeholder="请再次输入新密码" 
              style={{
                height: 44,
                background: token.colorBgContainer,
                border: `1px solid ${token.colorBorder}`,
                borderRadius: 10,
              }}
              prefix={<LockOutlined style={{ color: token.colorTextTertiary }} />}
            />
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              style={{
                height: 44,
                borderRadius: 10,
                background: token.colorPrimary,
                border: 'none',
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 500,
              }}
            >
              保存修改
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card 
        title={
          <span style={{ 
            color: token.colorText, 
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 600,
          }}>
            <BellOutlined style={{ marginRight: 8, color: '#22C55E' }} />
            通知设置
          </span>
        }
        style={cardStyle}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '16px 20px',
            background: token.colorBgContainer,
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.05)',
          }}>
            <div>
              <div style={{ fontWeight: 500, color: token.colorText }}>额度不足通知</div>
              <div style={{ color: token.colorTextTertiary, fontSize: 13, marginTop: 4 }}>当额度低于20%时发送邮件通知</div>
            </div>
            <Switch 
              checked={notifySettings.quota_low_alert}
              onChange={(checked) => onNotifyChange('quota_low_alert', checked)}
              loading={notifyLoading}
              style={{
                background: notifySettings.quota_low_alert ? '#2563EB' : '#334155',
              }}
            />
          </div>
          
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '16px 20px',
            background: token.colorBgContainer,
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.05)',
          }}>
            <div>
              <div style={{ fontWeight: 500, color: token.colorText }}>额度变动通知</div>
              <div style={{ color: token.colorTextTertiary, fontSize: 13, marginTop: 4 }}>额度增加或减少时发送邮件通知</div>
            </div>
            <Switch 
              checked={notifySettings.quota_change_alert}
              onChange={(checked) => onNotifyChange('quota_change_alert', checked)}
              loading={notifyLoading}
              style={{
                background: notifySettings.quota_change_alert ? '#2563EB' : '#334155',
              }}
            />
          </div>
          
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            padding: '16px 20px',
            background: token.colorBgContainer,
            borderRadius: 12,
            border: '1px solid rgba(255, 255, 255, 0.05)',
          }}>
            <div>
              <div style={{ fontWeight: 500, color: token.colorText }}>每日用量报表</div>
              <div style={{ color: token.colorTextTertiary, fontSize: 13, marginTop: 4 }}>每天发送用量统计邮件</div>
            </div>
            <Switch 
              checked={notifySettings.daily_report}
              onChange={(checked) => onNotifyChange('daily_report', checked)}
              loading={notifyLoading}
              style={{
                background: notifySettings.daily_report ? '#2563EB' : '#334155',
              }}
            />
          </div>
        </div>
      </Card>
    </div>
  )
}

export default SettingsPage
