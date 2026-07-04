/**
 * P2 · 真实后端接入配置。
 * 取值优先级：
 *   1) VITE_API_BASE_URL（显式配置，只填「源」如 http://服务器IP，勿带 /api，前缀 /api/v1 会自动拼接）
 *   2) 开发模式（import.meta.env.DEV）→ http://localhost:8000
 *   3) 生产构建未配置 → 同源（''），最终请求形如 /api/v1/... ，由 Nginx 的 location /api/ 反代到后端
 * localStorage.useRealApi='false' 可一键回退纯 mock。
 */
export const API_BASE_URL = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return '' // 生产同源：/api/v1 由 Nginx 反代到后端，无需把服务器 IP 打进构建
})()

export const API_PREFIX = '/api/v1'

export function realApiEnabled() {
  try {
    return window.localStorage.getItem('useRealApi') !== 'false'
  } catch {
    return true
  }
}
