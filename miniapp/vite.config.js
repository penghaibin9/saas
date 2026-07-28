import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// uni-app + Vue3 独立工程配置。仅服务小程序端，不影响 PC frontend。
export default defineConfig({
  resolve: {
    alias: [
      {
        find: '@/services/request',
        replacement: fileURLToPath(new URL('./src/services/requestCompat.js', import.meta.url))
      }
    ]
  },
  plugins: [uni()]
})
