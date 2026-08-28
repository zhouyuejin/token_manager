import { useEffect, useState } from 'react'
import { Button, App } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import gsap from 'gsap'

// 判断是否为开发环境
const isDev = import.meta.env.DEV

// 自定义输入框组件
const CustomInput = ({ prefix, placeholder, type = 'text', value, onChange }: any) => (
  <div style={{
    position: 'relative',
    height: 52,
    background: 'rgba(30, 41, 59, 0.5)',
    borderRadius: 14,
    display: 'flex',
    alignItems: 'center',
    padding: '0 16px',
    transition: 'all 0.3s ease',
    border: '1px solid transparent',
  }}
    className="custom-input-wrap"
  >
    <span style={{ color: '#475569', fontSize: 18, marginRight: 12, display: 'flex' }}>
      {prefix}
    </span>
    <input
      type={type}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      style={{
        flex: 1,
        background: 'transparent',
        border: 'none',
        outline: 'none',
        fontSize: 15,
        color: '#F1F5F9',
        fontFamily: "'DM Sans', sans-serif",
      }}
    />
    <style>{`
      .custom-input-wrap:hover {
        background: rgba(30, 41, 59, 0.7) !important;
      }
      .custom-input-wrap:focus-within {
        background: rgba(30, 41, 59, 0.8) !important;
        border-color: rgba(99, 102, 241, 0.4) !important;
      }
      .custom-input-wrap input::placeholder {
        color: #64748B !important;
      }
    `}</style>
  </div>
)

const Login = () => {
  const navigate = useNavigate()
  const { login, isLoading } = useAuthStore()
  const { message } = App.useApp()
  
  // 开发环境默认填充账号密码
  const [username, setUsername] = useState(isDev ? 'admin' : '')
  const [password, setPassword] = useState(isDev ? 'admin123' : '')

  useEffect(() => {
    // Card entrance animation
    gsap.fromTo('.login-card', 
      { opacity: 0, y: 30, scale: 0.95 },
      { opacity: 1, y: 0, scale: 1, duration: 0.6, ease: 'back.out(1.4)' }
    )

    // Stagger input animations
    gsap.fromTo('.login-input-wrap',
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.15, delay: 0.3, ease: 'power2.out' }
    )

    // Button animation
    gsap.fromTo('#login-btn',
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.4, delay: 0.6, ease: 'power2.out' }
    )

    // Floating particles
    const particles = document.querySelectorAll('.particle')
    particles.forEach((particle) => {
      gsap.to(particle, {
        y: 'random(-20, 20)',
        x: 'random(-15, 15)',
        opacity: 'random(0.3, 0.7)',
        duration: 'random(3, 5)',
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      })
    })
  }, [])

  const onFinish = async () => {
    if (!username || !password) {
      message.error('请输入用户名和密码')
      return
    }
    try {
      await login({ username, password })
      message.success('登录成功')
      navigate('/dashboard')
    } catch (error) {
      // 错误已在请求拦截器中处理
    }
  }

  // Generate particles
  const particles = [...Array(15)].map((_, i) => ({
    id: i,
    size: Math.random() * 3 + 2,
    left: Math.random() * 100,
    top: Math.random() * 100,
    color: ['#3B82F6', '#8B5CF6', '#EA580C'][i % 3],
  }))

  return (
    <div style={{ 
      minHeight: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      background: '#0a0e17',
    }}>
      {/* Background Effects */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: `
          radial-gradient(ellipse at 20% 30%, rgba(59, 130, 246, 0.12) 0%, transparent 50%),
          radial-gradient(ellipse at 80% 70%, rgba(139, 92, 246, 0.1) 0%, transparent 50%),
          radial-gradient(ellipse at 50% 50%, rgba(234, 88, 12, 0.06) 0%, transparent 60%)
        `,
      }} />

      {/* Grid */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: `
          linear-gradient(rgba(59, 130, 246, 0.02) 1px, transparent 1px),
          linear-gradient(90deg, rgba(59, 130, 246, 0.02) 1px, transparent 1px)
        `,
        backgroundSize: '60px 60px',
      }} />

      {/* Particles */}
      {particles.map((p) => (
        <div
          key={p.id}
          className="particle"
          style={{
            position: 'absolute',
            width: p.size,
            height: p.size,
            left: `${p.left}%`,
            top: `${p.top}%`,
            background: p.color,
            borderRadius: '50%',
            opacity: 0.5,
            boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
          }}
        />
      ))}
      
      {/* Login Card */}
      <div 
        className="login-card"
        style={{ 
          position: 'relative',
          zIndex: 1,
          width: 380,
          padding: 40,
          background: 'rgba(15, 23, 42, 0.9)',
          backdropFilter: 'blur(20px)',
          borderRadius: 20,
          border: '1px solid rgba(255, 255, 255, 0.06)',
          boxShadow: '0 25px 50px -20px rgba(0, 0, 0, 0.5)',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 52,
            height: 52,
            background: 'linear-gradient(135deg, #2563EB 0%, #6366F1 100%)',
            borderRadius: 14,
            marginBottom: 16,
            boxShadow: '0 8px 24px rgba(37, 99, 235, 0.3)',
          }}>
            <span style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 22,
              color: 'white',
            }}>T</span>
          </div>
          <h1 style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 22,
            fontWeight: 600,
            color: '#F8FAFC',
            marginBottom: 6,
            letterSpacing: '-0.02em',
          }}>
            Token中转平台
          </h1>
          <p style={{ color: '#64748B', fontSize: 13 }}>
            统一API入口，管理大模型调用
          </p>
        </div>
        
        <form onSubmit={onFinish}>
          <div className="login-input-wrap" style={{ marginBottom: 16 }}>
            <CustomInput
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
              value={username}
              onChange={(e: any) => setUsername(e.target.value)}
            />
          </div>

          <div className="login-input-wrap" style={{ marginBottom: 20 }}>
            <CustomInput
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              type="password"
              value={password}
              onChange={(e: any) => setPassword(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={isLoading}
              block
              id="login-btn"
              style={{
                height: 48,
                borderRadius: 12,
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
                fontSize: 15,
                background: 'linear-gradient(135deg, #2563EB 0%, #6366F1 100%)',
                border: 'none',
                boxShadow: '0 4px 16px rgba(37, 99, 235, 0.3)',
              }}
              onMouseEnter={(e) => {
                gsap.to(e.currentTarget, {
                  boxShadow: '0 6px 24px rgba(37, 99, 235, 0.45)',
                  duration: 0.2
                })
              }}
              onMouseLeave={(e) => {
                gsap.to(e.currentTarget, {
                  boxShadow: '0 4px 16px rgba(37, 99, 235, 0.3)',
                  duration: 0.2
                })
              }}
            >
              登 录
            </Button>
          </div>

          <div style={{ textAlign: 'center', color: '#64748B', fontSize: 13 }} id="login-btn">
            还没有账号？{' '}
            <Link 
              to="/register" 
              style={{
                color: '#6366F1',
                fontWeight: 500,
                textDecoration: 'none',
              }}
            >
              立即注册
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Login
