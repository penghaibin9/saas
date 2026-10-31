// Website links only. No school identity, cookies, router, permissions or data are imported.
const env = import.meta.env || {}
export function sanitizeEntryUrl(value) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (/^https:\/\/[^\s]+$/.test(text)) return text
  return ''
}
export const TEACHER_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_TEACHER_LOGIN_URL || 'https://www.hnyueke.com/teacher/login')
export const STUDENT_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_STUDENT_LOGIN_URL || 'https://www.hnyueke.com/portal/login')
export const ENTERPRISE_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_ENTERPRISE_LOGIN_URL || 'https://www.hnyueke.com/enterprise/login')
export const HR_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_HR_LOGIN_URL || 'https://hr.hnyueke.com/')
export const TEACHER_H5_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_TEACHER_H5_LOGIN_URL || 'https://www.hnyueke.com/miniapp/#/pages/login/teacher/index')
export const STUDENT_H5_LOGIN_URL = sanitizeEntryUrl(env.VITE_PORTAL_STUDENT_H5_LOGIN_URL || 'https://www.hnyueke.com/miniapp/#/pages/login/student/index')
export const TEACHER_MINIPROGRAM_QR = sanitizeEntryUrl(env.VITE_PORTAL_TEACHER_MP_QR)
export const STUDENT_MINIPROGRAM_QR = sanitizeEntryUrl(env.VITE_PORTAL_STUDENT_MP_QR)
export const PRIVACY_URL = '/privacy'
export const TERMS_URL = '/terms'
export const COMPANY_NAME = '湖南跃科信息工程有限公司'
export const ICP_NUMBER = '湘ICP备2026031107号'
export const ICP_QUERY_URL = 'https://beian.miit.gov.cn/'
