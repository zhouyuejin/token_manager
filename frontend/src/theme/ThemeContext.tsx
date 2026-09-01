import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { ThemeName, themeMap, themeOptions } from './themes'

const THEME_STORAGE_KEY = 'token-manager-theme'

// 各主题的 CSS 变量
const themeCSSVars: Record<ThemeName, Record<string, string>> = {
  dark: {
    '--color-primary': '#2563EB',
    '--color-primary-hover': '#1D4ED8',
    '--color-secondary': '#3B82F6',
    '--color-accent': '#EA580C',
    '--color-background': '#0F172A',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#111827',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#1E293B',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#334155',
    '--color-destructive': '#DC2626',
    '--color-ring': '#2563EB',
    '--glass-bg': 'rgba(17, 24, 39, 0.7)',
    '--glass-border': 'rgba(255, 255, 255, 0.1)',
    '--shadow-glow': '0 0 20px rgba(37, 99, 235, 0.3)',
    '--menu-hover-bg': 'rgba(37, 99, 235, 0.1)',
    '--menu-selected-bg': 'linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(59, 130, 246, 0.2) 100%)',
    '--header-bg': 'rgba(17, 24, 39, 0.7)',
    '--sider-bg': 'rgba(17, 24, 39, 0.7)',
  },
  light: {
    '--color-primary': '#2563EB',
    '--color-primary-hover': '#1D4ED8',
    '--color-secondary': '#3B82F6',
    '--color-accent': '#EA580C',
    '--color-background': '#F8FAFC',
    '--color-foreground': '#1E293B',
    '--color-card': '#FFFFFF',
    '--color-card-foreground': '#1E293B',
    '--color-muted': '#F1F5F9',
    '--color-muted-foreground': '#64748B',
    '--color-border': '#E2E8F0',
    '--color-destructive': '#DC2626',
    '--color-ring': '#2563EB',
    '--glass-bg': 'rgba(255, 255, 255, 0.8)',
    '--glass-border': 'rgba(0, 0, 0, 0.08)',
    '--shadow-glow': '0 0 20px rgba(37, 99, 235, 0.15)',
    '--menu-hover-bg': 'rgba(37, 99, 235, 0.08)',
    '--menu-selected-bg': 'linear-gradient(135deg, rgba(37, 99, 235, 0.2) 0%, rgba(59, 130, 246, 0.15) 100%)',
    '--header-bg': 'rgba(255, 255, 255, 0.8)',
    '--sider-bg': 'rgba(255, 255, 255, 0.8)',
  },
  purple: {
    '--color-primary': '#8B5CF6',
    '--color-primary-hover': '#7C3AED',
    '--color-secondary': '#A78BFA',
    '--color-accent': '#EA580C',
    '--color-background': '#1E1B2E',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#2D2640',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#3D3556',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#4C3F6E',
    '--color-destructive': '#DC2626',
    '--color-ring': '#8B5CF6',
    '--glass-bg': 'rgba(45, 38, 64, 0.7)',
    '--glass-border': 'rgba(139, 92, 246, 0.15)',
    '--shadow-glow': '0 0 20px rgba(139, 92, 246, 0.3)',
    '--menu-hover-bg': 'rgba(139, 92, 246, 0.12)',
    '--menu-selected-bg': 'linear-gradient(135deg, rgba(139, 92, 246, 0.3) 0%, rgba(167, 139, 250, 0.2) 100%)',
    '--header-bg': 'rgba(45, 38, 64, 0.7)',
    '--sider-bg': 'rgba(45, 38, 64, 0.7)',
  },
  green: {
    '--color-primary': '#10B981',
    '--color-primary-hover': '#059669',
    '--color-secondary': '#34D399',
    '--color-accent': '#F59E0B',
    '--color-background': '#0F1712',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#16221C',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#1A2E25',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#2D3F35',
    '--color-destructive': '#DC2626',
    '--color-ring': '#10B981',
    '--glass-bg': 'rgba(22, 34, 28, 0.7)',
    '--glass-border': 'rgba(16, 185, 129, 0.15)',
    '--shadow-glow': '0 0 20px rgba(16, 185, 129, 0.3)',
    '--menu-hover-bg': 'rgba(16, 185, 129, 0.1)',
    '--menu-selected-bg': 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(52, 211, 153, 0.2) 100%)',
    '--header-bg': 'rgba(22, 34, 28, 0.7)',
    '--sider-bg': 'rgba(22, 34, 28, 0.7)',
  },
}

interface ThemeContextValue {
  theme: ThemeName
  setTheme: (theme: ThemeName) => void
  themeOptions: typeof themeOptions
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

// 应用 CSS 变量
const applyCSSVars = (theme: ThemeName) => {
  const root = document.documentElement
  const vars = themeCSSVars[theme]
  Object.entries(vars).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })
}

interface ThemeProviderProps {
  children: ReactNode
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      if (stored && (stored === 'dark' || stored === 'light' || stored === 'purple' || stored === 'green')) {
        return stored as ThemeName
      }
    } catch {
      // 忽略存储异常
    }
    return 'dark'
  })

  // 初始化和切换主题时应用 CSS 变量
  useEffect(() => {
    applyCSSVars(theme)
  }, [theme])

  useEffect(() => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // 忽略存储异常
    }
  }, [theme])

  const setTheme = (newTheme: ThemeName) => {
    
    setThemeState(newTheme)
  }

  const themeConfig = themeMap[theme]

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themeOptions }}>
      <ConfigProvider theme={themeConfig} locale={zhCN}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}
