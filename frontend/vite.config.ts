import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    conditions: ['module', 'browser'],
  },
  optimizeDeps: {
    include: ['dayjs'],
  },
  server: {
    port: 3002,
    proxy: {
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws/': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
    fs: {
      // 允许访问上级目录的文件
      allow: ['..'],
    },
  },
})
