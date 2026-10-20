/**
 * CSRF helper（预留，总册 §4/§7）。
 * 规则：POST/PUT/PATCH/DELETE 需携带 CSRF Token；GET 不需要。
 * 当前 token 为前端 mock 值；真实阶段由后端下发（Cookie double-submit 或 meta 注入），本文件签名不变。
 */
import { CSRF_PROTECTED_METHODS, CSRF_HEADER_NAME } from '../constants/security.constants'

let mockToken = ''

/** 取 CSRF Token（mock：懒生成一个会话内固定值；真实阶段改读 cookie/meta） */
export function getCsrfToken() {
  if (!mockToken) {
    mockToken = 'mock-csrf-' + Math.random().toString(36).slice(2, 10)
  }
  return mockToken
}

/** 该方法是否需要 CSRF 保护 */
export function validateCsrfRequired(method = 'GET') {
  return CSRF_PROTECTED_METHODS.includes(String(method).toUpperCase())
}

/** 在 headers 上附加 CSRF 头（仅保护方法附加），返回同一 headers 对象 */
export function attachCsrfHeader(headers = {}, method = 'GET') {
  if (validateCsrfRequired(method)) {
    headers[CSRF_HEADER_NAME] = getCsrfToken()
  }
  return headers
}
