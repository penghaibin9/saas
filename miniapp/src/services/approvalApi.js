/**
 * 教师小程序审批专用真实 API。
 * A1 红线：RETURN/REJECT 分离，动作结果只认服务端；禁止 mock fallback 和本地合成终态。
 */
import { realRequest } from './request'

const TYPE_LABEL = {
  PROFILE_CORRECTION: '信息更正',
  COMPANY_CHANGE: '实习变更',
  MATERIAL_VERIFY: '材料核验',
  LEAVE: '请假审批',
  AID: '困难认定',
  FUNDING: '奖助评定',
  DISCIPLINE: '违纪认定',
  DISCIPLINE_REMOVE: '违纪解除',
  AA_STATUS_CHANGE: '学籍异动',
  AA_GRADE_TASK: '成绩审核',
  AA_GRADE_CHANGE: '成绩更正',
  AA_SCHEDULE_CHANGE: '调停课审批'
}

function fmt(value) {
  return value ? String(value).replace('T', ' ').slice(0, 16) : ''
}

function mapTask(t = {}) {
  const urgency = t.urgency || 'NORMAL'
  return {
    id: String(t.taskId || ''),
    taskId: String(t.taskId || ''),
    version: Number(t.version ?? 0),
    title: t.title || '审批任务',
    type: TYPE_LABEL[t.sourceBizType] || t.sourceBizType || '审批',
    sourceBizType: t.sourceBizType || '',
    student: t.applicantName || '申请人',
    className: t.className || '',
    submitTime: fmt(t.submittedAt),
    status: String(t.status || '').toUpperCase() === 'PENDING' ? 'PENDING_REVIEW' : String(t.status || ''),
    level: urgency === 'OVERDUE' || urgency === 'NEAR_DEADLINE' ? 'high' : 'normal',
    allowedActions: Array.isArray(t.allowedActions) ? t.allowedActions : ['APPROVE', 'RETURN', 'REJECT', 'TRANSFER'],
    fields: t.sourceBizId ? [{ label: '业务记录', value: String(t.sourceBizId) }] : [],
    flow: [{ node: t.nodeName || t.nodeCode || '当前审批', time: '', current: true, done: false }]
  }
}

export async function getPendingApprovals(page = 1, pageSize = 50) {
  const d = await realRequest(`/approvals/tasks?page=${page}&pageSize=${pageSize}`)
  const items = Array.isArray(d?.items) ? d.items.map(mapTask) : []
  return { items, total: Number(d?.total || 0), page: Number(d?.page || page), pageSize: Number(d?.pageSize || pageSize) }
}

export async function actApproval(task, action, reason = '') {
  const normalized = String(action || '').toUpperCase()
  const pathByAction = {
    APPROVE: 'approve',
    RETURN: 'return',
    REJECT: 'reject'
  }
  const endpoint = pathByAction[normalized]
  if (!endpoint) throw { code: 400001, biz: true, message: '不支持的审批动作' }
  const taskId = String(task?.taskId || task?.id || '')
  if (!/^\d+$/.test(taskId)) throw { code: 422001, biz: true, message: '审批任务编号无效，请刷新后重试' }
  if (!Array.isArray(task?.allowedActions) || !task.allowedActions.includes(normalized)) {
    throw { code: 409001, biz: true, message: '该任务当前不可执行此动作，请刷新后重试' }
  }
  const version = Number(task?.version)
  if (!Number.isInteger(version) || version < 0) throw { code: 409001, biz: true, message: '审批版本缺失，请刷新后重试' }
  if ((normalized === 'RETURN' || normalized === 'REJECT') && !String(reason || '').trim()) {
    throw { code: 422001, biz: true, message: normalized === 'RETURN' ? '请填写退回修改原因' : '请填写驳回终止原因' }
  }
  return realRequest(`/approvals/tasks/${encodeURIComponent(taskId)}/${endpoint}`, {
    method: 'POST',
    data: normalized === 'APPROVE'
      ? { comment: String(reason || ''), version }
      : { reason: String(reason || '').trim(), version }
  })
}
