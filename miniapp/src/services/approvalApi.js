/**
 * 教师小程序审批专用真实 API。
 * A1 红线：RETURN/REJECT 分离，动作结果只认服务端；禁止 mock fallback 和本地合成终态。
 * Stage B / B2：pending / done / mine 全部走真实服务端分页，并支持关键词搜索。
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
  const rawStatus = String(t.status || '').toUpperCase()
  return {
    id: String(t.taskId || t.instanceId || ''),
    taskId: String(t.taskId || t.instanceId || ''),
    instanceId: String(t.instanceId || ''),
    version: Number(t.version ?? 0),
    title: t.title || '审批任务',
    type: TYPE_LABEL[t.sourceBizType] || t.sourceBizType || '审批',
    sourceBizType: t.sourceBizType || '',
    sourceBizId: String(t.sourceBizId || ''),
    orderNo: t.sourceBizId ? String(t.sourceBizId) : '',
    student: t.applicantName || '申请人',
    studentNo: t.studentNo || '',
    className: t.className || '',
    submitTime: fmt(t.submittedAt),
    actedTime: fmt(t.actedAt),
    status: rawStatus === 'PENDING' ? 'PENDING_REVIEW' : rawStatus,
    level: urgency === 'OVERDUE' || urgency === 'NEAR_DEADLINE' ? 'high' : 'normal',
    allowedActions: Array.isArray(t.allowedActions) ? t.allowedActions : [],
    fields: [
      ...(t.studentNo ? [{ label: '学号', value: String(t.studentNo) }] : []),
      ...(t.sourceBizId ? [{ label: '业务单号', value: String(t.sourceBizId) }] : [])
    ],
    flow: [{ node: t.nodeName || t.nodeCode || '当前审批', time: '', current: rawStatus === 'PENDING', done: rawStatus !== 'PENDING' }]
  }
}

function buildQueueUrl(mode, page, pageSize, keyword = '', bizType = '') {
  const params = [
    `mode=${encodeURIComponent(mode)}`,
    `page=${Number(page || 1)}`,
    `pageSize=${Number(pageSize || 20)}`
  ]
  const kw = String(keyword || '').trim()
  if (kw) params.push(`keyword=${encodeURIComponent(kw)}`)
  if (bizType) params.push(`bizType=${encodeURIComponent(bizType)}`)
  return `/approvals/mobile/queue?${params.join('&')}`
}

export async function getApprovalQueue(mode = 'pending', page = 1, pageSize = 20, keyword = '', bizType = '') {
  const d = await realRequest(buildQueueUrl(mode, page, pageSize, keyword, bizType))
  const items = Array.isArray(d?.items) ? d.items.map(mapTask) : []
  return {
    items,
    total: Number(d?.total || 0),
    page: Number(d?.page || page),
    pageSize: Number(d?.pageSize || pageSize)
  }
}

export function getPendingApprovals(page = 1, pageSize = 20, keyword = '', bizType = '') {
  return getApprovalQueue('pending', page, pageSize, keyword, bizType)
}

export function getDoneApprovals(page = 1, pageSize = 20, keyword = '', bizType = '') {
  return getApprovalQueue('done', page, pageSize, keyword, bizType)
}

export function getMyApprovals(page = 1, pageSize = 20, keyword = '', bizType = '') {
  return getApprovalQueue('mine', page, pageSize, keyword, bizType)
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
  if ((normalized === 'RETURN' || normalized === 'REJECT') && !String(reason || '').trim()) {
    throw { code: 422001, biz: true, message: normalized === 'RETURN' ? '请填写退回修改原因' : '请填写驳回终止原因' }
  }

  // 点击动作时重新读取服务端详情：allowedActions 与 version 必须来自此刻的真实任务，
  // 列表缓存只用于展示，不能决定是否允许办理，也不能拿旧版本制造成功。
  const fresh = await realRequest(`/approvals/tasks/${encodeURIComponent(taskId)}`)
  const allowedActions = Array.isArray(fresh?.allowedActions) ? fresh.allowedActions : []
  if (!allowedActions.includes(normalized)) {
    throw { code: 409001, biz: true, message: '该任务当前不可执行此动作，请刷新后重试' }
  }
  const version = Number(fresh?.version)
  if (!Number.isInteger(version) || version < 0) throw { code: 409001, biz: true, message: '审批版本缺失，请刷新后重试' }

  return realRequest(`/approvals/tasks/${encodeURIComponent(taskId)}/${endpoint}`, {
    method: 'POST',
    data: normalized === 'APPROVE'
      ? { comment: String(reason || ''), version }
      : { reason: String(reason || '').trim(), version }
  })
}
