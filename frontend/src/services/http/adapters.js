/** P2 · 后端字段 → PC mock 契约字段适配（DTO 对齐，UI 零改动）。 */
import { request } from './client'

const envelope = (data) => ({ code: 0, message: 'ok（真实接口）', data })

const STAGE_TO_STATUS = {
  ORIENTATION: 'ADMITTED',
  ON_CAMPUS: 'ENROLLED',
  INTERNSHIP: 'ENROLLED',
  GRADUATION_DESIGN: 'ENROLLED',
  EMPLOYMENT: 'ENROLLED'
}

function studentRow(r) {
  return {
    studentId: String(r.id),
    name: r.realName,
    gender: r.gender || '—',
    studentNo: r.studentNo,
    idCard: r.idCardMasked || '',
    phone: r.phoneMasked || '',
    collegeId: r.collegeId || '',
    collegeName: r.collegeName || '',
    majorId: r.majorId || '',
    majorName: r.majorName || '',
    classId: r.classId || '',
    className: r.className || '',
    grade: r.grade || '',
    enrollDate: (r.createdAt || '').slice(0, 10),
    counselorName: '—',
    studentStatus: r.isDeleted ? 'VOIDED' : STAGE_TO_STATUS[r.currentStage] || 'ENROLLED',
    identityVerifyStatus: 'VERIFIED',
    accountBindStatus: 'BOUND',
    riskLevel: r.riskLevel || 'NONE',
    dataCompleteness: 90,
    voided: !!r.isDeleted,
    voidReason: '',
    updatedAt: (r.updatedAt || '').replace('T', ' ').slice(0, 16)
  }
}

export async function getStudents(params = {}) {
  const data = await request('/students', {
    params: {
      page: params.page || 1,
      pageSize: params.pageSize || 10,
      keyword: params.keyword,
      className: params.className,
      riskLevel: params.riskLevel
    }
  })
  return envelope({
    list: data.items.map(studentRow),
    total: data.total,
    page: data.page,
    pageSize: data.pageSize
  })
}

export async function getStudentDetail(studentId) {
  const d = await request(`/students/${studentId}`)
  return envelope({
    ...studentRow(d),
    contacts: d.contacts || [],
    timeline: d.timeline || [],
    statusHistory: [],
    identityRecords: [],
    corrections: [],
    riskTags: [],
    auditTrail: []
  })
}

export async function createStudent(payload = {}) {
  const d = await request('/students', {
    method: 'POST',
    body: {
      studentNo: payload.studentNo,
      realName: payload.name,
      gender: payload.gender,
      phone: payload.phone,
      idCard: payload.idCard,
      grade: payload.grade,
      classId: payload.classId || null
    }
  })
  return envelope(studentRow(d))
}

export async function updateStudent(studentId, payload = {}) {
  const d = await request(`/students/${studentId}`, {
    method: 'PUT',
    body: { realName: payload.name, gender: payload.gender, grade: payload.grade, phone: payload.phone }
  })
  return envelope(studentRow(d))
}

export async function voidStudent(studentId, reason) {
  const d = await request(`/students/${studentId}/void`, { method: 'POST', body: { reason } })
  return envelope({ studentId: d.studentId, studentStatus: 'VOIDED', voided: true })
}

/** 上下文增强：真实品牌 / 当前角色 / 数据范围 / 待办计数 合入 mock ctx（保留 mock 字典与权限矩阵） */
export async function enrichContext(mockRes) {
  const [brand, ctx, todoSummary] = await Promise.all([
    request('/tenant/brand'),
    request('/rbac/current-context'),
    request('/todos/summary').catch(() => null)
  ])
  const data = mockRes.data || mockRes
  if (data.tenantBrandConfig) {
    data.tenantBrandConfig = {
      ...data.tenantBrandConfig,
      schoolName: brand.schoolName || data.tenantBrandConfig.schoolName,
      platformName: brand.platformDisplayName,
      watermarkText: brand.watermarkText || data.tenantBrandConfig.watermarkText
    }
  }
  if (ctx.currentRole && data.currentRole) {
    data.currentRole = { ...data.currentRole, ...ctx.currentRole }
  }
  if (ctx.dataScope && data.dataScope) {
    data.dataScope = {
      ...data.dataScope,
      scopeName: ctx.dataScope.scopeName || data.dataScope.scopeName,
      name: ctx.dataScope.scopeName || data.dataScope.name
    }
  }
  if (todoSummary && typeof todoSummary.pending === 'number') {
    data.pendingCount = todoSummary.pending
  }
  data.realApi = true
  return mockRes
}

/* ── 审批 ── */
const BIZ_LABEL = {
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

function approvalItem(t) {
  return {
    taskId: String(t.taskId),
    bizType: t.sourceBizType || 'GENERAL',
    bizTypeLabel: BIZ_LABEL[t.sourceBizType] || t.sourceBizType || '审批',
    title: t.title || '',
    applicant: { name: t.applicantName || '—', studentNo: '', className: '' },
    submitTime: (t.submittedAt || '').replace('T', ' ').slice(5, 16),
    deadline: '',
    urgency: t.urgency || 'NORMAL',
    urgencyLabel: { OVERDUE: '已超时', NEAR_DEADLINE: '临期', URGENT: '临期' }[t.urgency] || '正常',
    status: 'PENDING_REVIEW',
    statusLabel: '待审批',
    currentNode: t.nodeName || t.nodeCode || '',
    transferred: false
  }
}

export async function getApprovalTodos(params = {}) {
  const data = await request('/approvals/tasks', {
    params: { page: params.page || 1, pageSize: params.pageSize || 10 }
  })
  let list = data.items.map(approvalItem)
  if (params.keyword) {
    const kw = String(params.keyword).trim()
    list = list.filter((t) => t.title.includes(kw) || t.applicant.name.includes(kw) || t.taskId.includes(kw))
  }
  return envelope({ list, total: data.total, page: data.page, pageSize: data.pageSize })
}

export async function getApprovalDetail(taskId) {
  const t = await request(`/approvals/tasks/${taskId}`)
  return envelope({
    ...approvalItem(t),
    bizFields: (t.diff || []).map((d) => ({ label: d.field, oldValue: d.oldMasked, newValue: d.newMasked })),
    timeline: (t.history || []).map((h) => ({ title: h.action, time: h.at, who: h.by })),
    attachments: [],
    suggestion: ''
  })
}

export async function approveTask(taskId, comment) {
  const d = await request(`/approvals/tasks/${taskId}/approve`, { method: 'POST', body: { comment } })
  return envelope({ taskId: String(d.taskId), status: 'APPROVED', statusLabel: '已通过' })
}

export async function returnTask(taskId, reason) {
  const d = await request(`/approvals/tasks/${taskId}/reject`, { method: 'POST', body: { reason } })
  return envelope({ taskId: String(d.taskId), status: 'RETURNED', statusLabel: '已退回' })
}

export async function getTodoSummary() {
  const [s, tasks, groups] = await Promise.all([
    request('/todos/summary'),
    request('/approvals/tasks', { params: { page: 1, pageSize: 1 } }),
    request('/approvals/tasks/summary/by-biz-type').catch(() => [])
  ])
  return envelope({
    todayTag: '',
    total: tasks.total,
    todayNew: 0,
    nearDeadline: s.nearDeadline || 0,
    overdue: s.overdue || 0,
    byBizType: (groups || []).map((g) => ({
      bizType: g.bizType,
      label: BIZ_LABEL[g.bizType] || g.bizType || '其他',
      count: g.count,
      overdue: 0,
      earliest: (g.earliest || '').replace('T', ' ').slice(0, 16)
    })),
    overdueList: []
  })
}

/* ── 审计 ── */
export async function getAuditLogs() {
  const data = await request('/audit/logs', { params: { page: 1, pageSize: 100 } })
  return envelope(
    data.items.map((a) => ({
      id: String(a.auditId),
      who: a.actorName || '—',
      roleName: a.currentRole || '',
      action: a.action,
      target: a.resource || '',
      detail: a.detail ? JSON.stringify(a.detail) : '',
      summary: a.resource || '',
      result: a.result || 'SUCCESS',
      time: (a.occurredAt || '').replace('T', ' ').slice(0, 19)
    }))
  )
}

/* ── P4 · 学生主档导出（真实 xlsx：脱敏+水印+审计，返回可下载任务） ── */
import { API_BASE_URL, API_PREFIX } from './config'

export async function createStudentsExport({ purpose, remark, scopeLabel } = {}) {
  const purposeText = [purpose, remark].filter(Boolean).join('：') || '学生台账导出'
  const t = await request('/export/students', {
    method: 'POST',
    body: { purpose: purposeText.length >= 5 ? purposeText : purposeText + '（管理台导出）' }
  })
  return envelope({
    id: t.taskId,
    type: 'EXPORT',
    typeLabel: '导出',
    title: scopeLabel || '学生主档导出',
    fileName: t.fileName,
    totalRows: t.rowCount,
    successRows: t.rowCount,
    failedRows: 0,
    status: 'COMPLETED',
    operator: '',
    roleName: '',
    time: new Date().toISOString().slice(0, 16).replace('T', ' '),
    masked: true,
    watermark: true,
    downloadUrl: `${API_BASE_URL}${API_PREFIX}/export/tasks/${t.taskId}/download`,
    securityNotice: t.securityNotice,
    realApi: true
  })
}

/* ── P4.1 · 学生真实文件导入（Dry-Run 两步） ── */
import { requestUpload } from './client'

export async function validateStudentImportFile(file) {
  const d = await requestUpload('/import/students/validate-file', file)
  return envelope({
    batchNo: d.batchNo,
    status: d.status,
    totalRows: d.totalRows,
    validRows: d.okRows,
    successRows: d.okRows,
    errorRows: d.errorRows,
    errors: (d.errors || []).map((e) => ({
      row: e.rowIndex || e.rowNo,
      rowIndex: e.rowIndex || e.rowNo,
      field: e.field || e.errorCode || '—',
      rawValue: e.rawValue === undefined || e.rawValue === '' ? '—' : String(e.rawValue),
      message: e.message
    })),
    realApi: true
  })
}

export async function confirmStudentImport(batchNo) {
  const d = await request('/import/students/confirm', { method: 'POST', body: { batchNo } })
  return envelope({
    batchNo: d.batchNo,
    status: d.status,
    successRows: d.insertedRows,
    failedRows: 0,
    auditId: d.batchNo,
    realApi: true
  })
}
