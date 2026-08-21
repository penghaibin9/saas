/**
 * 审批中心生产 API facade。
 * 只消费真实后端事实；禁止 mock fallback、浏览器内存写入和前端合成终态。
 */
import { request } from '@/services/http/client'

const BIZ_TYPES = [
  ['PROFILE_CORRECTION', '信息更正'],
  ['COMPANY_CHANGE', '实习变更'],
  ['MATERIAL_VERIFY', '材料核验'],
  ['LEAVE', '请假审批'],
  ['AID', '困难认定'],
  ['FUNDING', '奖助评定'],
  ['DISCIPLINE', '违纪认定'],
  ['DISCIPLINE_REMOVE', '违纪解除'],
  ['AA_STATUS_CHANGE', '学籍异动'],
  ['AA_GRADE_TASK', '成绩审核'],
  ['AA_GRADE_CHANGE', '成绩更正'],
  ['AA_SCHEDULE_CHANGE', '调停课审批']
].map(([value, label]) => ({ value, label }))

const BIZ_LABEL = Object.fromEntries(BIZ_TYPES.map((x) => [x.value, x.label]))
const ROLE_LABEL = {
  COUNSELOR: '辅导员',
  COLLEGE_ADMIN: '学院管理员',
  ACADEMIC_TEACHER: '任课教师',
  ACADEMIC_ADMIN: '教务管理员',
  STUDENT_AFFAIRS_ADMIN: '学工管理员',
  SCHOOL_ADMIN: '学校管理员'
}

const FILTER_OPTIONS = {
  bizTypes: BIZ_TYPES,
  urgencies: [
    { value: 'OVERDUE', label: '已超时' },
    { value: 'NEAR_DEADLINE', label: '临期' },
    { value: 'NORMAL', label: '正常' }
  ],
  doneResults: [
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回修改' },
    { value: 'REJECTED', label: '已驳回终止' },
    { value: 'TRANSFERRED', label: '已转办' }
  ],
  rectifyStatuses: [
    { value: 'PENDING_RESUBMIT', label: '待整改重报' },
    { value: 'RESUBMITTED', label: '已重新提交' },
    { value: 'CLOSED', label: '已关闭' }
  ],
  templateStatuses: [
    { value: 'ENABLED', label: '启用' },
    { value: 'VOIDED', label: '作废' }
  ],
  templateNodeRoles: Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))
}

const BATCH_ACTIONS = [
  { key: 'batchApprove', label: '批量通过' },
  { key: 'batchReturn', label: '批量退回' },
  { key: 'batchTransfer', label: '批量转交' }
]

const todoVersions = new Map()
const templateVersions = new Map()
const pendingIdempotencyKeys = new Map()
let latestTransferTargets = []

function ok(data, message = '成功') {
  return { code: 0, message, data }
}

function fail(error) {
  return {
    code: Number(error?.code) || -1,
    bizCode: error?.bizCode || '',
    message: error?.message || '请求失败，请稍后重试',
    details: error?.details,
    traceId: error?.traceId,
    data: null
  }
}

async function safe(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

function hasPattern(patterns, target) {
  const list = Array.isArray(patterns) ? patterns : []
  return list.some((p) => {
    if (p === '*' || p === target) return true
    if (p.endsWith('.*')) return target.startsWith(p.slice(0, -1))
    return false
  })
}

function actionMeta(visible, allowed, reason = '') {
  return { visible: !!visible, allowed: !!allowed, reason: allowed ? '' : reason }
}

function fmtTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

function stableStringify(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return '[' + value.map(stableStringify).join(',') + ']'
  return '{' + Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',') + '}'
}

function createIdempotencyKey(operation) {
  const suffix = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
  return `approval-${operation}-${suffix}`.slice(0, 128)
}

async function idempotentPost(operation, path, body) {
  const fingerprint = `${operation}:${stableStringify(body)}`
  let key = pendingIdempotencyKeys.get(fingerprint)
  if (!key) {
    key = createIdempotencyKey(operation)
    pendingIdempotencyKeys.set(fingerprint, key)
  }
  // await 抛错时后续 delete 不会执行，因此网络不确定失败会自然保留同一 key 供重试。
  const data = await request(path, {
    method: 'POST',
    body,
    headers: { 'Idempotency-Key': key }
  })
  pendingIdempotencyKeys.delete(fingerprint)
  return data
}

function mapStatus(status) {
  const raw = String(status || '').toUpperCase()
  const table = {
    PENDING: ['PENDING_REVIEW', '待审批'],
    APPROVED: ['APPROVED', '已通过'],
    RETURNED: ['RETURNED', '已退回修改'],
    REJECTED: ['REJECTED', '已驳回终止'],
    TRANSFERRED: ['TRANSFERRED', '已转办']
  }
  return table[raw] || [raw || 'UNKNOWN', raw || '未知']
}

function taskRow(t = {}) {
  const [status, statusLabel] = mapStatus(t.status)
  const urgency = t.urgency || 'NORMAL'
  return {
    taskId: String(t.taskId || ''),
    instanceId: String(t.instanceId || ''),
    bizType: t.sourceBizType || 'GENERAL',
    bizTypeLabel: BIZ_LABEL[t.sourceBizType] || t.sourceBizType || '审批',
    title: t.title || '',
    applicant: {
      name: t.applicantName || '—',
      studentNo: t.studentNo || '',
      className: t.className || ''
    },
    applicantName: t.applicantName || '—',
    className: t.className || '',
    submitTime: fmtTime(t.submittedAt),
    deadline: fmtTime(t.deadlineAt),
    urgency,
    urgencyLabel: {
      OVERDUE: '已超时',
      NEAR_DEADLINE: '临期',
      URGENT: '临期',
      NORMAL: '正常'
    }[urgency] || urgency,
    status,
    statusLabel,
    currentNode: t.nodeName || t.nodeCode || '',
    transferred: String(t.status || '').toUpperCase() === 'TRANSFERRED',
    version: Number(t.version ?? 0),
    allowedActions: Array.isArray(t.allowedActions) ? t.allowedActions : [],
    instanceStatus: t.instanceStatus || '',
    actedAt: t.actedAt || '',
    actionReason: t.actionReason || '',
    sourceBizId: t.sourceBizId || ''
  }
}

function timelineRow(h = {}) {
  const status = String(h.action || '').toUpperCase()
  const labels = {
    PENDING: '进入审批',
    APPROVED: '审批通过',
    RETURNED: '退回修改',
    REJECTED: '驳回终止',
    TRANSFERRED: '转办'
  }
  return {
    who: h.assigneeName || (h.assigneeId ? `办理人 ${h.assigneeId}` : '系统'),
    action: labels[status] || status,
    comment: h.comment || '',
    time: fmtTime(h.actedAt || h.createdAt),
    tone: status === 'APPROVED' ? 'success' : status === 'REJECTED' ? 'danger' : status === 'RETURNED' ? 'warning' : 'default'
  }
}

function doneRow(t = {}) {
  const row = taskRow(t)
  const raw = String(t.status || '').toUpperCase()
  return {
    ...row,
    result: raw,
    resultLabel: mapStatus(raw)[1],
    comment: t.actionReason || '',
    finishTime: fmtTime(t.actedAt),
    node: row.currentNode
  }
}

function returnedRow(t = {}) {
  const row = taskRow(t)
  const rs = t.rectifyStatus || 'PENDING_RESUBMIT'
  return {
    id: `return-${row.taskId}`,
    ...row,
    reason: t.actionReason || '',
    returnedBy: t.actorName || '当前办理人',
    returnTime: fmtTime(t.actedAt),
    rectifyStatus: rs,
    rectifyStatusLabel: {
      PENDING_RESUBMIT: '待整改重报',
      RESUBMITTED: '已重新提交',
      CLOSED: '已关闭'
    }[rs] || rs
  }
}

function templateRow(t = {}) {
  const mapped = {
    id: String(t.id || ''),
    name: t.name || '',
    bizType: t.bizType || '',
    bizTypeLabel: BIZ_LABEL[t.bizType] || t.bizType || '审批',
    version: `v${t.definitionVersion || 1}`,
    rowVersion: Number(t.rowVersion ?? 0),
    status: t.status || 'ENABLED',
    statusLabel: t.status === 'VOIDED' ? '已作废' : t.status === 'ENABLED' ? '启用' : t.status,
    updatedBy: t.updatedBy || '系统',
    updatedAt: fmtTime(t.updatedAt),
    voidReason: t.voidReason || '',
    nodes: (t.nodes || []).map((n) => ({
      name: n.name,
      role: n.role,
      roleLabel: ROLE_LABEL[n.role] || n.role,
      sla: n.sla,
      nodeCode: n.nodeCode
    }))
  }
  templateVersions.set(mapped.id, mapped.rowVersion)
  return mapped
}

async function resolveBatchItems(selected = []) {
  const out = []
  for (const value of selected) {
    const taskId = String(typeof value === 'object' ? (value.taskId || value.id || '') : value)
    if (!taskId) continue
    let version = typeof value === 'object' ? value.version : todoVersions.get(taskId)
    if (version === undefined || version === null) {
      const detail = await request(`/approvals/tasks/${encodeURIComponent(taskId)}`)
      version = detail.version
      todoVersions.set(taskId, version)
    }
    out.push({ taskId, version: Number(version) })
  }
  return out
}

async function loadTransferTargets(taskIds = []) {
  const ids = [...new Set((Array.isArray(taskIds) ? taskIds : [taskIds])
    .map((x) => String(typeof x === 'object' ? (x.taskId || x.id || '') : x))
    .filter(Boolean))]
  if (!ids.length) {
    latestTransferTargets = []
    return []
  }
  const lists = await Promise.all(ids.map((taskId) =>
    request(`/approvals/tasks/${encodeURIComponent(taskId)}/transfer-targets`)
  ))
  const first = Array.isArray(lists[0]) ? lists[0] : []
  const allowedSets = lists.slice(1).map((rows) => new Set((rows || []).map((x) => String(x.userId))))
  latestTransferTargets = first.filter((row) => allowedSets.every((set) => set.has(String(row.userId))))
  return latestTransferTargets
}

async function getContextRaw() {
  const [brand, authCtx] = await Promise.all([
    request('/tenant/brand'),
    request('/rbac/current-context')
  ])
  const patterns = Array.isArray(authCtx.permissionPatterns) ? authCtx.permissionPatterns : []
  const manage = hasPattern(patterns, 'approval.manage') || hasPattern(patterns, '*')
  const currentRole = authCtx.currentRole || {}
  const dataScope = authCtx.dataScope || {}
  latestTransferTargets = []
  const single = actionMeta(true, true)
  const batch = actionMeta(true, manage, '批量办理仅限具备 approval.manage 的管理角色')
  const adminOnly = actionMeta(true, manage, '当前身份缺少 approval.manage 权限')
  return {
    tenantBrandConfig: {
      schoolName: brand.schoolName || '',
      platformName: brand.platformDisplayName || '',
      watermarkText: brand.watermarkText || ''
    },
    currentRole: {
      ...currentRole,
      roleName: currentRole.roleName || currentRole.roleCode || '当前身份'
    },
    dataScope: {
      ...dataScope,
      scopeName: dataScope.scopeName || dataScope.name || '当前数据范围'
    },
    permissionPatterns: patterns,
    permissionActions: {
      approveTask: single,
      returnTask: single,
      rejectTask: single,
      transferTask: single,
      batchApprove: batch,
      batchReturn: batch,
      batchTransfer: batch,
      exportRecords: adminOnly,
      viewTemplates: adminOnly,
      createTemplate: adminOnly,
      editTemplate: adminOnly,
      voidTemplate: adminOnly,
      exportTemplates: adminOnly,
      viewAuditLog: adminOnly
    },
    filterOptions: FILTER_OPTIONS,
    batchActions: BATCH_ACTIONS,
    transferTargets: [],
    realApi: true
  }
}

export const approvalApi = {
  getContext: () => safe(getContextRaw),

  getTodoSummary: () => safe(async () => {
    const d = await request('/approvals/summary')
    return {
      ...d,
      byBizType: (d.byBizType || []).map((x) => {
        const label = BIZ_LABEL[x.bizType] || x.bizType || '审批'
        return {
          ...x,
          label,
          bizTypeLabel: label,
          earliest: fmtTime(x.earliest),
          overdue: Number(x.overdue || 0)
        }
      }),
      overdueList: (d.overdueList || []).map(taskRow)
    }
  }),

  getTodos: (params = {}) => safe(async () => {
    const d = await request('/approvals/tasks', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        bizType: params.bizType,
        urgency: params.urgency,
        submitDate: params.submitDate
      }
    })
    const list = (d.items || []).map(taskRow)
    list.forEach((x) => todoVersions.set(x.taskId, x.version))
    return { list, total: Number(d.total || 0) }
  }),

  getApprovalDetail: (taskId) => safe(async () => {
    const d = await request(`/approvals/tasks/${encodeURIComponent(taskId)}`)
    const task = taskRow(d)
    todoVersions.set(task.taskId, task.version)
    return {
      task,
      detail: {
        fields: d.sourceBizId ? [{ label: '业务记录', value: d.sourceBizId, masked: false }] : [],
        applyNote: '',
        attachments: Array.isArray(d.attachments) ? d.attachments : []
      },
      timeline: (d.history || []).map(timelineRow),
      suggestions: []
    }
  }),

  getTransferTargets: (taskIds) => safe(async () => loadTransferTargets(taskIds)),

  approveTask: (taskId, payload = {}) => safe(async () =>
    request(`/approvals/tasks/${encodeURIComponent(taskId)}/approve`, {
      method: 'POST',
      body: { comment: payload.comment || '', version: payload.version }
    })
  ),

  returnTask: (taskId, payload = {}) => safe(async () =>
    request(`/approvals/tasks/${encodeURIComponent(taskId)}/return`, {
      method: 'POST',
      body: { reason: payload.reason || '', version: payload.version }
    })
  ),

  rejectTask: (taskId, payload = {}) => safe(async () =>
    request(`/approvals/tasks/${encodeURIComponent(taskId)}/reject`, {
      method: 'POST',
      body: { reason: payload.reason || '', version: payload.version }
    })
  ),

  transferTask: (taskId, payload = {}) => safe(async () =>
    request(`/approvals/tasks/${encodeURIComponent(taskId)}/transfer`, {
      method: 'POST',
      body: {
        targetUserId: payload.targetUserId,
        comment: payload.note || payload.comment || '',
        version: payload.version
      }
    })
  ),

  batchApprove: (selected = []) => safe(async () => {
    const items = await resolveBatchItems(selected)
    const body = { action: 'APPROVE', items }
    return idempotentPost('batch-approve', '/approvals/batch', body)
  }),

  batchReturn: (selected = [], payload = {}) => safe(async () => {
    const items = await resolveBatchItems(selected)
    const body = { action: 'RETURN', items, reason: payload.reason || '' }
    return idempotentPost('batch-return', '/approvals/batch', body)
  }),

  batchTransfer: (selected = [], payload = {}) => safe(async () => {
    const items = await resolveBatchItems(selected)
    const body = {
      action: 'TRANSFER',
      items,
      targetUserId: payload.targetUserId,
      comment: payload.note || ''
    }
    const d = await idempotentPost('batch-transfer', '/approvals/batch', body)
    const target = latestTransferTargets.find((x) => String(x.userId) === String(payload.targetUserId))
    return { ...d, transferredTo: target?.userName || payload.targetUserId }
  }),

  getDoneItems: (params = {}) => safe(async () => {
    const d = await request('/approvals/tasks/done', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        bizType: params.bizType,
        result: params.result,
        actedFrom: params.actedFrom,
        actedTo: params.actedTo
      }
    })
    return { list: (d.items || []).map(doneRow), total: Number(d.total || 0) }
  }),

  // TP-A03/A04：真实服务端 seek 取"下一条待办"，不是拿 pageSize=1 重新查第一页猜。
  getNextTodo: (taskId, params = {}) => safe(async () => {
    const d = await request(`/approvals/tasks/${encodeURIComponent(taskId)}/next`, {
      params: {
        keyword: params.keyword,
        bizType: params.bizType,
        urgency: params.urgency,
        submitDate: params.submitDate
      }
    })
    return d ? taskRow(d) : null
  }),

  getCcItems: (params = {}) => safe(async () => {
    const d = await request('/approvals/cc', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        readStatus: params.readStatus
      }
    })
    return {
      list: (d.items || []).map((x) => ({
        ...x,
        bizTypeLabel: BIZ_LABEL[x.sourceBizType] || x.sourceBizType || '审批',
        readStatusLabel: x.readStatus === 'READ' ? '已读' : '未读'
      })),
      total: Number(d.total || 0)
    }
  }),

  getReturnedItems: (params = {}) => safe(async () => {
    const d = await request('/approvals/tasks/returned', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        rectifyStatus: params.rectifyStatus
      }
    })
    return { list: (d.items || []).map(returnedRow), total: Number(d.total || 0) }
  }),

  getTemplates: (params = {}) => safe(async () => {
    const d = await request('/approvals/templates', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        bizType: params.bizType,
        status: params.status
      }
    })
    return { list: (d.items || []).map(templateRow), total: Number(d.total || 0) }
  }),

  createTemplate: (payload = {}) => safe(async () => {
    const d = await request('/approvals/templates', { method: 'POST', body: payload })
    return templateRow(d)
  }),

  updateTemplate: (templateId, payload = {}) => safe(async () => {
    const version = templateVersions.get(String(templateId))
    if (version === undefined) throw new Error('模板版本缺失，请刷新列表后重试')
    return templateRow(await request(`/approvals/templates/${encodeURIComponent(templateId)}`, {
      method: 'PUT',
      body: { ...payload, version }
    }))
  }),

  voidTemplate: (templateId, payload = {}) => safe(async () => {
    const version = templateVersions.get(String(templateId))
    if (version === undefined) throw new Error('模板版本缺失，请刷新列表后重试')
    return templateRow(await request(`/approvals/templates/${encodeURIComponent(templateId)}/void`, {
      method: 'POST',
      body: { reason: payload.reason || '', version }
    }))
  }),

  exportRecords: (payload = {}) => safe(async () => {
    const body = { scope: payload.scope, purpose: payload.purpose }
    return idempotentPost('export', '/approvals/export', body)
  }),

  getAuditLogs: () => safe(async () => request('/approvals/audit', { params: { limit: 20 } }))
}
