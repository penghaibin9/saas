/**
 * 移动端敏感字段脱敏工具（与 frontend/src/utils/sensitive.js 保持同一规则）
 * 依据：V1.0 §10 权限与脱敏 UI 规则
 */
export function maskPhone(value) {
  const v = String(value ?? '')
  if (v.length < 7) return v ? '***' : ''
  return v.slice(0, 3) + '****' + v.slice(-4)
}

export function maskIdCard(value) {
  const v = String(value ?? '')
  if (v.length < 8) return v ? '***' : ''
  return v.slice(0, 3) + '*'.repeat(Math.max(v.length - 7, 4)) + v.slice(-4)
}

export function maskName(value, code) {
  if (code) return String(code)
  const v = String(value ?? '')
  if (!v) return ''
  return v.slice(0, 1) + '*'.repeat(Math.max(v.length - 1, 1))
}

export function maskAddress(value) {
  const v = String(value ?? '')
  if (!v) return ''
  const m = v.match(/^(.+?(?:省|自治区|市))?(.+?市)?/)
  const prefix = ((m && m[1]) || '') + ((m && m[2]) || '')
  return (prefix || v.slice(0, 6)) + '******'
}

export function maskGeneric(value, keepStart = 1, keepEnd = 1) {
  const v = String(value ?? '')
  if (v.length <= keepStart + keepEnd) return v ? '***' : ''
  return v.slice(0, keepStart) + '****' + v.slice(v.length - keepEnd)
}

export function maskByType(type, value, code) {
  switch (type) {
    case 'phone': return maskPhone(value)
    case 'idcard': return maskIdCard(value)
    case 'name': return maskName(value, code)
    case 'address': return maskAddress(value)
    default: return maskGeneric(value)
  }
}
