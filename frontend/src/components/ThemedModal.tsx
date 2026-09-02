import React from 'react'
import { Modal as AntModal, ModalProps } from 'antd'
import { useThemeToken } from '@/theme/useThemeToken'

/**
 * 主题感知的 Modal 组件
 * 自动适配当前主题颜色，无需手动配置
 */
export const ThemedModal: React.FC<ModalProps> = ({ 
  children, 
  styles,
  className,
  ...props 
}) => {
  const { token, isDark } = useThemeToken()
  
  // 自动适配主题的样式
  const themedStyles = {
    header: {
      color: token.colorText,
      ...styles?.header,
    },
    content: {
      background: token.colorBgElevated,
      color: token.colorText,
      ...styles?.content,
    },
    wrapper: {
      background: token.colorBgElevated,
      ...styles?.wrapper,
    },
    mask: {
      backgroundColor: isDark 
        ? 'rgba(0, 0, 0, 0.45)' 
        : 'rgba(0, 0, 0, 0.45)',
      ...styles?.mask,
    },
    footer: {
      background: token.colorBgElevated,
      ...styles?.footer,
    },
  }

  return (
    <AntModal 
      {...props} 
      styles={themedStyles}
      className={className}
    >
      {children}
    </AntModal>
  )
}

export default ThemedModal
