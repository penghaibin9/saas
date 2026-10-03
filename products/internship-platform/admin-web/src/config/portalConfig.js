const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}

export function sanitizeEntryUrl(value) {
  const url = typeof value === 'string' ? value.trim() : ''
  if (!url || url.startsWith('//')) return ''
  if (url.startsWith('/')) return url
  if (/^https?:\/\/[^\s]+$/i.test(url)) return url
  return ''
}

export const ENTERPRISE_LOGIN_URL = sanitizeEntryUrl(
  env.VITE_INTERNSHIP_ENTERPRISE_LOGIN_URL ||
  env.VITE_PORTAL_ENTERPRISE_LOGIN_URL ||
  '/enterprise/login'
)
