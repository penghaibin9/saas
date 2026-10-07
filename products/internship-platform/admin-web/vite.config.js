import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
  },
  server: {
    port: Number(process.env.PORT || 5176),
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) return 'vendor-element'
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/')) return 'vendor-vue'
          if (id.includes('node_modules/vue-router')) return 'vendor-vue-router'
          if (id.includes('node_modules/pinia')) return 'vendor-pinia'
        }
      }
    }
  }
})
