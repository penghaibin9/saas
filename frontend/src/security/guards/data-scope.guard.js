/**
 * data scope guard — 行级数据范围（ALL/SCHOOL/COLLEGE/CLASS/SELF/ASSIGNED）。
 * 复用 workflow guards.checkDataScope 单一实现；前端过滤仅为体验层，真实控制在后端复核。
 */
import { checkDataScope } from '@/modules/workflow/guards/workflow.guards'
import { DATA_SCOPE_LABELS } from '@/modules/workflow/constants/workflow.constants'
import { getCurrentPermissionContext, resolveSecurityDataScope } from './menu.guard'

/** 单条记录是否在当前数据范围内 */
export function checkRecordScope(record = {}) {
  const ctx = getCurrentPermissionContext()
  return checkDataScope(record, ctx)
}

/** 列表按数据范围过滤（返回新数组） */
export function filterRecordsByScope(records = []) {
  return records.filter((r) => checkRecordScope(r).allowed)
}

/** 当前数据范围的人类可读描述（顶部栏/导出确认用） */
export function getScopeDescription() {
  const { scope, label } = resolveSecurityDataScope()
  return { scope, label: DATA_SCOPE_LABELS[scope] || label || scope }
}
