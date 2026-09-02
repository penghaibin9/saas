/**
 * 02 数字迎新中心 API（生产级：业务与权限上下文仅走真实后端，不回退本地数据）。
 * orientation.meta 只保留字典与列配置，不承载品牌、角色、范围或权限事实。
 */
import * as meta from '@/modules/orientation/constants/orientation.meta'
import { request, requestUpload } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'

let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `ori-${Date.now()}-${++seq}`
})
const fail = (message, code = 1) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))

// 页面动作名只用于 UI 定位；是否允许完全由 current-context 返回的后端权限码模式判定。
const ACTION_PERMISSION = Object.freeze({
  'orientation.student.create': 'studentAffairs.orientation.manage',
  'orientation.student.view': 'studentAffairs.orientation.view',
  'orientation.student.edit': 'studentAffairs.orientation.manage',
  'orientation.student.void': 'studentAffairs.orientation.manage',
  'orientation.student.import': 'studentAffairs.orientation.import',
  'orientation.student.export': 'studentAffairs.orientation.export',
  'orientation.student.batchRemind': 'studentAffairs.orientation.manage',
  'orientation.student.batchAssign': 'studentAffairs.orientation.manage',
  'orientation.enrollment.finalize': 'studentAffairs.orientation.manage',
  'orientation.identity.activate': 'studentAffairs.orientation.manage',
  'orientation.progress.edit': 'studentAffairs.orientation.manage',
  'orientation.progress.export': 'studentAffairs.orientation.export',
  'orientation.progress.manualResolve': 'studentAffairs.orientation.manage',
  'orientation.payment.view': 'studentAffairs.orientation.view',
  'orientation.payment.export': 'studentAffairs.orientation.export',
  'orientation.greenchannel.review': 'studentAffairs.orientation.manage',
  'orientation.material.review': 'studentAffairs.orientation.manage',
  'orientation.material.export': 'studentAffairs.orientation.export',
  'orientation.dorm.edit': 'studentAffairs.orientation.manage',
  'orientation.dorm.confirm': 'studentAffairs.orientation.manage',
  'orientation.dorm.export': 'studentAffairs.orientation.export',
  'orientation.dorm.markException': 'studentAffairs.orientation.manage',
  'orientation.exception.handle': 'studentAffairs.orientation.manage',
  'orientation.exception.escalate': 'studentAffairs.orientation.manage',
  'orientation.exception.export': 'studentAffairs.orientation.export',
  'orientation.followup.create': 'studentAffairs.orientation.manage',
  'orientation.followup.edit': 'studentAffairs.orientation.manage',
  'orientation.audit.view': 'studentAffairs.orientation.view',
  'orientation.columns.setting': 'studentAffairs.orientation.view'
})

// 后端尚无精确能力的动作保持可见但禁用；不再用 501 伪装成已接通。
const UNSUPPORTED_ACTIONS = Object.freeze({
  'orientation.student.batchRemind': '当前后端尚未提供迎新批量提醒正式能力',
  'orientation.student.batchAssign': '当前后端尚未提供迎新批量分配辅导员正式能力',
  'orientation.followup.edit': '当前后端尚未提供异常跟进编辑正式能力'
})

function buildPermissionActions(patterns, readonlyTenant = false, readonlyReason = '') {
  return Object.fromEntries(
    Object.entries(ACTION_PERMISSION).map(([key, permissionCode]) => {
      const unsupportedReason = UNSUPPORTED_ACTIONS[key] || ''
      const permissionAllowed = matchPermission(patterns, permissionCode)
      const readonlyBlocked = readonlyTenant && (
        permissionCode.endsWith('.manage') || permissionCode.endsWith('.import')
      )
      const allowed = permissionAllowed && !unsupportedReason && !readonlyBlocked
      const reason = !permissionAllowed
        ? `当前身份缺少权限：${permissionCode}`
        : unsupportedReason || (readonlyBlocked ? readonlyReason || '当前租户为只读状态' : '')
      return [key, { allowed, visible: true, reason, permissionCode }]
    })
  )
}

async function callData(fn) {
  try {
    return envelope(await fn())
  } catch (e) {
    return fail(e.message || '真实接口不可用', e.code || 503001)
  }
}

async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) {
    return fail(e.message || '真实接口不可用', e.code || 503001)
  }
}

/* ---------------- 上下文 / 字典 ---------------- */
export async function getOrientationContext() {
  try {
    const [brand, ctx] = await Promise.all([
      request('/tenant/brand'),
      request('/rbac/current-context')
    ])
    const patterns = ctx?.moduleAccessHealthy === false
      ? []
      : (Array.isArray(ctx?.permissionPatterns) ? ctx.permissionPatterns : [])
    const role = ctx?.currentRole || {}
    const scope = ctx?.dataScope || {}
    return envelope({
      tenantBrandConfig: {
        ...(brand || {}),
        schoolName: brand?.schoolName || '',
        platformDisplayName: brand?.platformDisplayName || brand?.schoolName || '',
        watermarkText: brand?.watermarkText || brand?.schoolName || ''
      },
      currentRole: role,
      roles: Array.isArray(ctx?.availableRoles) ? ctx.availableRoles : [],
      dataScope: {
        ...scope,
        name: scope.scopeName || scope.scopeLabel || scope.name || '未声明数据范围'
      },
      permissionPatterns: patterns,
      permissionActions: buildPermissionActions(patterns, !!ctx?.readonlyTenant, ctx?.readonlyReason || ''),
      moduleEntitlements: Array.isArray(ctx?.moduleEntitlements) ? ctx.moduleEntitlements : [],
      moduleStates: ctx?.moduleStates || {},
      moduleAccessHealthy: ctx?.moduleAccessHealthy !== false,
      moduleAccessError: ctx?.moduleAccessError || '',
      readonlyTenant: !!ctx?.readonlyTenant,
      readonlyReason: ctx?.readonlyReason || '',
      realApi: true,
      ctxKey: [
        role.contextId || '',
        role.permissionVersion || '',
        role.roleCode || '',
        [...patterns].sort().join(',')
      ].join('|')
    })
  } catch (e) {
    return fail(e.message || '迎新权限上下文加载失败', e.code || 503001)
  }
}

export async function switchOrientationRole() {
  return fail('请使用系统身份切换，迎新模块不维护本地角色状态', 400003)
}

export async function getStatusOptions() {
  return envelope(clone(meta.statusOptions))
}
export async function getFilterOptions() {
  const [classResult, buildingResult] = await Promise.allSettled([
    request('/student-affairs/classes', { params: { page: 1, pageSize: 200 } }),
    request('/student-affairs/dorm/buildings', { params: { page: 1, pageSize: 200 } })
  ])
  const classes = classResult.status === 'fulfilled' ? (classResult.value?.items || []) : []
  const buildings = buildingResult.status === 'fulfilled' ? (buildingResult.value?.items || []) : []
  const colleges = [...new Map(classes
    .filter((row) => row.collegeId)
    .map((row) => [String(row.collegeId), {
      value: String(row.collegeId),
      label: row.collegeName || `学院#${row.collegeId}`
    }])).values()]
  return envelope({
    colleges,
    classes: classes.map((row) => ({
      value: String(row.classId || row.id || ''),
      label: row.className || row.name || `班级#${row.classId || row.id}`
    })).filter((row) => row.value),
    buildings: buildings.map((row) => ({
      value: String(row.buildingId || row.id || ''),
      label: row.buildingName || row.name || `楼栋#${row.buildingId || row.id}`
    })).filter((row) => row.value),
    availability: {
      classes: classResult.status === 'fulfilled' ? 'REAL' : 'UNAVAILABLE',
      buildings: buildingResult.status === 'fulfilled' ? 'REAL' : 'UNAVAILABLE'
    }
  })
}
export async function getRegistrationSteps() {
  return callData(async () => {
    const rows = await request('/orientation/flow-config')
    return (Array.isArray(rows) ? rows : [])
      .filter((row) => row.enabled !== false)
      .map((row) => ({ key: row.stepKey, label: row.stepName, required: !!row.required }))
  })
}
export async function getFieldColumns(listKey) {
  return envelope(clone(meta.fieldColumns[listKey] || []))
}
export async function getBatchActions(listKey) {
  return envelope(clone(meta.batchActions[listKey] || []))
}
export async function getImportTemplate(key) {
  return envelope(clone(meta.importTemplates[key] || null))
}
export async function getExportOptions(listKey) {
  return envelope({
    scopes: clone(meta.exportOptions.scopes),
    fieldGroups: clone(meta.exportOptions.fieldGroups[listKey] || []),
    maskDefault: meta.exportOptions.maskDefault,
    idCardPlainForbidden: meta.exportOptions.idCardPlainForbidden,
    watermarkNote: meta.exportOptions.watermarkNote,
    auditNotice: meta.exportOptions.auditNotice
  })
}

/* ---------------- 看板 / 新生 ---------------- */
export async function getOrientationDashboard() {
  return callData(() => request('/orientation/dashboard'))
}

export async function getOrientationStudents(params = {}) {
  return callList('/orientation/students', params)
}

export async function getOrientationStudentDetail(id) {
  return callData(() => request(`/orientation/students/${id}`))
}

export async function createOrientationStudent(payload) {
  return callData(() => request('/orientation/students', { method: 'POST', body: payload }))
}

export async function updateOrientationStudent(id, payload) {
  return callData(() => request(`/orientation/students/${id}`, { method: 'PUT', body: payload }))
}

export async function voidOrientationStudent(id, { reason }) {
  return callData(() => request(`/orientation/students/${id}/void`, { method: 'POST', body: { reason } }))
}

export async function verifyOrientationStudent(id, { passed = true, reason = '' } = {}) {
  return callData(() => request(`/orientation/students/${id}/verify`, { method: 'POST', body: { passed, reason } }))
}

export async function batchRemindStudents() {
  return fail('批量提醒能力未配置，操作已禁用', 400003)
}

export async function batchAssignCounselor() {
  return fail('批量分配辅导员能力未配置，操作已禁用', 400003)
}

/* ---------------- 报到进度 ---------------- */
export async function getRegistrationProgress(params = {}) {
  return callList('/orientation/progress', params)
}

export async function updateBlockedIssue(id, { blockedStep, blockedReason }) {
  return callData(() =>
    request(`/orientation/progress/${id}/blocked`, { method: 'PUT', body: { blockedStep, blockedReason } })
  )
}

export async function resolveBlockedIssue(id, { note = '' } = {}) {
  return callData(() => request(`/orientation/progress/${id}/resolve`, { method: 'POST', body: { note } }))
}

/* ---------------- 缴费 / 绿色通道 ---------------- */
export async function getPaymentStatusList(params = {}) {
  return callList('/orientation/payments', params)
}

export async function syncOrientationPayment(id, payload) {
  return callData(() => request(`/orientation/payments/${id}`, { method: 'PUT', body: payload }))
}

export async function getGreenChannelApplications(params = {}) {
  return callList('/orientation/green-channels', params)
}

export async function approveGreenChannel(id, { remark = '', expectedVersion } = {}) {
  return callData(() => request(`/orientation/green-channels/${id}/approve`, { method: 'POST', body: { remark, expectedVersion } }))
}

export async function rejectGreenChannel(id, { reason, expectedVersion }) {
  return callData(() => request(`/orientation/green-channels/${id}/reject`, { method: 'POST', body: { reason, expectedVersion } }))
}

export async function returnGreenChannel(id, { reason, expectedVersion }) {
  return callData(() => request(`/orientation/green-channels/${id}/return`, { method: 'POST', body: { reason, expectedVersion } }))
}

/* ---------------- 报到资格（服务端唯一裁决） ---------------- */
export async function getOrientationQualifications(params = {}) {
  return callList('/orientation/qualifications', params)
}

export async function getOrientationQualification(id) {
  return callData(() => request(`/orientation/qualifications/${id}`))
}

export async function recalculateOrientationQualification(id) {
  return callData(() => request(`/orientation/qualifications/${id}/recalculate`, { method: 'POST' }))
}

export async function finalizeOrientationEnrollment(id, payload) {
  return callData(() => request(`/orientation/students/${id}/finalize`, { method: 'POST', body: payload }))
}

export async function activateOrientationIdentity(id, payload) {
  return callData(() => request(`/orientation/students/${id}/activate`, { method: 'POST', body: payload }))
}

/* ---------------- 材料审核 ---------------- */
export async function getMaterialReviewList(params = {}) {
  return callList('/orientation/materials', params)
}

export async function approveOrientationMaterial(id, { comment = '' } = {}) {
  return callData(() => request(`/orientation/materials/${id}/approve`, { method: 'POST', body: { comment } }))
}

export async function returnOrientationMaterial(id, { reason }) {
  return callData(() => request(`/orientation/materials/${id}/return`, { method: 'POST', body: { reason } }))
}

export async function batchReviewOrientationMaterials(ids = [], { pass, reason = '' } = {}) {
  if (!pass && (!reason || reason.trim().length < 5)) return fail('批量退回必须填写原因（不少于 5 个字）')
  for (const id of ids) {
    const res = pass
      ? await approveOrientationMaterial(id, { comment: '批量通过' })
      : await returnOrientationMaterial(id, { reason })
    if (res.code !== 0) return res
  }
  return envelope({ count: ids.length })
}

/* ---------------- 宿舍入住 ---------------- */
export async function getDormitoryCheckinList(params = {}) {
  return callList('/orientation/dorms', params)
}

export async function updateDormInfo(id, payload) {
  return callData(() => request(`/orientation/dorms/${id}`, { method: 'PUT', body: payload }))
}

export async function batchConfirmCheckin(ids = []) {
  return callData(() => request('/orientation/dorms/confirm', { method: 'POST', body: { ids } }))
}

export async function markDormException(id, { note }) {
  return callData(() => request(`/orientation/dorms/${id}/exception`, { method: 'POST', body: { note } }))
}

/* ---------------- 异常学生 ---------------- */
export async function getExceptionStudents(params = {}) {
  return callList('/orientation/exceptions', params)
}

export async function getExceptionDetail(id) {
  return callData(() => request(`/orientation/exceptions/${id}`))
}

export async function addExceptionFollowUp(id, payload) {
  return callData(() => request(`/orientation/exceptions/${id}/followup`, { method: 'POST', body: payload }))
}

export async function updateExceptionFollowUp() {
  return fail('编辑异常跟进能力未配置，操作已禁用', 400003)
}

export async function resolveException(id, { note = '' } = {}) {
  return callData(() => request(`/orientation/exceptions/${id}/resolve`, { method: 'POST', body: { note } }))
}

export async function escalateException(id, { reason }) {
  return callData(() => request(`/orientation/exceptions/${id}/escalate`, { method: 'POST', body: { reason } }))
}

/* ---------------- 导入 / 导出（真实通用域端点） ---------------- */
export async function downloadImportTemplate(listKey) {
  if (listKey !== 'studentList') return fail('当前列表未配置导入模板', 400001)
  return callData(() => request('/import/domain/orientation/template'))
}

export async function validateImport(listKey, file) {
  if (listKey !== 'studentList') return fail('当前列表未配置导入能力', 400001)
  if (!file) return fail('请选择 .xlsx 文件', 400001)
  return callData(async () => {
    const data = await requestUpload('/import/domain/orientation/validate-file', file)
    return {
      batchNo: data.batchNo,
      status: data.status,
      total: Number(data.totalRows || 0),
      validCount: Number(data.okRows || 0),
      errorCount: Number(data.errorRows || 0),
      canConfirm: data.status === 'DRY_RUN_PASSED' && Number(data.okRows || 0) > 0,
      errorWorkbookUrl: data.errorWorkbookUrl || '',
      rows: (data.errors || []).map((row) => ({
        row: row.rowIndex,
        data: `${row.field || '字段'}：${row.rawValue ?? ''}`,
        valid: false,
        error: row.message || '校验失败'
      }))
    }
  })
}

export async function confirmImport(listKey, payload = {}) {
  if (listKey !== 'studentList') return fail('当前列表未配置导入能力', 400001)
  if (!payload.batchNo) return fail('导入批次不存在，请重新上传校验', 400001)
  return callData(async () => {
    const idempotencyKey = globalThis.crypto?.randomUUID?.() || `orientation-import-${Date.now()}`
    const data = await request('/import/domain/confirm', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: { domain: 'orientation', batchNo: payload.batchNo }
    })
    return {
      ...data,
      imported: Number(data.insertedRows || 0),
      receiptId: data.batchNo || payload.batchNo
    }
  })
}

export async function createExport(listKey, payload = {}) {
  if (!payload.auditConfirmed) return fail('请先勾选导出审计确认')
  const reportTypes = {
    studentList: 'students', orientationStudents: 'students', progressList: 'progress', materialList: 'materials',
    paymentList: 'payment', greenChannelList: 'green-channel', dormList: 'dorm',
    exceptionList: 'exceptions', noShowList: 'no-show', checkinList: 'checkin'
  }
  const reportType = reportTypes[listKey]
  if (!reportType) return fail('当前列表未配置生产台账导出', 400001)
  const purpose = String(payload.purpose || '').trim()
  if (purpose.length < 5) return fail('导出用途必填且不少于 5 个字', 400001)
  return callData(async () => {
    let batchId = payload.batchId
    if (!batchId) {
      const batches = await request('/orientation/batches', { params: { status: 'ACTIVE', page: 1, pageSize: 1 } })
      batchId = batches?.items?.[0]?.id
    }
    if (!batchId) throw new Error('当前没有进行中的迎新批次，无法生成批次台账')
    const idempotencyKey = globalThis.crypto?.randomUUID?.() || `orientation-export-${Date.now()}`
    const data = await request('/export/domain/orientation', {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: { purpose, batchId, reportType }
    })
    return {
      ...data,
      downloadUrl: `/api/v1/export/tasks/${data.taskId}/download`,
      watermarkText: '服务端首行水印（学校、操作人、时间、用途）',
      auditId: data.taskId
    }
  })
}

/* ---------------- 审计 ---------------- */
export async function getAuditLogs(params = {}) {
  return callList('/orientation/audit-logs', params)
}

/* ---------------- 迎新批次 ---------------- */
export async function getOrientationBatches(params = {}) {
  return callList('/orientation/batches', params)
}

export async function createOrientationBatch(payload = {}) {
  return callData(() => request('/orientation/batches', { method: 'POST', body: payload }))
}

export async function updateOrientationBatch(id, payload = {}) {
  return callData(() => request(`/orientation/batches/${id}`, { method: 'PUT', body: payload }))
}

export async function activateOrientationBatch(id) {
  return callData(() => request(`/orientation/batches/${id}/activate`, { method: 'POST' }))
}

export async function assignOrientationBatchStudentNumbers(id, payload = {}) {
  return callData(() => request(`/orientation/batches/${id}/student-numbers/assign`, { method: 'POST', body: payload }))
}

export async function closeOrientationBatch(id) {
  return callData(() => request(`/orientation/batches/${id}/close`, { method: 'POST' }))
}

export async function voidOrientationBatch(id, reason) {
  return callData(() => request(`/orientation/batches/${id}/void`, { method: 'POST', body: { reason } }))
}

/* ---------------- 现场报到点 / 流程 / 通知 / 归档 ---------------- */
export async function getCheckinPoints(params = {}) {
  return callList('/orientation/checkin-points', params)
}

export async function createCheckinPoint(payload) {
  return callData(() => request('/orientation/checkin-points', { method: 'POST', body: payload }))
}

export async function updateCheckinPoint(id, payload) {
  return callData(() => request(`/orientation/checkin-points/${id}`, { method: 'PUT', body: payload }))
}

export async function toggleCheckinPoint(id) {
  return callData(() => request(`/orientation/checkin-points/${id}/toggle`, { method: 'POST' }))
}

export async function deleteCheckinPoint(id) {
  return callData(() => request(`/orientation/checkin-points/${id}/delete`, { method: 'POST' }))
}

export async function getFlowConfig() {
  return callData(() => request('/orientation/flow-config'))
}

export async function updateFlowConfig(id, payload) {
  return callData(() => request(`/orientation/flow-config/${id}`, { method: 'PUT', body: payload }))
}

export async function getNoticeTasks(params = {}) {
  return callList('/orientation/notices', params)
}

export async function createNoticeTask(payload) {
  return callData(() => request('/orientation/notices', { method: 'POST', body: payload }))
}

export async function sendNoticeTask(id) {
  return callData(() => request(`/orientation/notices/${id}/send`, { method: 'POST' }))
}

export async function getArchives(params = {}) {
  return callList('/orientation/archives', params)
}

export async function createArchive(payload) {
  return callData(() => request('/orientation/archives', { method: 'POST', body: payload }))
}

export async function runArchive(id) {
  return callData(() => request(`/orientation/archives/${id}/run`, { method: 'POST' }))
}
