import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// uni-app + Vue3 独立工程配置。仅服务小程序端，不影响 PC frontend。
export default defineConfig({
  plugins: [uni()]
})
