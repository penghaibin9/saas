/**
 * 统一 guard 预留（本次不注册全局路由守卫；P8 实装时在 router 中调用，签名冻结不变）。
 * 判定顺序与 03 开关模型冻结优先级兼容：
 * 租户停用 > 到期只读 > 模块未授权 > 试用限制 > 功能开关 > 角色权限 > 按钮权限 > 数据范围。
 * licenseContext 为预留关系，本次不接真实授权中心。
 */
import {
  canAccessPage,
  canViewMenu,
  canClickButton,
  resolveDataScope
} from '../helpers/permission.helpers'
import { DATA_SCOPE } from '../constants/workflow.constants'

/**
 * 路由级校验。
 * @param {object} routeMeta 期望包含 { permissionKey?, moduleCode? }
 * @returns {{ allowed:boolean, reason:string }}
 */
export function checkRoutePermission(routeMeta = {}, permissionContext = null) {
  // licenseContext 预留位：moduleCode 未授权/只读的拦截在 P6-2 接入 licenseContext 后叠加于此
  if (!routeMeta.permissionKey) return { allowed: true, reason: '' }
  const allowed = canAccessPage(routeMeta.permissionKey, permissionContext)
  return { allowed, reason: allowed ? '' : `缺少页面权限：${routeMeta.permissionKey}` }
}

/** 菜单级校验 */
export function checkMenuPermission(menuItem = {}, permissionContext = null) {
  if (!menuItem.permissionKey) return { allowed: true, reason: '' }
  const allowed = canViewMenu(menuItem.permissionKey, permissionContext)
  return { allowed, reason: allowed ? '' : `缺少菜单权限：${menuItem.permissionKey}` }
}

/** 按钮级校验 */
export function checkButtonPermission(permissionKey, permissionContext = null) {
  const allowed = canClickButton(permissionKey, permissionContext)
  return { allowed, reason: allowed ? '' : `缺少按钮权限：${permissionKey}` }
}

/**
 * 数据范围校验（行级）。record 期望携带 schoolId/collegeId/classId/ownerId。
 * mock 阶段宽松放行未知字段；真实阶段由后端复核。
 */
export function checkDataScope(record = {}, permissionContext = null) {
  const ctx = permissionContext
  if (!ctx) return { allowed: false, reason: '权限上下文未加载' }
  const { scope } = resolveDataScope(ctx)
  switch (scope) {
    case DATA_SCOPE.ALL:
      return { allowed: true, reason: '' }
    case DATA_SCOPE.SCHOOL:
      return ok(!record.schoolId || record.schoolId === ctx.schoolId, '超出本校数据范围')
    case DATA_SCOPE.COLLEGE:
      return ok(!record.collegeId || record.collegeId === ctx.collegeId, '超出本学院数据范围')
    case DATA_SCOPE.CLASS:
      return ok(!record.classId || record.classId === ctx.classId, '超出本班级数据范围')
    case DATA_SCOPE.SELF:
      return ok(!record.ownerId || record.ownerId === ctx.userId, '仅可访问本人数据')
    case DATA_SCOPE.ASSIGNED:
      return ok(!record.assigneeIds || record.assigneeIds.includes(ctx.userId), '仅可访问被指派对象')
    default:
      return { allowed: false, reason: `未知数据范围：${scope}` }
  }
}

function ok(allowed, failReason) {
  return { allowed: !!allowed, reason: allowed ? '' : failReason }
}
