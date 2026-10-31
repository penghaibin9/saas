import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { cpSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

// UI-P1.5 最小工程配置：仅 Vue 插件 + @ alias，不引入任何 UI 框架
export default defineConfig({
  plugins: [vue(), {
    name: 'school-public-help-only',
    writeBundle(options) {
      // 官网图片与站点地图由独立 website 工程发布；学校仅保留公共帮助资源。
      const help = fileURLToPath(new URL('./public/help', import.meta.url))
      if (existsSync(help)) cpSync(help, resolve(options.dir, 'help'), { recursive: true })
    }
  }],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    copyPublicDir: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
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
    // 开发态 API 走同源 /api → 后端，避免端口变化（5174/5175）触发 CORS 拦截导致登录失败。
    // 并行开发（多窗口/多 worktree）时用 VITE_PROXY_TARGET 指到自己那份后端，免得几个人抢 8000；
    // 不设该变量时行为与以往完全一致。
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
