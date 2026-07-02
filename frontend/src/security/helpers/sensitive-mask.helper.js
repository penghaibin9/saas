/**
 * sensitive mask helper — 敏感数据脱敏（总册 §3 分级 + §9 脱敏规范）。
 * 复用 utils/sensitive.js 已有能力；身份证/姓名/地址按安全总册口径在此收严：
 *   身份证：前 6 + **** + 后 4（utils 旧口径为前 3，安全域以本文件为准）
 *   手机号：前 3 + **** + 后 4（与 utils 一致，直接复用）
 *   姓名：姓 + *；地址：保留区/县级 + ****
 * 禁止任何函数 console 输出入参明文。
 */
import { maskPhone as basePhone } from '@/utils/sensitive'
import { SENSITIVE_LEVEL } from '../constants/security.constants'

/** 身份证：前 6 + **** + 后 4 */
export function maskIdCard(value) {
  const v = String(value ?? '')
  if (!v) return ''
  if (v.length < 11) return '******'
  return v.slice(0, 6) + '****' + v.slice(-4)
}

/** 手机号：前 3 + **** + 后 4（复用 utils 实现） */
export function maskPhone(value) {
  return basePhone(value)
}

/** 姓名：姓 + * */
export function maskName(value) {
  const v = String(value ?? '')
  if (!v) return ''
  return v.slice(0, 1) + '*'
}

/** 家庭住址：保留到区/县 + **** */
export function maskAddress(value) {
  const v = String(value ?? '')
  if (!v) return ''
  const m = v.match(/^(.*?(?:省|自治区|市))??(.*?市)?(.*?(?:区|县|旗))?/)
  const prefix = ((m && m[1]) || '') + ((m && m[2]) || '') + ((m && m[3]) || '')
  return (prefix || v.slice(0, 6)) + '****'
}

/** 银行卡：前 4 + ***** + 后 4 */
export function maskBankCard(value) {
  const v = String(value ?? '').replace(/\s/g, '')
  if (!v) return ''
  if (v.length < 9) return '*****'
  return v.slice(0, 4) + '*****' + v.slice(-4)
}

/** 薪资：转区间；无法解析时返回 **** */
export function maskSalary(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return '****'
  const lower = Math.floor(n / 1000) * 1000
  return `${lower}-${lower + 1000} 元`
}

/** 邮箱：首字符 + *** + @domain */
export function maskEmail(value) {
  const v = String(value ?? '')
  const at = v.indexOf('@')
  if (at <= 0) return v ? '***' : ''
  return v.slice(0, 1) + '***' + v.slice(at)
}

/**
 * 按敏感级别脱敏：
 * PUBLIC → 原样；INTERNAL → 原样（仅校内页面展示）；
 * SENSITIVE → 按 kind 脱敏；SECRET → 恒定 '******'（禁止明文出现）。
 */
export function maskByLevel(value, level, kind = 'generic') {
  if (level === SENSITIVE_LEVEL.SECRET) return '******'
  if (level === SENSITIVE_LEVEL.SENSITIVE) {
    switch (kind) {
      case 'idCard':
        return maskIdCard(value)
      case 'phone':
        return maskPhone(value)
      case 'name':
        return maskName(value)
      case 'address':
        return maskAddress(value)
      case 'bankCard':
        return maskBankCard(value)
      case 'salary':
        return maskSalary(value)
      case 'email':
        return maskEmail(value)
      default:
        return '****'
    }
  }
  return String(value ?? '')
}

/**
 * 学生记录整体脱敏：返回新对象，常见敏感字段按规则处理，原对象不变。
 * 供列表/导出前统一调用。
 */
export function maskStudentRecord(record = {}) {
  const out = { ...record }
  if (out.idCard) out.idCard = maskIdCard(out.idCard)
  if (out.idcard) out.idcard = maskIdCard(out.idcard)
  if (out.phone) out.phone = maskPhone(out.phone)
  if (out.mobile) out.mobile = maskPhone(out.mobile)
  if (out.guardianPhone) out.guardianPhone = maskPhone(out.guardianPhone)
  if (out.name) out.name = maskName(out.name)
  if (out.address) out.address = maskAddress(out.address)
  if (out.homeAddress) out.homeAddress = maskAddress(out.homeAddress)
  if (out.bankCard) out.bankCard = maskBankCard(out.bankCard)
  if (out.salary !== undefined) out.salary = maskSalary(out.salary)
  if (out.email) out.email = maskEmail(out.email)
  if (out.password) out.password = '******'
  return out
}
