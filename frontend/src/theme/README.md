# 主题换肤实现指南

## 概述

本项目使用 Ant Design v5 的 Design Token 系统实现主题换肤，支持 5 种主题：
- 🌙 深色主题 (dark)
- ☀️ 亮色主题 (light)  
- 🟣 紫罗兰主题 (purple)
- 🌿 翠绿主题 (green)
- 🌊 海洋之心主题 (ocean)

## 核心实现

### 1. 主题配置 (`themes.ts`)

使用 Ant Design 的 `ThemeConfig` 配置每个主题的：
- **Seed Token**: 基础颜色令牌 (primary, borderRadius, fontFamily 等)
- **Map Token**: 映射令牌 (基于 Seed Token 计算)
- **Component Token**: 组件级令牌 (Modal、Table、Input 等的具体样式)

### 2. 主题 Provider (`ThemeContext.tsx`)

通过 `ConfigProvider` 组件将主题应用到所有 Ant Design 组件。

### 3. 自定义组件主题支持 (`useThemeToken.ts`)

提供 Hook 供自定义组件获取当前主题颜色：

```tsx
import { useThemeToken } from '@/theme'

const MyComponent = () => {
  const { token, isDark } = useThemeToken()
  
  return (
    <div style={{
      background: token.colorBgContainer,
      color: token.colorText,
      borderColor: token.colorBorder,
    }}>
      内容
    </div>
  )
}
```

## 使用方法

### 在 Ant Design 组件中使用

Ant Design 组件会自动应用主题，无需额外配置：

```tsx
<Button type="primary">按钮</Button>  // 自动使用主题色
<Input />  // 自动应用主题背景和边框
<Modal />  // 自动应用主题背景
<Table />  // 自动应用主题样式
```

### 在自定义组件中使用主题色

```tsx
import { useThemeToken } from '@/theme'

const Card = ({ children }) => {
  const { token } = useThemeToken()
  
  return (
    <div style={{
      background: token.colorBgContainer,
      border: `1px solid ${token.colorBorder}`,
      borderRadius: token.borderRadius,
      padding: token.paddingLG,
    }}>
      {children}
    </div>
  )
}
```

### 常用 Token 列表

| Token | 用途 |
|-------|------|
| `token.colorBgBase` | 页面背景色 |
| `token.colorBgContainer` | 容器背景色 |
| `token.colorBgElevated` | 浮层背景色 (Modal, Dropdown 等) |
| `token.colorText` | 主文字色 |
| `token.colorTextSecondary` | 次级文字色 |
| `token.colorTextTertiary` | 第三级文字色 |
| `token.colorBorder` | 边框色 |
| `token.colorBorderSecondary` | 次级边框色 |
| `token.colorPrimary` | 主题色 |
| `token.borderRadius` | 圆角大小 |
| `token.fontSize` | 基础字号 |

### 使用 isDark 判断主题类型

```tsx
const { isDark, token } = useThemeToken()

const background = isDark 
  ? 'rgba(17, 24, 39, 0.6)'  // 深色主题的半透明背景
  : 'rgba(255, 255, 255, 0.8)'  // 亮色主题的半透明背景
```

## 新增主题

在 `themes.ts` 中添加新的主题配置：

```tsx
export const myTheme: ThemeConfig = {
  token: {
    ...getBaseToken('#FF6B6B'),
    colorBgBase: '#FFF5F5',
    colorTextBase: '#2D3748',
    // ... 其他 token
  },
  algorithm: theme.defaultAlgorithm,  // 或 theme.darkAlgorithm
  components: {
    // 组件级配置
  }
}

// 添加到主题映射
export const themeMap: Record<ThemeName, ThemeConfig> = {
  // ... 其他主题
  myTheme,
}
```

然后在 `themeOptions` 中添加选项。

## 故障排除

### 问题：Modal 背景色不正确

确保：
1. `themes.ts` 中 Modal 的 `contentBg`、`headerBg`、`footerBg` 已配置
2. 没有在 Modal 上使用硬编码的 style

### 问题：文字颜色不正确

确保使用 `token.colorText` 而不是硬编码的颜色值。

### 问题：组件没有响应主题变化

检查是否在组件中正确使用了 `useThemeToken` hook。
