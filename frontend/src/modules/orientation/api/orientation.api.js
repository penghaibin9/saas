/**
 * 02 数字迎新中心 API（生产级：业务数据仅走真实后端，不回退 mock）。
 * 展示层元数据（角色/字典/列配置）来自 orientation.meta，非业务假数据。
 */
import * as meta from '@/modules/orientation/constants/orientation.meta'
import { request } from '@/services/http/client'
import { enrichContext } from '@/services/http/adapters'

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

const currentRole = () => meta.roles.find((r) => r.roleId === meta.state.currentRoleId) || meta.roles[0]
const rolePerm = () => meta.permissionActionsByRole[meta.state.currentRoleId] || meta.permissionActionsByRole.ORI_TEACHER

function buildPermissionActions() {
  const conf = rolePerm()
  const hidden = conf.hidden || []
  return Object.fromEntries(
    Object.entries(conf.actions).map(([key, allowed]) => [
      key,
      { allowed, visible: !hidden.includes(key), reason: allowed ? '' : conf.disabledReason || '当前角色无此操作权限' }
    ])
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

/* ---------------- 上下文 / 字典（展示层元数据） ---------------- */
export async function getOrientationContext() {
  const role = currentRole()
  const localContext = envelope({
    tenantBrandConfig: clone(meta.tenantBrandConfig),
    currentRole: clone(role),
    roles: clone(meta.roles),
    dataScope: clone(role.dataScope),
    permissionActions: buildPermissionActions()
  })
  try {
    return await enrichContext(localContext)
  } catch {
    // 展示元数据可以降级；真实业务接口仍由后端权限校验兜底。
    return localContext
  }
}

export async function switchOrientationRole(roleId) {
  if (!meta.roles.some((r) => r.roleId === roleId)) return fail('角色不存在')
  meta.state.currentRoleId = roleId
  return getOrientationContext()
}

export async function getStatusOptions() {
  return envelope(clone(meta.statusOptions))
}
export async function getFilterOptions() {
  return envelope(clone(meta.filterOptions))
}
export async function getRegistrationSteps() {
  return envelope(clone(meta.registrationSteps))
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
  return fail('批量提醒待接入真实后端', 501001)
}

export async function batchAssignCounselor() {
  return fail('批量分配辅导员待接入真实后端', 501001)
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

export async function getGreenChannelApplications(params = {}) {
  return callList('/orientation/green-channels', params)
}

export async function approveGreenChannel(id, { remark = '' } = {}) {
  return callData(() => request(`/orientation/green-channels/${id}/approve`, { method: 'POST', body: { remark } }))
}

export async function rejectGreenChannel(id, { reason }) {
  return callData(() => request(`/orientation/green-channels/${id}/reject`, { method: 'POST', body: { reason } }))
}

export async function returnGreenChannel(id, { reason }) {
  return callData(() => request(`/orientation/green-channels/${id}/return`, { method: 'POST', body: { reason } }))
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
  return fail('编辑异常跟进待接入真实后端', 501001)
}

export async function resolveException(id, { note = '' } = {}) {
  return callData(() => request(`/orientation/exceptions/${id}/resolve`, { method: 'POST', body: { note } }))
}

export async function escalateException(id, { reason }) {
  return callData(() => request(`/orientation/exceptions/${id}/escalate`, { method: 'POST', body: { reason } }))
}

/* ---------------- 导入 / 导出（待后端） ---------------- */
export async function validateImport() {
  return fail('导入功能待接入真实后端', 501001)
}

export async function confirmImport() {
  return fail('导入功能待接入真实后端', 501001)
}

export async function createExport(listKey, payload = {}) {
  if (!payload.auditConfirmed) return fail('请先勾选导出审计确认')
  return fail(`导出功能（${listKey}）待接入真实后端`, 501001)
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
