import { theme } from 'antd'

/**
 * 主题感知 Hook
 * 用于获取当前主题的颜色 tokens
 * 可以在任何组件中使用，自动响应主题变化
 */
export const useThemeToken = () => {
  const { token } = theme.useToken()
  
  // 判断是否为深色主题 - 通过判断 colorBgBase
  const isDark = token.colorBgBase === '#0F172A' || 
                 token.colorBgBase === '#1E1B2E' ||
                 token.colorBgBase === '#0F1712' ||
                 token.colorBgBase === '#0C1222'
  
  return {
    token,
    isDark,
    // 常用颜色便捷访问
    colorBgBase: token.colorBgBase,
    colorTextBase: token.colorTextBase,
    colorBgContainer: token.colorBgContainer,
    colorBgElevated: token.colorBgElevated,
    colorText: token.colorText,
    colorTextSecondary: token.colorTextSecondary,
    colorBorder: token.colorBorder,
    colorPrimary: token.colorPrimary,
  }
}

/**
 * 获取用于样式对象的颜色
 * 根据当前主题返回正确的颜色
 */
export const getThemedColors = (isDark: boolean) => ({
  // 背景色
  bgBase: isDark ? '#0F172A' : '#F8FAFC',
  bgContainer: isDark ? '#111827' : '#FFFFFF',
  bgElevated: isDark ? '#1E293B' : '#FFFFFF',
  bgLayout: isDark ? '#0F172A' : '#F8FAFC',
  bgSpotlight: isDark ? '#1E293B' : '#FFFFFF',
  
  // 文字色
  text: isDark ? '#F8FAFC' : '#1E293B',
  textSecondary: isDark ? '#CBD5E1' : '#64748B',
  textTertiary: isDark ? '#94A3B8' : '#94A3B8',
  
  // 边框色
  border: isDark ? '#334155' : '#E2E8F0',
  borderSecondary: isDark ? '#334155' : '#F1F5F9',
  
  // 主题色
  primary: isDark ? '#3B82F6' : '#2563EB',
  primaryHover: isDark ? '#60A5FA' : '#3B82F6',
  
  // 卡片背景 (半透明)
  cardBg: isDark ? 'rgba(17, 24, 39, 0.6)' : 'rgba(255, 255, 255, 0.8)',
  cardBorder: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)',
})

export default useThemeToken
