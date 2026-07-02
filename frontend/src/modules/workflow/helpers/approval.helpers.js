/**
 * 统一审批 helper —— 退回校验/可操作判断/记录追加/状态文案。
 * 页面禁止自行实现这些规则（尤其退回原因校验）。
 */
import {
  TASK_STATUS,
  TASK_STATUS_LABELS,
  TASK_STATUS_BADGE,
  REJECT_REASON_MIN_LENGTH
} from '../constants/workflow.constants'

/** 终态集合 */
const FINISHED = [TASK_STATUS.APPROVED, TASK_STATUS.COMPLETED, TASK_STATUS.CANCELED, TASK_STATUS.WITHDRAWN, TASK_STATUS.REJECTED]

/** 任务是否已终态（已退回视为终态：需发起人重新提交产生新流转） */
export function isTaskFinished(task) {
  return !task || FINISHED.includes(task.status)
}

/**
 * 退回原因校验（唯一实现）。
 * @returns {{ valid:boolean, message:string, length:number, minLength:number }}
 */
export function validateRejectReason(reason) {
  const trimmed = String(reason || '').trim()
  const length = trimmed.length
  const valid = length >= REJECT_REASON_MIN_LENGTH
  return {
    valid,
    length,
    minLength: REJECT_REASON_MIN_LENGTH,
    message: valid ? '' : `退回原因不能少于 ${REJECT_REASON_MIN_LENGTH} 个字（当前 ${length} 字）`
  }
}

/** 是否可通过：待处理 + 有审批权限 */
export function canApproveTask(task, context) {
  if (!task || task.status !== TASK_STATUS.PENDING) return false
  return hasPerm(context, 'workflow.task.approve')
}

/** 是否可退回 */
export function canRejectTask(task, context) {
  if (!task || task.status !== TASK_STATUS.PENDING) return false
  return hasPerm(context, 'workflow.task.reject')
}

/** 是否可撤回：待处理 + 有撤回权限（真实场景应校验发起人本人，mock 阶段由按钮权限承担） */
export function canWithdrawTask(task, context) {
  if (!task || task.status !== TASK_STATUS.PENDING) return false
  return hasPerm(context, 'workflow.task.withdraw')
}

function hasPerm(context, key) {
  if (!context) return false
  const pool = context.buttonPermissions || context.permissions || []
  return pool.includes(key)
}

/** 前端侧追加审批记录（乐观更新用；服务端记录以 api 返回为准） */
export function appendApprovalRecord(task, action, operator, comment = '') {
  if (!task) return task
  const record = {
    recordId: `rec-local-${Date.now()}`,
    time: nowText(),
    operator,
    action,
    comment,
    nodeName: task.currentNode
  }
  task.records = [...(task.records || []), record]
  return record
}

export function getTaskStatusText(status) {
  return TASK_STATUS_LABELS[status] || status || '—'
}

/** 状态 → AppBadge type */
export function getTaskStatusType(status) {
  return TASK_STATUS_BADGE[status] || 'neutral'
}

function nowText() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
