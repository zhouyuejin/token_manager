import { useEffect, useState, useMemo, useRef } from 'react'
import { useThemeToken } from '@/theme/useThemeToken'
import { Form, Input, Button } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { register } from '../api/auth'
import { useMessage } from '../utils/message'
import gsap from 'gsap'

// 单颗星星
const TwinklingStar = ({ x, y, size, baseOpacity, twinkleDuration, twinkleDelay }: { 
  x: number
  y: number
  size: number
  baseOpacity: number
  twinkleDuration: number
  twinkleDelay: number
}) => {
  const starRef = useRef<HTMLDivElement>(null)
  const tlRef = useRef<gsap.core.Timeline | null>(null)

  useEffect(() => {
    if (!starRef.current) return
    const star = starRef.current
    
    gsap.set(star, { opacity: baseOpacity })

    tlRef.current = gsap.timeline({ repeat: -1, delay: twinkleDelay })
    
    tlRef.current.to(star, {
      opacity: Math.min(baseOpacity + 0.4, 0.9),
      scale: 1.2,
      duration: twinkleDuration * (0.8 + Math.random() * 0.4),
      ease: 'sine.inOut',
    })
    .to(star, {
      opacity: Math.max(baseOpacity - 0.2, 0.1),
      scale: 0.9,
      duration: twinkleDuration * (0.6 + Math.random() * 0.4),
      ease: 'sine.inOut',
    })
    .to(star, {
      opacity: baseOpacity,
      scale: 1,
      duration: twinkleDuration * (0.5 + Math.random() * 0.3),
      ease: 'sine.inOut',
    })

    return () => {
      if (tlRef.current) tlRef.current.kill()
    }
  }, [baseOpacity, twinkleDuration, twinkleDelay])

  const isBig = size > 2

  return (
    <div
      ref={starRef}
      style={{
        position: 'absolute',
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        borderRadius: '50%',
        background: '#fff',
        boxShadow: isBig ? `0 0 ${size * 2}px rgba(255,255,255,0.8), 0 0 ${size * 4}px rgba(255,255,255,0.4)` : 'none',
        willChange: 'opacity, transform',
      }}
    />
  )
}

// 遥远的恒星
const DistantStar = ({ x, y, color }: { x: number; y: number; color: string }) => {
  const starRef = useRef<HTMLDivElement>(null)
  const tlRef = useRef<gsap.core.Timeline | null>(null)

  useEffect(() => {
    if (!starRef.current) return
    
    tlRef.current = gsap.timeline({ repeat: -1 })
    
    tlRef.current.to(starRef.current, {
      opacity: 0.3,
      scale: 1.1,
      duration: 3 + Math.random() * 2,
      ease: 'sine.inOut',
    })
    .to(starRef.current, {
      opacity: 0.8,
      scale: 1,
      duration: 3 + Math.random() * 2,
      ease: 'sine.inOut',
    })

    return () => {
      if (tlRef.current) tlRef.current.kill()
    }
  }, [])

  return (
    <div
      ref={starRef}
      style={{
        position: 'absolute',
        left: `${x}%`,
        top: `${y}%`,
        width: 4,
        height: 4,
        borderRadius: '50%',
        background: color,
        boxShadow: `0 0 20px ${color}, 0 0 40px ${color}, 0 0 60px rgba(255,255,255,0.3)`,
        opacity: 0.6,
      }}
    />
  )
}

// 缓慢飘动的星尘
const Stardust = ({ x, y, size, speed, delay }: { x: number; y: number; size: number; speed: number; delay: number }) => {
  const dustRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!dustRef.current) return

    gsap.to(dustRef.current, {
      y: '-=30',
      x: '+=15',
      opacity: 0.3,
      duration: speed,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut',
      delay: delay,
    })

  }, [speed, delay])

  return (
    <div
      ref={dustRef}
      style={{
        position: 'absolute',
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'rgba(200, 220, 255, 0.3)',
        filter: 'blur(1px)',
        opacity: 0.5,
      }}
    />
  )
}

// 星云光晕
const Nebula = () => {
  const nebula1Ref = useRef<HTMLDivElement>(null)
  const nebula2Ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (nebula1Ref.current) {
      gsap.to(nebula1Ref.current, {
        opacity: 0.15,
        scale: 1.05,
        duration: 8,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      })
    }
    if (nebula2Ref.current) {
      gsap.to(nebula2Ref.current, {
        opacity: 0.1,
        scale: 1.1,
        duration: 12,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
        delay: 2,
      })
    }
  }, [])

  return (
    <>
      <div
        ref={nebula1Ref}
        style={{
          position: 'absolute',
          top: '5%',
          left: '10%',
          width: '40%',
          height: '50%',
          background: 'radial-gradient(ellipse at 30% 40%, rgba(138, 43, 226, 0.12) 0%, rgba(138, 43, 226, 0.05) 40%, transparent 70%)',
          filter: 'blur(30px)',
          opacity: 0.1,
          pointerEvents: 'none',
        }}
      />
      <div
        ref={nebula2Ref}
        style={{
          position: 'absolute',
          bottom: '10%',
          right: '5%',
          width: '50%',
          height: '40%',
          background: 'radial-gradient(ellipse at 70% 60%, rgba(65, 105, 225, 0.1) 0%, rgba(65, 105, 225, 0.04) 40%, transparent 70%)',
          filter: 'blur(40px)',
          opacity: 0.08,
          pointerEvents: 'none',
        }}
      />
    </>
  )
}

// 地平线微光
const HorizonGlow = () => {
  const glowRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!glowRef.current) return
    
    gsap.to(glowRef.current, {
      opacity: 0.4,
      duration: 5,
      repeat: -1,
      yoyo: true,
      ease: 'sine.inOut',
    })
  }, [])

  return (
    <div
      ref={glowRef}
      style={{
        position: 'absolute',
        bottom: '15%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '120%',
        height: '200px',
        background: 'radial-gradient(ellipse at center bottom, rgba(100, 120, 180, 0.08) 0%, transparent 70%)',
        opacity: 0.2,
        pointerEvents: 'none',
      }}
    />
  )
}

// 星空背景
const StarField = () => {
  const stars = useMemo(() => {
    return Array.from({ length: 150 }, (_, i) => {
      const isBig = Math.random() > 0.92
      const isMedium = Math.random() > 0.8
      const size = isBig ? 2.5 + Math.random() * 1.5 : isMedium ? 1.5 + Math.random() * 0.8 : 0.5 + Math.random() * 1
      
      return {
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size,
        baseOpacity: isBig ? 0.6 + Math.random() * 0.3 : isMedium ? 0.3 + Math.random() * 0.3 : 0.1 + Math.random() * 0.2,
        twinkleDuration: 2 + Math.random() * 4,
        twinkleDelay: Math.random() * 8,
      }
    })
  }, [])

  const distantStars = useMemo(() => [
    { x: 15, y: 20, color: '#FFE4B5' },
    { x: 75, y: 15, color: '#ADD8E6' },
    { x: 35, y: 60, color: '#FFA07A' },
    { x: 80, y: 55, color: '#98FB98' },
    { x: 55, y: 10, color: '#E6E6FA' },
  ], [])

  const stardusts = useMemo(() => 
    Array.from({ length: 20 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: 1 + Math.random() * 2,
      speed: 8 + Math.random() * 12,
      delay: Math.random() * 5,
    }))
  , [])

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      {stars.map((star) => (
        <TwinklingStar key={star.id} {...star} />
      ))}
      {distantStars.map((star, i) => (
        <DistantStar key={`distant-${i}`} {...star} />
      ))}
      {stardusts.map((dust) => (
        <Stardust key={`dust-${dust.id}`} {...dust} />
      ))}
    </div>
  )
}

const Register = () => {
  const { token, isDark } = useThemeToken()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const message = useMessage()

  useEffect(() => {
    gsap.fromTo('.register-card', 
      { opacity: 0, y: 30, scale: 0.95 },
      { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: 'back.out(1.4)' }
    )

    gsap.fromTo('.register-input-wrap',
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5, stagger: 0.1, delay: 0.3, ease: 'power2.out' }
    )

    gsap.fromTo('#register-btn',
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.4, delay: 0.8, ease: 'power2.out' }
    )
  }, [])

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
      background: '#010106',
    }}>
      {/* 深空背景 */}
      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'radial-gradient(ellipse at 50% 30%, rgba(10,15,35,0.6) 0%, rgba(1,1,6,1) 70%)',
      }} />

      <Nebula />
      <StarField />
      <HorizonGlow />

      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '35%',
        background: 'linear-gradient(to top, rgba(1,1,6,0.95) 0%, rgba(1,1,6,0.5) 30%, transparent 100%)',
        pointerEvents: 'none',
      }} />
      
      {/* Register card */}
      <div 
        className="register-card"
        style={{ 
          position: 'relative',
          zIndex: 10,
          width: 420,
          padding: 44,
          background: 'rgba(8, 12, 20, 0.85)',
          backdropFilter: 'blur(20px)',
          borderRadius: 24,
          border: '1px solid rgba(255, 255, 255, 0.06)',
          boxShadow: '0 25px 60px -20px rgba(0, 0, 0, 0.8)',
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 64,
            height: 64,
            background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
            borderRadius: 18,
            marginBottom: 20,
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255,255,255,0.1)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <span style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 26,
              color: '#E2E8F0',
              textShadow: '0 2px 8px rgba(0,0,0,0.5)',
            }}>T</span>
          </div>
          <h1 style={{ 
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 24,
            fontWeight: 600,
            color: '#E2E8F0',
            marginBottom: 8,
          }}>
            注册账号
          </h1>
          <p style={{ color: '#64748B', fontSize: 14 }}>
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
          <div className="register-input-wrap">
            <Form.Item
              name="username"
              rules={[
                { required: true, message: '请输入用户名' },
                { min: 4, max: 20, message: '用户名4-20位' }
              ]}
              style={{ marginBottom: 16 }}
            >
              <Input 
                prefix={<UserOutlined style={{ color: '#475569' }} />} 
                placeholder="用户名（4-20位字母数字）"
                style={{
                  height: 52,
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 14,
                }}
              />
            </Form.Item>
          </div>

          <div className="register-input-wrap">
            <Form.Item
              name="email"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]}
              style={{ marginBottom: 16 }}
            >
              <Input 
                prefix={<MailOutlined style={{ color: '#475569' }} />} 
                placeholder="邮箱"
                style={{
                  height: 52,
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 14,
                }}
              />
            </Form.Item>
          </div>

          <div className="register-input-wrap">
            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 8, message: '密码至少8位' }
              ]}
              style={{ marginBottom: 16 }}
            >
              <Input.Password 
                prefix={<LockOutlined style={{ color: '#475569' }} />} 
                placeholder="密码（至少8位）"
                style={{
                  height: 52,
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 14,
                }}
              />
            </Form.Item>
          </div>

          <div className="register-input-wrap">
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
              style={{ marginBottom: 24 }}
            >
              <Input.Password 
                prefix={<LockOutlined style={{ color: '#475569' }} />} 
                placeholder="确认密码"
                style={{
                  height: 52,
                  background: 'rgba(30, 41, 59, 0.5)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: 14,
                }}
              />
            </Form.Item>
          </div>

          <Form.Item style={{ marginBottom: 20 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              block
              id="register-btn"
              style={{
                height: 52,
                borderRadius: 14,
                fontFamily: "'Space Grotesk', sans-serif",
                fontWeight: 600,
                fontSize: 16,
                background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
                border: '1px solid rgba(255,255,255,0.1)',
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
              }}
              onMouseEnter={(e) => {
                gsap.to(e.currentTarget, {
                  background: 'linear-gradient(135deg, #234b70 0%, #102540 100%)',
                  boxShadow: '0 6px 28px rgba(0, 0, 0, 0.4)',
                  duration: 0.25
                })
              }}
              onMouseLeave={(e) => {
                gsap.to(e.currentTarget, {
                  background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
                  duration: 0.25
                })
              }}
            >
              <span style={{ position: 'relative', zIndex: 1, letterSpacing: '0.15em', color: '#E2E8F0' }}>注 册</span>
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center', color: '#475569', fontSize: 14 }}>
            已有账号？{' '}
            <Link 
              to="/login" 
              style={{
                color: '#94A3B8',
                fontWeight: 500,
                textDecoration: 'none',
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                gsap.to(e.currentTarget, { color: '#CBD5E1', duration: 0.2 })
              }}
              onMouseLeave={(e) => {
                gsap.to(e.currentTarget, { color: '#94A3B8', duration: 0.2 })
              }}
            >
              立即登录
            </Link>
          </div>
        </Form>
      </div>

      <style>{`* { box-sizing: border-box; } body { margin: 0; padding: 0; }`}</style>
    </div>
  )
}

export default Register
