/** P2 · 真实后端接入配置。VITE_API_BASE_URL 可覆盖；localStorage.useRealApi='false' 可一键回退纯 mock。 */
export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  'http://localhost:8000'

export const API_PREFIX = '/api/v1'

export function realApiEnabled() {
  try {
    return window.localStorage.getItem('useRealApi') !== 'false'
  } catch {
    return true
  }
}
