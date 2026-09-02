import React, { createContext, useContext, useState, useEffect, ReactNode, useMemo, useCallback } from 'react'
import { ConfigProvider, theme as antTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { ThemeName, themeMap, themeOptions, ThemeConfig } from './themes'

const THEME_STORAGE_KEY = 'token-manager-theme'

// CSS 变量配置 - 用于自定义组件
const themeCSSVars: Record<ThemeName, Record<string, string>> = {
  dark: {
    '--color-primary': '#2563EB',
    '--color-primary-hover': '#3B82F6',
    '--color-primary-active': '#1D4ED8',
    '--color-secondary': '#3B82F6',
    '--color-accent': '#EA580C',
    '--color-background': '#0F172A',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#111827',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#1E293B',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#334155',
    '--color-border-secondary': '#334155',
    '--color-destructive': '#DC2626',
    '--color-ring': '#2563EB',
    '--color-success': '#22C55E',
    '--color-warning': '#F59E0B',
    '--color-error': '#DC2626',
    '--color-info': '#2563EB',
    '--color-text': '#F8FAFC',
    '--color-text-secondary': '#CBD5E1',
    '--color-text-tertiary': '#94A3B8',
    '--color-text-quaternary': '#64748B',
    '--glass-bg': 'rgba(17, 24, 39, 0.8)',
    '--glass-border': 'rgba(255, 255, 255, 0.1)',
    '--shadow-glow': '0 0 20px rgba(37, 99, 235, 0.3)',
    '--shadow-card': '0 4px 20px rgba(0, 0, 0, 0.3)',
    '--menu-hover-bg': 'rgba(37, 99, 235, 0.1)',
    '--menu-selected-bg': 'rgba(37, 99, 235, 0.2)',
    '--header-bg': 'rgba(17, 24, 39, 0.8)',
    '--sider-bg': 'rgba(17, 24, 39, 0.8)',
  },
  light: {
    '--color-primary': '#2563EB',
    '--color-primary-hover': '#3B82F6',
    '--color-primary-active': '#1D4ED8',
    '--color-secondary': '#3B82F6',
    '--color-accent': '#EA580C',
    '--color-background': '#F8FAFC',
    '--color-foreground': '#1E293B',
    '--color-card': '#FFFFFF',
    '--color-card-foreground': '#1E293B',
    '--color-muted': '#F1F5F9',
    '--color-muted-foreground': '#64748B',
    '--color-border': '#E2E8F0',
    '--color-border-secondary': '#F1F5F9',
    '--color-destructive': '#DC2626',
    '--color-ring': '#2563EB',
    '--color-success': '#22C55E',
    '--color-warning': '#F59E0B',
    '--color-error': '#DC2626',
    '--color-info': '#2563EB',
    '--color-text': '#1E293B',
    '--color-text-secondary': '#64748B',
    '--color-text-tertiary': '#94A3B8',
    '--color-text-quaternary': '#CBD5E1',
    '--glass-bg': 'rgba(255, 255, 255, 0.8)',
    '--glass-border': 'rgba(0, 0, 0, 0.08)',
    '--shadow-glow': '0 0 20px rgba(37, 99, 235, 0.15)',
    '--shadow-card': '0 4px 20px rgba(0, 0, 0, 0.08)',
    '--menu-hover-bg': 'rgba(37, 99, 235, 0.08)',
    '--menu-selected-bg': 'rgba(37, 99, 235, 0.15)',
    '--header-bg': '#FFFFFF',
    '--sider-bg': '#FFFFFF',
  },
  purple: {
    '--color-primary': '#8B5CF6',
    '--color-primary-hover': '#A78BFA',
    '--color-primary-active': '#7C3AED',
    '--color-secondary': '#A78BFA',
    '--color-accent': '#EA580C',
    '--color-background': '#1E1B2E',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#2D2640',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#3D3556',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#4C3F6E',
    '--color-border-secondary': '#4C3F6E',
    '--color-destructive': '#DC2626',
    '--color-ring': '#8B5CF6',
    '--color-success': '#22C55E',
    '--color-warning': '#F59E0B',
    '--color-error': '#DC2626',
    '--color-info': '#8B5CF6',
    '--color-text': '#F8FAFC',
    '--color-text-secondary': '#CBD5E1',
    '--color-text-tertiary': '#94A3B8',
    '--color-text-quaternary': '#64748B',
    '--glass-bg': 'rgba(45, 38, 64, 0.8)',
    '--glass-border': 'rgba(139, 92, 246, 0.15)',
    '--shadow-glow': '0 0 20px rgba(139, 92, 246, 0.3)',
    '--shadow-card': '0 4px 20px rgba(0, 0, 0, 0.3)',
    '--menu-hover-bg': 'rgba(139, 92, 246, 0.12)',
    '--menu-selected-bg': 'rgba(139, 92, 246, 0.25)',
    '--header-bg': 'rgba(30, 27, 46, 0.8)',
    '--sider-bg': 'rgba(30, 27, 46, 0.8)',
  },
  green: {
    '--color-primary': '#10B981',
    '--color-primary-hover': '#34D399',
    '--color-primary-active': '#059669',
    '--color-secondary': '#34D399',
    '--color-accent': '#F59E0B',
    '--color-background': '#0F1712',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#16221C',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#1A2E25',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#2D3F35',
    '--color-border-secondary': '#2D3F35',
    '--color-destructive': '#DC2626',
    '--color-ring': '#10B981',
    '--color-success': '#22C55E',
    '--color-warning': '#F59E0B',
    '--color-error': '#DC2626',
    '--color-info': '#10B981',
    '--color-text': '#F8FAFC',
    '--color-text-secondary': '#CBD5E1',
    '--color-text-tertiary': '#94A3B8',
    '--color-text-quaternary': '#64748B',
    '--glass-bg': 'rgba(22, 34, 28, 0.8)',
    '--glass-border': 'rgba(16, 185, 129, 0.15)',
    '--shadow-glow': '0 0 20px rgba(16, 185, 129, 0.3)',
    '--shadow-card': '0 4px 20px rgba(0, 0, 0, 0.3)',
    '--menu-hover-bg': 'rgba(16, 185, 129, 0.1)',
    '--menu-selected-bg': 'rgba(16, 185, 129, 0.2)',
    '--header-bg': 'rgba(22, 34, 28, 0.8)',
    '--sider-bg': 'rgba(22, 34, 28, 0.8)',
  },
  ocean: {
    '--color-primary': '#0EA5E9',
    '--color-primary-hover': '#38BDF8',
    '--color-primary-active': '#0284C7',
    '--color-secondary': '#38BDF8',
    '--color-accent': '#F59E0B',
    '--color-background': '#0C1222',
    '--color-foreground': '#F8FAFC',
    '--color-card': '#162035',
    '--color-card-foreground': '#F8FAFC',
    '--color-muted': '#1E2A42',
    '--color-muted-foreground': '#CBD5E1',
    '--color-border': '#2D3F5C',
    '--color-border-secondary': '#2D3F5C',
    '--color-destructive': '#DC2626',
    '--color-ring': '#0EA5E9',
    '--color-success': '#22C55E',
    '--color-warning': '#F59E0B',
    '--color-error': '#DC2626',
    '--color-info': '#0EA5E9',
    '--color-text': '#F8FAFC',
    '--color-text-secondary': '#CBD5E1',
    '--color-text-tertiary': '#94A3B8',
    '--color-text-quaternary': '#64748B',
    '--glass-bg': 'rgba(22, 32, 53, 0.8)',
    '--glass-border': 'rgba(14, 165, 233, 0.15)',
    '--shadow-glow': '0 0 20px rgba(14, 165, 233, 0.3)',
    '--shadow-card': '0 4px 20px rgba(0, 0, 0, 0.3)',
    '--menu-hover-bg': 'rgba(14, 165, 233, 0.1)',
    '--menu-selected-bg': 'rgba(14, 165, 233, 0.2)',
    '--header-bg': 'rgba(22, 32, 53, 0.8)',
    '--sider-bg': 'rgba(22, 32, 53, 0.8)',
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

// Hook: 获取当前主题的 Design Token
export const useDesignToken = () => {
  const { token } = antTheme.useToken()
  return token
}

interface ThemeProviderProps {
  children: ReactNode
}

// 应用 CSS 变量到 document
const applyCSSVars = (themeName: ThemeName) => {
  const root = document.documentElement
  const vars = themeCSSVars[themeName]
  Object.entries(vars).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeName>(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      if (stored && themeOptions.some(opt => opt.name === stored)) {
        return stored as ThemeName
      }
    } catch {
      // 忽略存储异常
    }
    return 'dark'
  })

  // 初始化时应用 CSS 变量
  useEffect(() => {
    applyCSSVars(theme)
  }, [theme])

  // 持久化主题设置
  useEffect(() => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // 忽略存储异常
    }
  }, [theme])

  const setTheme = useCallback((newTheme: ThemeName) => {
    setThemeState(newTheme)
  }, [])

  // 使用 useMemo 缓存主题配置
  const themeConfig = useMemo(() => themeMap[theme], [theme])

  const contextValue = useMemo(() => ({
    theme,
    setTheme,
    themeOptions,
  }), [theme, setTheme])

  return (
    <ThemeContext.Provider value={contextValue}>
      <ConfigProvider theme={themeConfig} locale={zhCN}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}

// 导出主题配置供其他地方使用
export { themeMap, themeOptions, themeCSSVars, type ThemeName }
export default ThemeProvider
