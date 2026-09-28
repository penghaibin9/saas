/**
 * download guard — 文件下载控制（总册 §9：签名 URL + 敏感下载审计）。
 * 业务表只存 file_id；下载必须使用短期签名 URL（真实签发在后端/文件中心，此处校验形态）。
 */
import { canClickSecurityButton } from './menu.guard'
import { isAuthenticated } from '../auth/auth.context'
import { createDownloadAuditEvent as buildDownloadEvent } from '../helpers/audit-event.helper'

/** 是否允许下载（登录 + 可选按钮权限） */
export function canDownload(permissionKey = '') {
  if (!isAuthenticated()) return false
  if (permissionKey && !canClickSecurityButton(permissionKey)) return false
  return true
}

/**
 * 校验签名 URL 形态（mock 规则）：
 * 必须 https 或同源相对路径；必须携带 sign 与 expires 参数；expires 未过期。
 * 真实校验在服务端，前端仅防呆。
 */
export function validateSignedUrl(url = '') {
  const v = String(url)
  if (!v) return { valid: false, reason: '下载地址为空' }
  if (v.startsWith('http://')) return { valid: false, reason: '禁止使用非加密链接下载' }
  let parsed
  try {
    parsed = new URL(v, 'https://placeholder.local')
  } catch {
    return { valid: false, reason: '下载地址格式非法' }
  }
  const sign = parsed.searchParams.get('sign')
  const expires = Number(parsed.searchParams.get('expires'))
  if (!sign) return { valid: false, reason: '缺少签名参数' }
  if (!expires || Number.isNaN(expires)) return { valid: false, reason: '缺少有效期参数' }
  if (expires * 1000 < Date.now()) return { valid: false, reason: '签名已过期，请重新获取下载链接' }
  return { valid: true, reason: '' }
}

/** 生成下载审计事件 */
export function createDownloadAuditEvent(file = {}) {
  return buildDownloadEvent(file.fileId || '', file.fileName || '', {
    module: file.module || '',
    sensitive: !!file.sensitive
  })
}
