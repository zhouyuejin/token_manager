import { ThemeConfig, theme } from 'antd'

export type ThemeName = 'dark' | 'light' | 'purple' | 'green' | 'ocean'

export interface ThemeOption {
  name: ThemeName
  label: string
  icon: string
  primaryColor: string
}

export const themeOptions: ThemeOption[] = [
  { name: 'dark', label: '深色主题', icon: '🌙', primaryColor: '#2563EB' },
  { name: 'light', label: '亮色主题', icon: '☀️', primaryColor: '#2563EB' },
  { name: 'purple', label: '紫罗兰', icon: '🟣', primaryColor: '#8B5CF6' },
  { name: 'green', label: '翠绿主题', icon: '🌿', primaryColor: '#10B981' },
  { name: 'ocean', label: '海洋之心', icon: '🌊', primaryColor: '#0EA5E9' },
]

// 基础 Seed Token 配置
const getBaseToken = (primaryColor: string) => ({
  colorPrimary: primaryColor,
  borderRadius: 10,
  fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  colorSuccess: '#22C55E',
  colorWarning: '#F59E0B',
  colorError: '#DC2626',
  colorInfo: primaryColor,
})

// ============================================================
// 深色主题
// ============================================================
export const darkTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#2563EB'),
    colorBgBase: '#0F172A',
    colorTextBase: '#F8FAFC',
    colorBgContainer: '#111827',
    colorBgElevated: '#1E293B',
    colorBgLayout: '#0F172A',
    colorBgSpotlight: '#1E293B',
    colorBorder: '#334155',
    colorBorderSecondary: '#334155',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#64748B',
    colorFill: 'rgba(148, 163, 184, 0.15)',
    colorFillSecondary: 'rgba(148, 163, 184, 0.1)',
    colorFillTertiary: 'rgba(148, 163, 184, 0.06)',
    colorFillQuaternary: 'rgba(148, 163, 184, 0.04)',
    colorSplit: 'rgba(148, 163, 184, 0.1)',
    colorLink: '#3B82F6',
    colorLinkHover: '#60A5FA',
    colorLinkActive: '#2563EB',
  },
  algorithm: theme.darkAlgorithm,
  components: {
    Layout: {
      headerBg: 'rgba(17, 24, 39, 0.95)',
      siderBg: 'rgba(17, 24, 39, 0.95)',
      bodyBg: '#0F172A',
      headerPadding: '0 24px',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(37, 99, 235, 0.2)',
      darkItemHoverBg: 'rgba(37, 99, 235, 0.1)',
      darkItemSelectedColor: '#3B82F6',
      darkItemColor: '#CBD5E1',
      itemMarginInline: 8,
      itemPaddingInline: 12,
    },
    Card: {
      colorBgContainer: 'rgba(17, 24, 39, 0.6)',
      colorBorderSecondary: '#334155',
      paddingLG: 24,
      borderRadiusLG: 12,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#1E293B',
      headerColor: '#F8FAFC',
      rowHoverBg: 'rgba(37, 99, 235, 0.08)',
      borderColor: '#334155',
    },
    Input: {
      colorBgContainer: '#1E293B',
      colorBorder: '#334155',
      hoverBorderColor: '#2563EB',
      activeBorderColor: '#2563EB',
      activeShadow: '0 0 0 2px rgba(37, 99, 235, 0.2)',
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(37, 99, 235, 0.4)',
      defaultShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
    },
    Select: {
      colorBgContainer: '#1E293B',
      colorBorder: '#334155',
      optionSelectedBg: 'rgba(37, 99, 235, 0.2)',
    },
    Dropdown: {
      colorBgElevated: 'rgba(17, 24, 39, 0.98)',
      colorBgSpotlight: 'rgba(30, 41, 59, 0.98)',
    },
    Modal: {
      contentBg: '#111827',
      headerBg: '#111827',
      footerBg: '#111827',
      titleColor: '#F8FAFC',
      titleFontSize: 16,
      borderRadiusLG: 12,
    },
    Drawer: {
      colorBgElevated: '#111827',
    },
    Popover: {
      colorBgElevated: 'rgba(17, 24, 39, 0.98)',
    },
    Tooltip: {
      colorBgSpotlight: 'rgba(17, 24, 39, 0.98)',
    },
    Tabs: {
      inkBarColor: '#2563EB',
      itemSelectedColor: '#3B82F6',
      itemHoverColor: '#60A5FA',
    },
    Badge: {
      colorBgContainer: '#DC2626',
    },
    Switch: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Checkbox: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Radio: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Slider: {
      trackBg: 'rgba(37, 99, 235, 0.3)',
      railBg: 'rgba(148, 163, 184, 0.2)',
      handleColor: '#2563EB',
      dotActiveBorderColor: '#2563EB',
    },
    Progress: {
      remainingColor: 'rgba(148, 163, 184, 0.15)',
    },
    Skeleton: {
      gradientFromColor: 'rgba(30, 41, 59, 0.6)',
      gradientToColor: 'rgba(17, 24, 39, 0.4)',
    },
    Alert: {
      colorInfoBg: 'rgba(37, 99, 235, 0.1)',
      colorSuccessBg: 'rgba(34, 197, 94, 0.1)',
      colorWarningBg: 'rgba(245, 158, 11, 0.1)',
      colorErrorBg: 'rgba(220, 38, 38, 0.1)',
    },
    Message: {
      contentBg: '#1E293B',
    },
    Notification: {
      colorBgElevated: 'rgba(17, 24, 39, 0.98)',
    },
    Form: {
      labelColor: '#CBD5E1',
    },
    InputNumber: {
      colorBgContainer: '#1E293B',
      colorBorder: '#334155',
    },
  },
}

// ============================================================
// 亮色主题 - 修复版
// ============================================================
export const lightTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#2563EB'),
    colorBgBase: '#F8FAFC',
    colorTextBase: '#1E293B',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#F8FAFC',
    colorBgSpotlight: '#FFFFFF',
    colorBorder: '#E2E8F0',
    colorBorderSecondary: '#F1F5F9',
    colorText: '#1E293B',
    colorTextSecondary: '#64748B',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#94A3B8',
    colorFill: 'rgba(0, 0, 0, 0.06)',
    colorFillSecondary: 'rgba(0, 0, 0, 0.04)',
    colorFillTertiary: 'rgba(0, 0, 0, 0.02)',
    colorFillQuaternary: 'rgba(0, 0, 0, 0.01)',
    colorSplit: 'rgba(0, 0, 0, 0.06)',
    colorLink: '#2563EB',
    colorLinkHover: '#3B82F6',
    colorLinkActive: '#1D4ED8',
  },
  algorithm: theme.defaultAlgorithm,
  components: {
    Layout: {
      headerBg: '#FFFFFF',
      siderBg: '#FFFFFF',
      bodyBg: '#F8FAFC',
      headerPadding: '0 24px',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(37, 99, 235, 0.1)',
      itemHoverBg: 'rgba(37, 99, 235, 0.05)',
      itemSelectedColor: '#2563EB',
      itemColor: '#64748B',
      itemHoverColor: '#2563EB',
      itemMarginInline: 8,
      itemPaddingInline: 12,
      subMenuItemBg: 'transparent',
    },
    Card: {
      colorBgContainer: '#FFFFFF',
      colorBorderSecondary: '#E2E8F0',
      paddingLG: 24,
      borderRadiusLG: 12,
    },
    Table: {
      colorBgContainer: '#FFFFFF',
      headerBg: '#F1F5F9',
      headerColor: '#1E293B',
      rowHoverBg: 'rgba(37, 99, 235, 0.04)',
      borderColor: '#E2E8F0',
      borderRadius: 8,
      headerSortActiveBg: '#E2E8F0',
      headerSortHoverBg: '#E2E8F0',
      bodySortBg: 'rgba(0, 0, 0, 0.02)',
      rowSelectedBg: 'rgba(37, 99, 235, 0.05)',
      rowSelectedHoverBg: 'rgba(37, 99, 235, 0.08)',
      // 额外的 Table token
      colorText: '#1E293B',
      colorTextHeading: '#475569',
      colorFillAlter: 'rgba(0, 0, 0, 0.02)',
      headerSplitColor: '#E2E8F0',
      cellPaddingBlock: 12,
      cellPaddingInline: 12,
    },
    Input: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#E2E8F0',
      hoverBorderColor: '#2563EB',
      activeBorderColor: '#2563EB',
      activeShadow: '0 0 0 2px rgba(37, 99, 235, 0.1)',
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(37, 99, 235, 0.3)',
      defaultShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
    },
    Select: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#E2E8F0',
      optionSelectedBg: 'rgba(37, 99, 235, 0.1)',
      optionActiveBg: 'rgba(37, 99, 235, 0.08)',
    },
    Dropdown: {
      colorBgElevated: '#FFFFFF',
      colorBgSpotlight: '#FFFFFF',
    },
    Modal: {
      contentBg: '#FFFFFF',
      headerBg: '#FFFFFF',
      footerBg: '#FFFFFF',
      titleColor: '#1E293B',
      titleFontSize: 16,
      borderRadiusLG: 12,
      // 额外的 Modal 样式
      colorText: '#1E293B',
    },
    Drawer: {
      colorBgElevated: '#FFFFFF',
    },
    Popover: {
      colorBgElevated: '#FFFFFF',
    },
    Tooltip: {
      colorBgSpotlight: '#1E293B',
      colorText: '#FFFFFF',
    },
    Tabs: {
      inkBarColor: '#2563EB',
      itemSelectedColor: '#2563EB',
      itemHoverColor: '#3B82F6',
    },
    Form: {
      labelColor: '#1E293B',
    },
    Message: {
      contentBg: '#FFFFFF',
    },
    Notification: {
      colorBgElevated: '#FFFFFF',
    },
    InputNumber: {
      colorBgContainer: '#FFFFFF',
      colorBorder: '#E2E8F0',
    },
    Checkbox: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Radio: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Switch: {
      colorPrimary: '#2563EB',
      colorPrimaryHover: '#3B82F6',
    },
    Badge: {
      colorBgContainer: '#2563EB',
    },
    Progress: {
      remainingColor: 'rgba(37, 99, 235, 0.1)',
    },
    Alert: {
      colorInfoBg: 'rgba(37, 99, 235, 0.1)',
      colorSuccessBg: 'rgba(34, 197, 94, 0.1)',
      colorWarningBg: 'rgba(245, 158, 11, 0.1)',
      colorErrorBg: 'rgba(220, 38, 38, 0.1)',
    },
  },
}

// ============================================================
// 紫罗兰主题
// ============================================================
export const purpleTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#8B5CF6'),
    colorBgBase: '#1E1B2E',
    colorTextBase: '#F8FAFC',
    colorBgContainer: '#2D2640',
    colorBgElevated: '#3D3556',
    colorBgLayout: '#1E1B2E',
    colorBgSpotlight: '#3D3556',
    colorBorder: '#4C3F6E',
    colorBorderSecondary: '#4C3F6E',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#64748B',
    colorFill: 'rgba(139, 92, 246, 0.15)',
    colorFillSecondary: 'rgba(139, 92, 246, 0.1)',
    colorFillTertiary: 'rgba(139, 92, 246, 0.06)',
    colorFillQuaternary: 'rgba(139, 92, 246, 0.04)',
    colorSplit: 'rgba(139, 92, 246, 0.1)',
    colorLink: '#A78BFA',
    colorLinkHover: '#C4B5FD',
    colorLinkActive: '#8B5CF6',
  },
  algorithm: theme.darkAlgorithm,
  components: {
    Layout: {
      headerBg: 'rgba(30, 27, 46, 0.95)',
      siderBg: 'rgba(30, 27, 46, 0.95)',
      bodyBg: '#1E1B2E',
      headerPadding: '0 24px',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(139, 92, 246, 0.25)',
      darkItemHoverBg: 'rgba(139, 92, 246, 0.12)',
      darkItemSelectedColor: '#A78BFA',
      darkItemColor: '#CBD5E1',
      itemMarginInline: 8,
      itemPaddingInline: 12,
    },
    Card: {
      colorBgContainer: 'rgba(45, 38, 64, 0.6)',
      colorBorderSecondary: '#4C3F6E',
      paddingLG: 24,
      borderRadiusLG: 12,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#3D3556',
      headerColor: '#F8FAFC',
      rowHoverBg: 'rgba(139, 92, 246, 0.08)',
      borderColor: '#4C3F6E',
    },
    Input: {
      colorBgContainer: '#3D3556',
      colorBorder: '#4C3F6E',
      hoverBorderColor: '#8B5CF6',
      activeBorderColor: '#8B5CF6',
      activeShadow: '0 0 0 2px rgba(139, 92, 246, 0.2)',
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(139, 92, 246, 0.4)',
      defaultShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
    },
    Select: {
      colorBgContainer: '#3D3556',
      colorBorder: '#4C3F6E',
      optionSelectedBg: 'rgba(139, 92, 246, 0.2)',
    },
    Dropdown: {
      colorBgElevated: 'rgba(45, 38, 64, 0.98)',
      colorBgSpotlight: 'rgba(61, 53, 86, 0.98)',
    },
    Modal: {
      contentBg: '#2D2640',
      headerBg: '#2D2640',
      footerBg: '#2D2640',
      titleColor: '#F8FAFC',
      titleFontSize: 16,
      borderRadiusLG: 12,
    },
    Drawer: {
      colorBgElevated: '#2D2640',
    },
    Popover: {
      colorBgElevated: 'rgba(45, 38, 64, 0.98)',
    },
    Tooltip: {
      colorBgSpotlight: 'rgba(45, 38, 64, 0.98)',
    },
    Tabs: {
      inkBarColor: '#8B5CF6',
      itemSelectedColor: '#A78BFA',
      itemHoverColor: '#C4B5FD',
    },
    Badge: {
      colorBgContainer: '#8B5CF6',
    },
    Switch: {
      colorPrimary: '#8B5CF6',
      colorPrimaryHover: '#A78BFA',
    },
    Checkbox: {
      colorPrimary: '#8B5CF6',
      colorPrimaryHover: '#A78BFA',
    },
    Radio: {
      colorPrimary: '#8B5CF6',
      colorPrimaryHover: '#A78BFA',
    },
    Form: {
      labelColor: '#CBD5E1',
    },
    Message: {
      contentBg: '#3D3556',
    },
    Notification: {
      colorBgElevated: 'rgba(45, 38, 64, 0.98)',
    },
  },
}

// ============================================================
// 翠绿主题
// ============================================================
export const greenTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#10B981'),
    colorBgBase: '#0F1712',
    colorTextBase: '#F8FAFC',
    colorBgContainer: '#16221C',
    colorBgElevated: '#1A2E25',
    colorBgLayout: '#0F1712',
    colorBgSpotlight: '#1A2E25',
    colorBorder: '#2D3F35',
    colorBorderSecondary: '#2D3F35',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#64748B',
    colorFill: 'rgba(16, 185, 129, 0.15)',
    colorFillSecondary: 'rgba(16, 185, 129, 0.1)',
    colorFillTertiary: 'rgba(16, 185, 129, 0.06)',
    colorFillQuaternary: 'rgba(16, 185, 129, 0.04)',
    colorSplit: 'rgba(16, 185, 129, 0.1)',
    colorLink: '#34D399',
    colorLinkHover: '#6EE7B7',
    colorLinkActive: '#10B981',
  },
  algorithm: theme.darkAlgorithm,
  components: {
    Layout: {
      headerBg: 'rgba(22, 34, 28, 0.95)',
      siderBg: 'rgba(22, 34, 28, 0.95)',
      bodyBg: '#0F1712',
      headerPadding: '0 24px',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(16, 185, 129, 0.25)',
      darkItemHoverBg: 'rgba(16, 185, 129, 0.12)',
      darkItemSelectedColor: '#34D399',
      darkItemColor: '#CBD5E1',
      itemMarginInline: 8,
      itemPaddingInline: 12,
    },
    Card: {
      colorBgContainer: 'rgba(22, 34, 28, 0.6)',
      colorBorderSecondary: '#2D3F35',
      paddingLG: 24,
      borderRadiusLG: 12,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#1A2E25',
      headerColor: '#F8FAFC',
      rowHoverBg: 'rgba(16, 185, 129, 0.08)',
      borderColor: '#2D3F35',
    },
    Input: {
      colorBgContainer: '#1A2E25',
      colorBorder: '#2D3F35',
      hoverBorderColor: '#10B981',
      activeBorderColor: '#10B981',
      activeShadow: '0 0 0 2px rgba(16, 185, 129, 0.2)',
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(16, 185, 129, 0.4)',
      defaultShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
    },
    Select: {
      colorBgContainer: '#1A2E25',
      colorBorder: '#2D3F35',
      optionSelectedBg: 'rgba(16, 185, 129, 0.2)',
    },
    Dropdown: {
      colorBgElevated: 'rgba(22, 34, 28, 0.98)',
      colorBgSpotlight: 'rgba(26, 46, 37, 0.98)',
    },
    Modal: {
      contentBg: '#16221C',
      headerBg: '#16221C',
      footerBg: '#16221C',
      titleColor: '#F8FAFC',
      titleFontSize: 16,
      borderRadiusLG: 12,
    },
    Drawer: {
      colorBgElevated: '#16221C',
    },
    Popover: {
      colorBgElevated: 'rgba(22, 34, 28, 0.98)',
    },
    Tooltip: {
      colorBgSpotlight: 'rgba(22, 34, 28, 0.98)',
    },
    Tabs: {
      inkBarColor: '#10B981',
      itemSelectedColor: '#34D399',
      itemHoverColor: '#6EE7B7',
    },
    Badge: {
      colorBgContainer: '#10B981',
    },
    Switch: {
      colorPrimary: '#10B981',
      colorPrimaryHover: '#34D399',
    },
    Checkbox: {
      colorPrimary: '#10B981',
      colorPrimaryHover: '#34D399',
    },
    Radio: {
      colorPrimary: '#10B981',
      colorPrimaryHover: '#34D399',
    },
    Form: {
      labelColor: '#CBD5E1',
    },
    Message: {
      contentBg: '#1A2E25',
    },
    Notification: {
      colorBgElevated: 'rgba(22, 34, 28, 0.98)',
    },
  },
}

// ============================================================
// 海洋之心主题
// ============================================================
export const oceanTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#0EA5E9'),
    colorBgBase: '#0C1222',
    colorTextBase: '#F8FAFC',
    colorBgContainer: '#162035',
    colorBgElevated: '#1E2A42',
    colorBgLayout: '#0C1222',
    colorBgSpotlight: '#1E2A42',
    colorBorder: '#2D3F5C',
    colorBorderSecondary: '#2D3F5C',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#64748B',
    colorTextQuaternary: '#64748B',
    colorFill: 'rgba(14, 165, 233, 0.15)',
    colorFillSecondary: 'rgba(14, 165, 233, 0.1)',
    colorFillTertiary: 'rgba(14, 165, 233, 0.06)',
    colorFillQuaternary: 'rgba(14, 165, 233, 0.04)',
    colorSplit: 'rgba(14, 165, 233, 0.1)',
    colorLink: '#38BDF8',
    colorLinkHover: '#7DD3FC',
    colorLinkActive: '#0EA5E9',
  },
  algorithm: theme.darkAlgorithm,
  components: {
    Layout: {
      headerBg: 'rgba(22, 32, 53, 0.95)',
      siderBg: 'rgba(22, 32, 53, 0.95)',
      bodyBg: '#0C1222',
      headerPadding: '0 24px',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkSubMenuItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(14, 165, 233, 0.2)',
      darkItemHoverBg: 'rgba(14, 165, 233, 0.1)',
      darkItemSelectedColor: '#38BDF8',
      darkItemColor: '#CBD5E1',
      itemMarginInline: 8,
      itemPaddingInline: 12,
    },
    Card: {
      colorBgContainer: 'rgba(22, 32, 53, 0.6)',
      colorBorderSecondary: '#2D3F5C',
      paddingLG: 24,
      borderRadiusLG: 12,
    },
    Table: {
      colorBgContainer: 'transparent',
      headerBg: '#1E2A42',
      headerColor: '#F8FAFC',
      rowHoverBg: 'rgba(14, 165, 233, 0.08)',
      borderColor: '#2D3F5C',
    },
    Input: {
      colorBgContainer: '#1E2A42',
      colorBorder: '#2D3F5C',
      hoverBorderColor: '#0EA5E9',
      activeBorderColor: '#0EA5E9',
      activeShadow: '0 0 0 2px rgba(14, 165, 233, 0.2)',
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(14, 165, 233, 0.4)',
      defaultShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
    },
    Select: {
      colorBgContainer: '#1E2A42',
      colorBorder: '#2D3F5C',
      optionSelectedBg: 'rgba(14, 165, 233, 0.2)',
    },
    Dropdown: {
      colorBgElevated: 'rgba(22, 32, 53, 0.98)',
      colorBgSpotlight: 'rgba(30, 42, 66, 0.98)',
    },
    Modal: {
      contentBg: '#162035',
      headerBg: '#162035',
      footerBg: '#162035',
      titleColor: '#F8FAFC',
      titleFontSize: 16,
      borderRadiusLG: 12,
    },
    Drawer: {
      colorBgElevated: '#162035',
    },
    Popover: {
      colorBgElevated: 'rgba(22, 32, 53, 0.98)',
    },
    Tooltip: {
      colorBgSpotlight: 'rgba(22, 32, 53, 0.98)',
    },
    Tabs: {
      inkBarColor: '#0EA5E9',
      itemSelectedColor: '#38BDF8',
      itemHoverColor: '#7DD3FC',
    },
    Badge: {
      colorBgContainer: '#0EA5E9',
    },
    Switch: {
      colorPrimary: '#0EA5E9',
      colorPrimaryHover: '#38BDF8',
    },
    Checkbox: {
      colorPrimary: '#0EA5E9',
      colorPrimaryHover: '#38BDF8',
    },
    Radio: {
      colorPrimary: '#0EA5E9',
      colorPrimaryHover: '#38BDF8',
    },
    Form: {
      labelColor: '#CBD5E1',
    },
    Message: {
      contentBg: '#1E2A42',
    },
    Notification: {
      colorBgElevated: 'rgba(22, 32, 53, 0.98)',
    },
  },
}

// ============================================================
// 主题映射
// ============================================================
export const themeMap: Record<ThemeName, ThemeConfig> = {
  dark: darkTheme,
  light: lightTheme,
  purple: purpleTheme,
  green: greenTheme,
  ocean: oceanTheme,
}

export type { ThemeConfig }
