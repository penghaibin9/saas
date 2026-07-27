import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

const root = fileURLToPath(new URL('.', import.meta.url))

// base 与 API 地址均可配置，便于部署到 /portal/ 或正式域名子路径。
// - VITE_BASE：静态资源与 history base（默认 /portal/）
// - VITE_API_BASE_URL：后端源地址（默认同源，经 Nginx /api/ 反代）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    base: env.VITE_BASE || '/portal/',
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(root, 'src'),
      },
    },
    server: { port: 5199 }
  }
})
