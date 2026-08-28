import { useState } from 'react'
import { Form, Input, Button } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { register } from '../api/auth'
import { useMessage } from '../utils/message'

const Register = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const message = useMessage()

  const onFinish = async (values: { username: string; email: string; password: string }) => {
    setLoading(true)
    try {
      await register(values)
      message.success('注册成功，请登录')
      navigate('/login')
    } catch (error) {
      // 错误已在请求拦截器中处理
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background decoration */}
      <div style={{
        position: 'absolute',
        top: '20%',
        right: '10%',
        width: 400,
        height: 400,
        background: 'radial-gradient(circle, rgba(37, 99, 235, 0.3) 0%, transparent 70%)',
        filter: 'blur(60px)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute',
        bottom: '20%',
        left: '10%',
        width: 300,
        height: 300,
        background: 'radial-gradient(circle, rgba(234, 88, 12, 0.2) 0%, transparent 70%)',
        filter: 'blur(60px)',
        pointerEvents: 'none',
      }} />
      
      {/* Register card */}
      <div style={{ 
        position: 'relative',
        zIndex: 1,
        width: 420,
        padding: 48,
        background: 'rgba(17, 24, 39, 0.8)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRadius: 24,
        border: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      }} className="animate-fade-in-up">
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 64,
            height: 64,
            background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
            borderRadius: 16,
            marginBottom: 20,
            boxShadow: '0 0 30px rgba(37, 99, 235, 0.4)',
          }}>
            <span style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 24,
              color: 'white',
            }}>T</span>
          </div>
          <h1 style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 28,
            fontWeight: 700,
            background: 'linear-gradient(135deg, #F8FAFC 0%, #CBD5E1 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: 8,
          }}>
            注册账号
          </h1>
          <p style={{ color: '#94A3B8', fontSize: 14 }}>
            创建账号，开始使用
          </p>
        </div>
        
        <Form
          name="register"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
          layout="vertical"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 4, max: 20, message: '用户名4-20位' }
            ]}
            style={{ marginBottom: 20 }}
          >
            <Input 
              prefix={<UserOutlined style={{ color: '#64748B' }} />} 
              placeholder="用户名（4-20位字母数字）"
              style={{
                height: 48,
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
              }}
            />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' }
            ]}
            style={{ marginBottom: 20 }}
          >
            <Input 
              prefix={<MailOutlined style={{ color: '#64748B' }} />} 
              placeholder="邮箱"
              style={{
                height: 48,
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少8位' }
            ]}
            style={{ marginBottom: 20 }}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#64748B' }} />} 
              placeholder="密码（至少8位）"
              style={{
                height: 48,
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
              }}
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
            style={{ marginBottom: 32 }}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#64748B' }} />} 
              placeholder="确认密码"
              style={{
                height: 48,
                background: 'rgba(30, 41, 59, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: 12,
              }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 24 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              block
              style={{
                height: 48,
                borderRadius: 12,
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
                fontSize: 16,
                background: 'linear-gradient(135deg, #2563EB 0%, #3B82F6 100%)',
                border: 'none',
                boxShadow: '0 0 20px rgba(37, 99, 235, 0.4)',
              }}
            >
              注 册
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center', color: '#94A3B8' }}>
            已有账号？{' '}
            <Link 
              to="/login" 
              style={{
                color: '#3B82F6',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              立即登录
            </Link>
          </div>
        </Form>
      </div>
    </div>
  )
}

export default Register
