import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import uni from '@dcloudio/vite-plugin-uni'

const envDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, envDir, 'VITE_')
  const apiBase = process.env.VITE_API_BASE_URL || env.VITE_API_BASE_URL
  if (command === 'build' && !String(apiBase || '').trim()) {
    throw new Error('移动端构建缺少后端地址：请配置 VITE_API_BASE_URL 后重新构建。')
  }
  return {
    envDir,
    plugins: [uni()],
    server: {
      proxy: {
        '/api': {
          target: process.env.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    }
  }
})
