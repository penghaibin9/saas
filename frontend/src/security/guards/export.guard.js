/**
 * export guard — 导出三档控制（台账/加密档案/脱敏外发，总册 §9）。
 * 所有导出必须：权限校验 → 行数限制 → 生成审计事件。真实拦截在后端，前端为第一道闸。
 */
import { EXPORT_POLICY } from '../constants/security.constants'
import { canClickSecurityButton, getCurrentPermissionContext } from './menu.guard'
import { createExportAuditEvent as buildExportEvent } from '../helpers/audit-event.helper'
import { getScopeDescription } from './data-scope.guard'

/** 当前导出类型的行数上限（预留按套餐/角色差异化，当前统一默认值） */
export function getExportLimit(exportType = EXPORT_POLICY.TYPES.LIST) {
  void exportType
  return EXPORT_POLICY.MAX_ROWS_DEFAULT
}

/** 是否具备该导出类型的权限 */
export function canExport(exportType = EXPORT_POLICY.TYPES.LIST) {
  const permKey = EXPORT_POLICY.REQUIRED_PERMISSION[exportType]
  if (!permKey) return false
  return canClickSecurityButton(permKey)
}

/**
 * 导出请求校验。
 * @param {object} req { exportType, rowCount, purpose }
 * @returns {{ allowed:boolean, reason:string }}
 */
export function validateExportRequest(req = {}) {
  const exportType = req.exportType || EXPORT_POLICY.TYPES.LIST
  if (!Object.values(EXPORT_POLICY.TYPES).includes(exportType)) {
    return { allowed: false, reason: '未知的导出类型' }
  }
  if (!canExport(exportType)) {
    return { allowed: false, reason: '当前账号无此导出权限' }
  }
  const limit = getExportLimit(exportType)
  if (Number(req.rowCount) > limit) {
    return { allowed: false, reason: `导出行数超过上限（${limit} 行），请缩小范围或走异步导出` }
  }
  if (exportType === EXPORT_POLICY.TYPES.DESENSITIZED && !req.purpose) {
    return { allowed: false, reason: '脱敏外发导出必须填写用途' }
  }
  if (getCurrentPermissionContext() == null) {
    return { allowed: false, reason: '权限上下文未加载' }
  }
  return { allowed: true, reason: '' }
}

/** 生成导出审计事件（调用方随后 sendAuditEventToBackend） */
export function createExportAuditEvent(req = {}) {
  const { label } = getScopeDescription()
  return buildExportEvent(req.exportType || EXPORT_POLICY.TYPES.LIST, label, Number(req.rowCount) || 0, {
    purpose: req.purpose || '',
    module: req.module || ''
  })
}
