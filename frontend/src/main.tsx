import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import App from './App'
import { MessageProvider } from './components/MessageProvider'
import { ThemeProvider } from './theme'
import './index.css'

// 后端 naive datetime 实际是 UTC 时间，注册插件后用 dayjs.utc(val).local() 解析
dayjs.extend(utc)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <MessageProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </MessageProvider>
    </ThemeProvider>
  </React.StrictMode>,
)
