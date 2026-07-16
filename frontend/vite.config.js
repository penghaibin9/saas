import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// UI-P1.5 最小工程配置：仅 Vue 插件 + @ alias，不引入任何 UI 框架
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/@antv/g2')) return 'vendor-g2'
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/dayjs') || id.includes('node_modules/@popperjs') || id.includes('node_modules/@element-plus')) return 'vendor-element'
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/')) return 'vendor-vue'
          if (id.includes('node_modules/vue-router')) return 'vendor-vue-router'
          if (id.includes('node_modules/pinia')) return 'vendor-pinia'
        }
      }
    }
  },
  server: {
    port: 5173,
    host: true,
    // 开发态 API 走同源 /api → 后端，避免端口变化（5174/5175）触发 CORS 拦截导致登录失败
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
