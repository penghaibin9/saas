/**
 * SECURITY-P0 · 脱敏算法统一出口。
 * 复用既有实现（utils/sensitive.js、security/helpers/sensitive-mask.helper.js），
 * 本文件只做补齐与统一命名，禁止页面各自手写脱敏。
 * 输出样例：
 *   手机号     138****5678
 *   身份证     430***********1234
 *   银行卡     6222 **** **** 1234
 *   邮箱       p***@example.com
 *   家庭住址   湖南省长沙市******
 *   学号       默认不脱敏（可按规则保留前后段）
 */
import { maskPhone, maskIdCard, maskName, maskAddress, maskGeneric } from '@/utils/sensitive'
import { maskBankCard as maskBankCardCompact, maskEmail, maskSalary } from '@/security/helpers/sensitive-mask.helper'
import { SENSITIVE_LEVEL } from '@/security/constants/security.constants'
import { SENSITIVE_FIELDS } from './sensitive-fields'

export { maskPhone, maskIdCard, maskName, maskAddress, maskGeneric, maskEmail, maskSalary }

/** 银行卡（分组样式）：6222 **** **** 1234 */
export function maskBankCard(value) {
  const v = String(value ?? '').replace(/\s/g, '')
  if (!v) return ''
  if (v.length < 9) return '****'
  return v.slice(0, 4) + ' **** **** ' + v.slice(-4)
}

export { maskBankCardCompact }

/** 紧急联系人电话：与手机号同规则 */
export function maskEmergencyPhone(value) {
  return maskPhone(value)
}

/** 学号：默认不脱敏；needMask=true 时保留前 4 后 2 */
export function maskStudentNo(value, needMask = false) {
  const v = String(value ?? '')
  if (!needMask) return v
  return maskGeneric(v, 4, 2)
}

/** 文件/附件 URL：只展示文件名，隐藏路径与签名参数（下载仍走 download.guard） */
export function maskUrl(value) {
  const v = String(value ?? '')
  if (!v) return ''
  const clean = v.split('?')[0]
  const name = clean.slice(clean.lastIndexOf('/') + 1)
  return name ? '…/' + name : '…'
}

/** 按 kind 统一脱敏 */
export function maskByKind(value, kind) {
  switch (kind) {
    case 'phone':
      return maskPhone(value)
    case 'idCard':
      return maskIdCard(value)
    case 'bankCard':
      return maskBankCard(value)
    case 'email':
      return maskEmail(value)
    case 'address':
      return maskAddress(value)
    case 'name':
      return maskName(value)
    case 'salary':
      return maskSalary(value)
    case 'url':
      return maskUrl(value)
    case 'studentNo':
      return maskStudentNo(value)
    case 'secret':
      return '******'
    default:
      return maskGeneric(value)
  }
}

/**
 * 记录级脱敏：按 SENSITIVE_FIELDS 注册表处理所有登记字段，返回新对象。
 * 列表展示 / 导出预处理前统一调用；SECRET 恒定 ******；INTERNAL 默认保留。
 */
export function maskRecordByFields(record = {}) {
  const out = { ...record }
  for (const [field, def] of Object.entries(SENSITIVE_FIELDS)) {
    if (out[field] === undefined || out[field] === null || out[field] === '') continue
    if (def.level === SENSITIVE_LEVEL.SECRET) {
      out[field] = '******'
    } else if (def.level === SENSITIVE_LEVEL.SENSITIVE) {
      out[field] = maskByKind(out[field], def.kind)
    }
    /* INTERNAL / PUBLIC 保留原值（姓名、学号默认不强制全脱敏） */
  }
  return out
}
