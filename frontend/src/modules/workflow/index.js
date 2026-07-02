/**
 * 11 权限与流程中心 —— 模块聚合出口。
 * 页面只准从此处或 provider/context/helpers 引用；禁止直引 mock 与 api.mock。
 */
export * as workflowProvider from './provider/workflow.provider'
export * from './constants/workflow.constants'
export {
  loadPermissionContext,
  getPermissionContext,
  canAccessPage,
  canClickButton,
  canViewMenu,
  getDataScope,
  hasRole,
  hasAnyPermission,
  filterMenusByPermission,
  filterActionsByPermission
} from './context/permission.context'
export {
  checkRoutePermission,
  checkMenuPermission,
  checkButtonPermission,
  checkDataScope
} from './guards/workflow.guards'
export * from './helpers/approval.helpers'
export * from './helpers/permission.helpers'
export * from './helpers/workflow.helpers'
