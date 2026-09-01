import { ThemeConfig, theme } from 'antd'

export type ThemeName = 'dark' | 'light' | 'purple' | 'green'

export interface ThemeOption {
  name: ThemeName
  label: string
  icon: string
}

export const themeOptions: ThemeOption[] = [
  { name: 'dark', label: '深色主题', icon: '🌙' },
  { name: 'light', label: '亮色主题', icon: '☀️' },
  { name: 'purple', label: '紫罗兰', icon: '🟣' },
  { name: 'green', label: '翠绿主题', icon: '🌿' },
]

// 通用主题配置
const getBaseConfig = (primaryColor: string): Partial<ThemeConfig['token']> => ({
  colorPrimary: primaryColor,
  borderRadius: 10,
  fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  colorSuccess: '#22C55E',
  colorWarning: '#F59E0B',
  colorError: '#DC2626',
  colorInfo: primaryColor,
})

// 深色主题
export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    ...getBaseConfig('#2563EB'),
    colorBgContainer: '#111827',
    colorBgElevated: '#1E293B',
    colorBorder: '#334155',
    colorBorderSecondary: '#334155',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#64748B',
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      siderBg: 'transparent',
      bodyBg: 'transparent',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(37, 99, 235, 0.2)',
      darkItemHoverBg: 'rgba(37, 99, 235, 0.1)',
    },
    Card: {
      colorBgContainer: 'rgba(17, 24, 39, 0.7)',
      colorBorderSecondary: '#334155',
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#1E293B',
    },
    Input: {
      colorBgContainer: '#1E293B',
      colorBorder: '#334155',
      hoverBorderColor: '#2563EB',
      activeBorderColor: '#2563EB',
    },
    Button: {
      primaryShadow: '0 0 20px rgba(37, 99, 235, 0.3)',
    },
  },
}

// 亮色主题
export const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    ...getBaseConfig('#2563EB'),
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBorder: '#E2E8F0',
    colorBorderSecondary: '#F1F5F9',
    colorText: '#1E293B',
    colorTextSecondary: '#64748B',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#CBD5E1',
  },
  components: {
    Layout: {
      headerBg: '#FFFFFF',
      siderBg: '#FFFFFF',
      bodyBg: '#F8FAFC',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(37, 99, 235, 0.15)',
      darkItemHoverBg: 'rgba(37, 99, 235, 0.08)',
    },
    Card: {
      colorBgContainer: '#FFFFFF',
      colorBorderSecondary: '#E2E8F0',
    },
    Table: {
      colorBgContainer: '#FFFFFF',
      headerBg: '#F8FAFC',
    },
    Input: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#E2E8F0',
      hoverBorderColor: '#2563EB',
      activeBorderColor: '#2563EB',
    },
    Button: {
      primaryShadow: '0 2px 8px rgba(37, 99, 235, 0.25)',
    },
  },
}

// 紫罗兰主题
export const purpleTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    ...getBaseConfig('#8B5CF6'),
    colorBgContainer: '#1E1B2E',
    colorBgElevated: '#2D2640',
    colorBorder: '#4C3F6E',
    colorBorderSecondary: '#4C3F6E',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#64748B',
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      siderBg: 'transparent',
      bodyBg: 'transparent',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(139, 92, 246, 0.25)',
      darkItemHoverBg: 'rgba(139, 92, 246, 0.12)',
    },
    Card: {
      colorBgContainer: 'rgba(30, 27, 46, 0.7)',
      colorBorderSecondary: '#4C3F6E',
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#2D2640',
    },
    Input: {
      colorBgContainer: '#2D2640',
      colorBorder: '#4C3F6E',
      hoverBorderColor: '#8B5CF6',
      activeBorderColor: '#8B5CF6',
    },
    Button: {
      primaryShadow: '0 0 20px rgba(139, 92, 246, 0.3)',
    },
  },
}

// 翠绿主题
export const greenTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    ...getBaseConfig('#10B981'),
    colorBgContainer: '#0F1712',
    colorBgElevated: '#16221C',
    colorBorder: '#2D3F35',
    colorBorderSecondary: '#2D3F35',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#64748B',
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      siderBg: 'transparent',
      bodyBg: 'transparent',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(16, 185, 129, 0.2)',
      darkItemHoverBg: 'rgba(16, 185, 129, 0.1)',
    },
    Card: {
      colorBgContainer: 'rgba(15, 23, 18, 0.7)',
      colorBorderSecondary: '#2D3F35',
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#16221C',
    },
    Input: {
      colorBgContainer: '#16221C',
      colorBorder: '#2D3F35',
      hoverBorderColor: '#10B981',
      activeBorderColor: '#10B981',
    },
    Button: {
      primaryShadow: '0 0 20px rgba(16, 185, 129, 0.3)',
    },
  },
}

// 主题映射
export const themeMap: Record<ThemeName, ThemeConfig> = {
  dark: darkTheme,
  light: lightTheme,
  purple: purpleTheme,
  green: greenTheme,
}
