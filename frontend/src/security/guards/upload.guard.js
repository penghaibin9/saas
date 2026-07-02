/**
 * upload guard — 上传白名单/大小控制（总册 §9）。
 * 白名单：pdf/doc/docx/jpg/jpeg/png/zip/rar/xlsx/pptx；单文件 ≤ 50MB；黑名单双保险。
 * 前端为第一道闸，真实校验（魔数/杀毒/重命名）在后端文件中心。
 */
import { UPLOAD_POLICY } from '../constants/security.constants'
import { canClickSecurityButton } from './menu.guard'
import { isAuthenticated } from '../auth/auth.context'

/** 当前上传策略（预留按模块差异化） */
export function getUploadPolicy() {
  return {
    allowedExtensions: [...UPLOAD_POLICY.ALLOWED_EXTENSIONS],
    maxFileSizeBytes: UPLOAD_POLICY.MAX_FILE_SIZE_BYTES,
    maxFileSizeText: '50MB'
  }
}

/** 是否允许发起上传 */
export function canUpload(permissionKey = '') {
  if (!isAuthenticated()) return false
  if (permissionKey && !canClickSecurityButton(permissionKey)) return false
  return true
}

/**
 * 单文件校验。
 * @param {File|{name:string,size:number}} file
 * @returns {{ valid:boolean, reason:string }}
 */
export function validateUploadFile(file) {
  if (!file || !file.name) return { valid: false, reason: '未选择文件' }
  const ext = String(file.name).split('.').pop().toLowerCase()
  if (UPLOAD_POLICY.BLOCKED_EXTENSIONS.includes(ext)) {
    return { valid: false, reason: `不允许上传 .${ext} 类型文件` }
  }
  if (!UPLOAD_POLICY.ALLOWED_EXTENSIONS.includes(ext)) {
    return {
      valid: false,
      reason: `仅支持 ${UPLOAD_POLICY.ALLOWED_EXTENSIONS.join('/')} 类型`
    }
  }
  if (Number(file.size) > UPLOAD_POLICY.MAX_FILE_SIZE_BYTES) {
    return { valid: false, reason: '文件超过 50MB，请压缩后重新上传' }
  }
  return { valid: true, reason: '' }
}
