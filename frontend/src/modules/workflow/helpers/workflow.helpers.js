/**
 * 流程通用 helper —— 模块/流程状态文案与徽标、视图状态计算。
 */
import {
  MODULE_LABELS,
  PROCESS_STATUS,
  PROCESS_STATUS_LABELS,
  PROCESS_INSTANCE_STATUS_LABELS,
  NODE_TYPE_LABELS,
  LICENSE_VIEW_STATE
} from '../constants/workflow.constants'

export function getModuleLabel(moduleCode) {
  return MODULE_LABELS[moduleCode] || moduleCode || '—'
}

export function getProcessStatusText(status) {
  return PROCESS_STATUS_LABELS[status] || status
}

/** 流程模板状态 → AppBadge type */
export function getProcessStatusType(status) {
  if (status === PROCESS_STATUS.ENABLED) return 'success'
  if (status === PROCESS_STATUS.DISABLED) return 'neutral'
  return 'info' // DRAFT
}

export function getInstanceStatusText(status) {
  return PROCESS_INSTANCE_STATUS_LABELS[status] || status
}

export function getNodeTypeLabel(nodeType) {
  return NODE_TYPE_LABELS[nodeType] || nodeType
}

/**
 * 计算页面授权视图状态（NORMAL / READONLY / NO_LICENSE）。
 * 当前 licenseContext 为预留关系（本次不接真实授权中心）；
 * 冻结优先级：租户停用 > 到期只读 > 模块未授权 > 试用限制 > 功能开关 > 角色权限。
 * P6-2 /platform 落地后，此函数改读真实 licenseContext，签名不变。
 */
export function resolveLicenseViewState(rawState) {
  if (rawState === LICENSE_VIEW_STATE.READONLY) return LICENSE_VIEW_STATE.READONLY
  if (rawState === LICENSE_VIEW_STATE.NO_LICENSE) return LICENSE_VIEW_STATE.NO_LICENSE
  return LICENSE_VIEW_STATE.NORMAL
}

export function isReadonlyState(viewState) {
  return viewState === LICENSE_VIEW_STATE.READONLY
}

export function isNoLicenseState(viewState) {
  return viewState === LICENSE_VIEW_STATE.NO_LICENSE
}
