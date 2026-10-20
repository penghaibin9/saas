/**
 * SECURITY-P0 · 敏感字段统一定义（字段名 → 脱敏类别 kind + 数据分级 level）。
 * 唯一事实来源：新增敏感字段先登记在此，再谈展示/导出。
 * 依据：docs/security/02-敏感字段脱敏规则.md、00-等保三级安全基线总册 §3。
 * 声明：前端脱敏只是展示层防护，不替代后端权限校验与存储加密。
 */
import { SENSITIVE_LEVEL } from '@/security/constants/security.constants'

/**
 * 字段注册表。kind 决定脱敏算法（见 mask.js / security/helpers/sensitive-mask.helper.js），
 * level 决定默认展示策略（SENSITIVE=默认脱敏；SECRET=禁止前端明文）。
 */
export const SENSITIVE_FIELDS = Object.freeze({
  /* 证件 */
  idCard: { kind: 'idCard', level: SENSITIVE_LEVEL.SENSITIVE },
  id_card: { kind: 'idCard', level: SENSITIVE_LEVEL.SENSITIVE },
  idcard: { kind: 'idCard', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 电话 */
  phone: { kind: 'phone', level: SENSITIVE_LEVEL.SENSITIVE },
  mobile: { kind: 'phone', level: SENSITIVE_LEVEL.SENSITIVE },
  parentPhone: { kind: 'phone', level: SENSITIVE_LEVEL.SENSITIVE },
  guardianPhone: { kind: 'phone', level: SENSITIVE_LEVEL.SENSITIVE },
  emergencyPhone: { kind: 'phone', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 地址 */
  address: { kind: 'address', level: SENSITIVE_LEVEL.SENSITIVE },
  homeAddress: { kind: 'address', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 金融 */
  bankCard: { kind: 'bankCard', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 联络 */
  email: { kind: 'email', level: SENSITIVE_LEVEL.SENSITIVE },
  familyContact: { kind: 'name', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 文件地址：防止直链外泄（展示时截断，下载走 download.guard） */
  fileUrl: { kind: 'url', level: SENSITIVE_LEVEL.SENSITIVE },
  attachmentUrl: { kind: 'url', level: SENSITIVE_LEVEL.SENSITIVE },
  /* 永不明文 */
  password: { kind: 'secret', level: SENSITIVE_LEVEL.SECRET },
  token: { kind: 'secret', level: SENSITIVE_LEVEL.SECRET },
  /* 学号：默认不全脱敏（业务需要可辨识），仅登记级别 */
  studentNo: { kind: 'studentNo', level: SENSITIVE_LEVEL.INTERNAL },
  /* 姓名：默认不强制全脱敏，按角色/场景决定（见 role-mask.js） */
  name: { kind: 'name', level: SENSITIVE_LEVEL.INTERNAL }
})

/** 字段是否登记为敏感字段 */
export function isSensitiveField(fieldName) {
  return Object.prototype.hasOwnProperty.call(SENSITIVE_FIELDS, fieldName)
}

/** 取字段脱敏类别；未登记返回 '' */
export function getFieldKind(fieldName) {
  const def = SENSITIVE_FIELDS[fieldName]
  return def ? def.kind : ''
}

/** 取字段分级；未登记返回 PUBLIC */
export function getFieldLevel(fieldName) {
  const def = SENSITIVE_FIELDS[fieldName]
  return def ? def.level : SENSITIVE_LEVEL.PUBLIC
}
