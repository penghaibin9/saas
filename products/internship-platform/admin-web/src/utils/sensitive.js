/**
 * 敏感字段脱敏工具
 * 依据：V1.0 §10 权限与脱敏 UI 规则
 * 所有敏感字段展示必须经过本工具，禁止页面各自实现脱敏。
 */

/** 手机号：135****6867 */
export function maskPhone(value) {
  const v = String(value ?? '')
  if (v.length < 7) return v ? '***' : ''
  return v.slice(0, 3) + '****' + v.slice(-4)
}

/** 身份证：430***********1234 */
export function maskIdCard(value) {
  const v = String(value ?? '')
  if (v.length < 8) return v ? '***' : ''
  return v.slice(0, 3) + '*'.repeat(Math.max(v.length - 7, 4)) + v.slice(-4)
}

/** 姓名：对外展示编码（如 S2026-000001），无编码时保留姓氏 */
export function maskName(value, code) {
  if (code) return String(code)
  const v = String(value ?? '')
  if (!v) return ''
  return v.slice(0, 1) + '*'.repeat(Math.max(v.length - 1, 1))
}

/** 地址：保留省市，后续用 ****** */
export function maskAddress(value) {
  const v = String(value ?? '')
  if (!v) return ''
  const m = v.match(/^(.+?(?:省|自治区|市))?(.+?市)?/)
  const prefix = ((m && m[1]) || '') + ((m && m[2]) || '')
  return (prefix || v.slice(0, 6)) + '******'
}

/** 通用：保留首尾各 n 位 */
export function maskGeneric(value, keepStart = 1, keepEnd = 1) {
  const v = String(value ?? '')
  if (v.length <= keepStart + keepEnd) return v ? '***' : ''
  return v.slice(0, keepStart) + '****' + v.slice(v.length - keepEnd)
}

export function maskByType(type, value, code) {
  switch (type) {
    case 'phone':
      return maskPhone(value)
    case 'idcard':
      return maskIdCard(value)
    case 'name':
      return maskName(value, code)
    case 'address':
      return maskAddress(value)
    default:
      return maskGeneric(value)
  }
}
