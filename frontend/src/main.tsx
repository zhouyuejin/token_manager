import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, theme, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { MessageProvider } from './components/MessageProvider'
import './index.css'

const darkTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#2563EB',
    colorBgContainer: '#111827',
    colorBgElevated: '#1E293B',
    colorBorder: '#334155',
    colorBorderSecondary: '#334155',
    colorText: '#F8FAFC',
    colorTextSecondary: '#CBD5E1',
    colorTextTertiary: '#94A3B8',
    colorTextQuaternary: '#64748B',
    borderRadius: 10,
    fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    colorSuccess: '#22C55E',
    colorWarning: '#F59E0B',
    colorError: '#DC2626',
    colorInfo: '#2563EB',
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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={darkTheme} locale={zhCN}>
      <AntApp>
        <MessageProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </MessageProvider>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
