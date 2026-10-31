import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { OFFICIAL_SEO_ROUTES } from './src/config/officialSalesPages.js'
const publicPaths = new Set(OFFICIAL_SEO_ROUTES.map(route => route.path))
export default defineConfig(({ isPreview }) => ({
  appType: isPreview ? 'mpa' : 'spa',
  plugins: [vue(), {
    name: 'website-static-routes',
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url, 'http://127.0.0.1')
        const route = url.pathname.replace(/\/+$/, '') || '/'
        if (route.startsWith('/api/') || route === '/news' || route.startsWith('/news/')) return next()
        if (publicPaths.has(route)) req.url = `${route === '/' ? '' : route}/index.html${url.search}`
        else if (route === '/manage' || route.startsWith('/manage/')) req.url = `/manage/index.html${url.search}`
        else if (!/\.[a-z0-9]+$/i.test(route)) {
          res.statusCode = 404
          res.setHeader('Content-Type', 'text/html; charset=utf-8')
          return res.end(readFileSync(new URL('./dist/404.html', import.meta.url)))
        }
        next()
      })
    }
  }],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { proxy: { '/api': 'http://127.0.0.1:8012', '/news': 'http://127.0.0.1:8012' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:8012', '/news': 'http://127.0.0.1:8012' } },
  build: { target: 'es2022', manifest: true, assetsDir: 'website-assets' }
}))
