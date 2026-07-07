/**
 * 02 数字迎新中心 — mock API（页面唯一数据入口，接真实后端时仅替换本文件实现）。
 * 返回 envelope：{ code, message, data, timestamp, requestId }
 * 所有写操作真实变更内存 mock 并写入审计日志；删除一律逻辑作废。
 * 数据范围：辅导员(CLASS)本班 / 学院角色(COLLEGE)本院 / 宿管(POINT)本楼栋 / SCHOOL 全部。
 */
import * as db from '@/mocks/orientation/orientation.mock'
import { maskPhone, maskIdCard } from '@/security'
import { request, shouldTryReal } from '@/services/http/client'

const delay = (ms = 160) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `ori-mock-${Date.now()}-${++seq}`
})
const fail = (message, code = 1) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))
const kw = (t, k) => !k || String(t || '').includes(k)

/* ---------------- 上下文 ---------------- */
const currentRole = () => db.roles.find((r) => r.roleId === db.state.currentRoleId) || db.roles[0]
const rolePerm = () => db.permissionActionsByRole[db.state.currentRoleId] || db.permissionActionsByRole.ORI_TEACHER

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

export async function getOrientationContext() {
  await delay(80)
  const role = currentRole()
  return envelope({
    tenantBrandConfig: clone(db.tenantBrandConfig),
    currentRole: clone(role),
    roles: clone(db.roles),
    dataScope: clone(role.dataScope),
    permissionActions: buildPermissionActions()
  })
}

export async function switchOrientationRole(roleId) {
  await delay(60)
  if (!db.roles.some((r) => r.roleId === roleId)) return fail('角色不存在')
  db.state.currentRoleId = roleId
  return getOrientationContext()
}

/* ---------------- 数据范围过滤 ---------------- */
function scopeFilter(list) {
  const role = currentRole()
  if (role.dataScope.code === 'CLASS') return list.filter((s) => ['NCL01', 'NCL02'].includes(s.classId))
  if (role.dataScope.code === 'COLLEGE') return list.filter((s) => s.collegeId === 'C01')
  if (role.dataScope.code === 'POINT') return list.filter((s) => s.building)
  return list
}

/* ---------------- 审计 ---------------- */
function pushAudit(bizType, bizId, action, detail, before = '', after = '') {
  const role = currentRole()
  db.auditLogs.unshift({
    id: `ori-a-${Date.now()}-${++seq}`,
    time: db.nowText(),
    operator: `${role.roleName}（演示账号）`,
    roleName: role.roleName,
    bizType,
    bizId,
    action,
    detail,
    before,
    after
  })
}

/* ---------------- 字典 / 配置 ---------------- */
export async function getStatusOptions() {
  await delay(40)
  return envelope(clone(db.statusOptions))
}
export async function getFilterOptions() {
  await delay(40)
  return envelope(clone(db.filterOptions))
}
export async function getRegistrationSteps() {
  await delay(40)
  return envelope(clone(db.registrationSteps))
}
export async function getFieldColumns(listKey) {
  await delay(40)
  return envelope(clone(db.fieldColumns[listKey] || []))
}
export async function getBatchActions(listKey) {
  await delay(40)
  return envelope(clone(db.batchActions[listKey] || []))
}
export async function getImportTemplate(key) {
  await delay(40)
  return envelope(clone(db.importTemplates[key] || null))
}
export async function getExportOptions(listKey) {
  await delay(40)
  return envelope({
    scopes: clone(db.exportOptions.scopes),
    fieldGroups: clone(db.exportOptions.fieldGroups[listKey] || []),
    maskDefault: db.exportOptions.maskDefault,
    idCardPlainForbidden: db.exportOptions.idCardPlainForbidden,
    watermarkNote: db.exportOptions.watermarkNote,
    auditNotice: db.exportOptions.auditNotice
  })
}

/* ---------------- 看板 ---------------- */
export async function getOrientationDashboard() {
  if (shouldTryReal()) {
    try { return envelope(await request('/orientation/dashboard')) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  return envelope(clone(db.dashboardSummary))
}

/* ---------------- 新生台账 ---------------- */
function maskStudent(s) {
  return { ...s, phone: maskPhone(s.phone), idCard: maskIdCard(s.idCard) }
}

export async function getOrientationStudents(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/students', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', classId = '', stage = '', reportStatus = '', paymentStatus = '', riskLevel = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.orientationStudents)
  list = list.filter(
    (s) =>
      (kw(s.name, keyword) || kw(s.admissionNo, keyword)) &&
      (!classId || s.classId === classId) &&
      (!stage || s.stage === stage) &&
      (!reportStatus || s.reportStatus === reportStatus) &&
      (!paymentStatus || s.paymentStatus === paymentStatus) &&
      (!riskLevel || s.riskLevel === riskLevel)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskStudent), total, page, pageSize })
}

export async function getOrientationStudentDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/students/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('新生记录不存在')
  const greenChannels = db.greenChannelApplications.filter((g) => g.studentId === id)
  const materials = db.materialReviewList.filter((m) => m.studentId === id)
  const exceptions = db.exceptionStudents.filter((e) => e.studentId === id)
  const audits = db.auditLogs.filter(
    (a) => a.bizId === id || greenChannels.some((g) => g.id === a.bizId) || materials.some((m) => m.id === a.bizId) || exceptions.some((e) => e.id === a.bizId)
  )
  return envelope({
    student: maskStudent(clone(s)),
    steps: clone(db.registrationSteps),
    greenChannels: clone(greenChannels),
    materials: clone(materials),
    exceptions: clone(exceptions),
    auditLogs: clone(audits)
  })
}

export async function createOrientationStudent(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/orientation/students', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.name || !payload?.admissionNo) return fail('姓名与录取编号为必填项')
  const id = `ori-s-${Date.now()}`
  const record = {
    id,
    studentId: id,
    gender: '—',
    collegeId: 'C01',
    collegeName: db.filterOptions.colleges[0].label,
    majorName: payload.majorName || '—',
    classId: payload.classId || 'NCL01',
    className: db.filterOptions.classes.find((c) => c.value === (payload.classId || 'NCL01'))?.label || '',
    grade: '2026级',
    phone: payload.phone || '',
    idCard: payload.idCard || '',
    origin: payload.origin || '',
    stage: 'ADMITTED',
    reportStatus: 'NOT_REPORTED',
    paymentStatus: 'UNPAID',
    greenChannelStatus: 'NOT_APPLIED',
    materialStatus: 'NOT_UPLOADED',
    dormStatus: 'UNASSIGNED',
    building: '',
    room: '',
    riskLevel: 'LOW',
    recordStatus: 'ACTIVE',
    voidReason: '',
    counselor: payload.counselor || '—',
    steps: { ACTIVATE: 'TODO', INFO: 'TODO', MATERIAL: 'TODO', PAYMENT: 'TODO', DORM: 'TODO', CHECKIN: 'TODO', CONFIRM: 'TODO' },
    blockedStep: '',
    blockedReason: '',
    payableAmount: 8600,
    paidAmount: 0,
    checkinTime: '',
    exceptionNote: '',
    updateTime: db.nowText(),
    ...payload
  }
  db.orientationStudents.unshift(record)
  pushAudit('STUDENT', id, '新增新生记录', `${record.name}（${record.admissionNo}）`, '', 'ADMITTED')
  return envelope({ id })
}

export async function updateOrientationStudent(id, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/students/${id}`, { method: 'PUT', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  const before = s.reportStatus
  Object.assign(s, payload, { updateTime: db.nowText() })
  pushAudit('STUDENT', id, '编辑报到信息', `${s.name} 报到信息更新`, before, s.reportStatus)
  return envelope({ id })
}

export async function voidOrientationStudent(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/students/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  s.recordStatus = 'VOIDED'
  s.voidReason = reason
  s.updateTime = db.nowText()
  pushAudit('STUDENT', id, '作废报到记录', `${s.name}：${reason}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

export async function verifyOrientationStudent(id, { passed = true, reason = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/students/${id}/verify`, { method: 'POST', body: { passed, reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  if (!passed && (!reason || reason.trim().length < 5)) return fail('核验不通过原因不少于 5 个字')
  if (passed) {
    s.stage = 'PRE_STUDENT_VERIFIED'
    s.steps = { ...(s.steps || {}), INFO: 'DONE' }
    pushAudit('STUDENT', id, '信息核验通过', s.name, 'ADMITTED', 'PRE_STUDENT_VERIFIED')
  } else {
    s.exceptionNote = reason
    pushAudit('STUDENT', id, '信息核验不通过', `${s.name}：${reason}`)
  }
  s.updateTime = db.nowText()
  return envelope({ id, stage: s.stage })
}

export async function batchRemindStudents(ids = [], scene = '报到提醒') {
  await delay()
  pushAudit('STUDENT', ids.join(','), '批量提醒', `向 ${ids.length} 名新生发送${scene}`)
  return envelope({ count: ids.length })
}

export async function batchAssignCounselor(ids = [], { counselor }) {
  await delay()
  if (!counselor) return fail('请输入辅导员姓名')
  ids.forEach((id) => {
    const s = db.orientationStudents.find((x) => x.id === id)
    if (s) {
      s.counselor = counselor
      s.updateTime = db.nowText()
    }
  })
  pushAudit('STUDENT', ids.join(','), '批量分配辅导员', `${ids.length} 名新生分配给 ${counselor}`)
  return envelope({ count: ids.length })
}

/* ---------------- 报到进度 ---------------- */
export async function getRegistrationProgress(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/progress', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', blockedOnly = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.orientationStudents).filter((s) => s.recordStatus === 'ACTIVE')
  list = list.filter((s) => (kw(s.name, keyword) || kw(s.admissionNo, keyword)) && (!blockedOnly || (blockedOnly === 'YES' ? !!s.blockedStep : !s.blockedStep)))
  const total = list.length
  const start = (page - 1) * pageSize
  const rows = clone(list.slice(start, start + pageSize)).map((s) => {
    const doneCount = Object.values(s.steps || {}).filter((v) => v === 'DONE').length
    return {
      ...maskStudent(s),
      progress: `${doneCount}/${db.registrationSteps.length}`,
      blockedStepLabel: db.registrationSteps.find((st) => st.key === s.blockedStep)?.label || ''
    }
  })
  return envelope({ list: rows, total, page, pageSize, steps: clone(db.registrationSteps) })
}

export async function updateBlockedIssue(id, { blockedStep, blockedReason }) {
  if (shouldTryReal()) {
    try {
      return envelope(await request(`/orientation/progress/${id}/blocked`, {
        method: 'PUT',
        body: { blockedStep, blockedReason }
      }))
    } catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  const before = s.blockedStep
  s.blockedStep = blockedStep || ''
  s.blockedReason = blockedReason || ''
  if (blockedStep) s.steps[blockedStep] = 'BLOCKED'
  s.updateTime = db.nowText()
  pushAudit('PROGRESS', id, '编辑卡点事项', `${s.name}：${blockedReason || '清除卡点'}`, before, blockedStep || '')
  return envelope({ id })
}

export async function resolveBlockedIssue(id, { note = '' } = {}) {
  if (shouldTryReal()) {
    try {
      return envelope(await request(`/orientation/progress/${id}/resolve`, { method: 'POST', body: { note } }))
    } catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  const before = s.blockedStep
  if (s.blockedStep && s.steps[s.blockedStep]) s.steps[s.blockedStep] = 'DONE'
  s.blockedStep = ''
  s.blockedReason = ''
  s.updateTime = db.nowText()
  pushAudit('PROGRESS', id, '标记人工已处理', `${s.name} 卡点已人工处理${note ? '：' + note : ''}`, before, '')
  return envelope({ id })
}

/* ---------------- 缴费 / 绿色通道 ---------------- */
export async function getPaymentStatusList(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/payments', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', paymentStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.orientationStudents).filter((s) => s.recordStatus === 'ACTIVE')
  list = list.filter((s) => (kw(s.name, keyword) || kw(s.admissionNo, keyword)) && (!paymentStatus || s.paymentStatus === paymentStatus))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({
    list: clone(list.slice(start, start + pageSize)).map((s) => ({
      ...maskStudent(s),
      payableAmount: `¥${s.payableAmount}`,
      paidAmount: `¥${s.paidAmount}`
    })),
    total,
    page,
    pageSize
  })
}

export async function getGreenChannelApplications(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/green-channels', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', status = '', page = 1, pageSize = 10 } = params
  const scopedIds = new Set(scopeFilter(db.orientationStudents).map((s) => s.id))
  let list = db.greenChannelApplications.filter(
    (g) => scopedIds.has(g.studentId) && (kw(g.name, keyword) || kw(g.applyType, keyword)) && (!status || g.status === status)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function approveGreenChannel(id, { remark = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/green-channels/${id}/approve`, { method: 'POST', body: { remark } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.greenChannelApplications.find((x) => x.id === id)
  if (!g) return fail('申请不存在')
  const before = g.status
  const role = currentRole()
  Object.assign(g, { status: 'APPROVED', reviewer: role.roleName, reviewTime: db.nowText(), rejectReason: '', remark: remark || g.remark })
  const s = db.orientationStudents.find((x) => x.id === g.studentId)
  if (s) {
    s.greenChannelStatus = 'APPROVED'
    if (s.paymentStatus === 'UNPAID' || s.paymentStatus === 'PARTIAL') s.paymentStatus = 'GREEN_CHANNEL'
    if (s.blockedStep === 'PAYMENT') {
      s.steps.PAYMENT = 'DONE'
      s.blockedStep = ''
      s.blockedReason = ''
    }
    s.updateTime = db.nowText()
  }
  pushAudit('GREEN_CHANNEL', id, '审核通过', `批准 ${g.name} ${g.applyType}（¥${g.applyAmount}）${remark ? ' · ' + remark : ''}`, before, 'APPROVED')
  return envelope({ id })
}

export async function rejectGreenChannel(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/green-channels/${id}/reject`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.greenChannelApplications.find((x) => x.id === id)
  if (!g) return fail('申请不存在')
  if (!reason || reason.trim().length < 5) return fail('驳回原因不少于 5 个字')
  const before = g.status
  const role = currentRole()
  Object.assign(g, { status: 'REJECTED', reviewer: role.roleName, reviewTime: db.nowText(), rejectReason: reason })
  const s = db.orientationStudents.find((x) => x.id === g.studentId)
  if (s) {
    s.greenChannelStatus = 'REJECTED'
    s.updateTime = db.nowText()
  }
  pushAudit('GREEN_CHANNEL', id, '驳回申请', `驳回 ${g.name} ${g.applyType}：${reason}`, before, 'REJECTED')
  return envelope({ id })
}

export async function returnGreenChannel(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/green-channels/${id}/return`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.greenChannelApplications.find((x) => x.id === id)
  if (!g) return fail('申请不存在')
  if (!reason || reason.trim().length < 5) return fail('退回原因不少于 5 个字')
  const before = g.status
  const role = currentRole()
  Object.assign(g, { status: 'RETURNED', reviewer: role.roleName, reviewTime: db.nowText(), rejectReason: reason })
  const s = db.orientationStudents.find((x) => x.id === g.studentId)
  if (s) {
    s.greenChannelStatus = 'RETURNED'
    s.updateTime = db.nowText()
  }
  pushAudit('GREEN_CHANNEL', id, '退回补充', `退回 ${g.name} ${g.applyType}：${reason}`, before, 'RETURNED')
  return envelope({ id })
}

/* ---------------- 材料审核 ---------------- */
export async function getMaterialReviewList(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/materials', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', status = '', materialType = '', page = 1, pageSize = 10 } = params
  const scopedIds = new Set(scopeFilter(db.orientationStudents).map((s) => s.id))
  let list = db.materialReviewList.filter(
    (m) => scopedIds.has(m.studentId) && (kw(m.name, keyword) || kw(m.fileName, keyword)) && (!status || m.status === status) && (!materialType || m.materialType === materialType)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function approveOrientationMaterial(id, { comment = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/materials/${id}/approve`, { method: 'POST', body: { comment } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const m = db.materialReviewList.find((x) => x.id === id)
  if (!m) return fail('材料不存在')
  const before = m.status
  const role = currentRole()
  Object.assign(m, { status: 'APPROVED', reviewer: role.roleName, reviewTime: db.nowText(), returnReason: '' })
  const s = db.orientationStudents.find((x) => x.id === m.studentId)
  if (s) {
    const pendings = db.materialReviewList.filter((x) => x.studentId === s.id && x.status !== 'APPROVED')
    s.materialStatus = pendings.length ? s.materialStatus : 'APPROVED'
    if (s.blockedStep === 'MATERIAL' && !pendings.length) {
      s.steps.MATERIAL = 'DONE'
      s.blockedStep = ''
      s.blockedReason = ''
    }
    s.updateTime = db.nowText()
  }
  pushAudit('MATERIAL', id, '审核通过', `通过《${m.fileName}》${comment ? ' · ' + comment : ''}`, before, 'APPROVED')
  return envelope({ id })
}

export async function returnOrientationMaterial(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/materials/${id}/return`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const m = db.materialReviewList.find((x) => x.id === id)
  if (!m) return fail('材料不存在')
  if (!reason || reason.trim().length < 5) return fail('退回原因不少于 5 个字')
  const before = m.status
  const role = currentRole()
  Object.assign(m, { status: 'RETURNED', reviewer: role.roleName, reviewTime: db.nowText(), returnReason: reason })
  const s = db.orientationStudents.find((x) => x.id === m.studentId)
  if (s) {
    s.materialStatus = 'RETURNED'
    s.updateTime = db.nowText()
  }
  pushAudit('MATERIAL', id, '退回材料', `退回《${m.fileName}》：${reason}`, before, 'RETURNED')
  return envelope({ id })
}

export async function batchReviewOrientationMaterials(ids = [], { pass, reason = '' }) {
  await delay()
  if (!pass && (!reason || reason.trim().length < 5)) return fail('批量退回必须填写原因（不少于 5 个字）')
  for (const id of ids) {
    if (pass) await approveOrientationMaterial(id, { comment: '批量通过' })
    else await returnOrientationMaterial(id, { reason })
  }
  pushAudit('MATERIAL', ids.join(','), pass ? '批量通过材料' : '批量退回材料', `${ids.length} 份材料${pass ? '通过' : `退回：${reason}`}`)
  return envelope({ count: ids.length })
}

/* ---------------- 宿舍入住 ---------------- */
export async function getDormitoryCheckinList(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/dorms', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', dormStatus = '', building = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.orientationStudents).filter((s) => s.recordStatus === 'ACTIVE')
  const buildingLabel = db.filterOptions.buildings.find((b) => b.value === building)?.label || ''
  list = list.filter(
    (s) => (kw(s.name, keyword) || kw(s.room, keyword)) && (!dormStatus || s.dormStatus === dormStatus) && (!building || s.building === buildingLabel)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskStudent), total, page, pageSize })
}

export async function updateDormInfo(id, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/dorms/${id}`, { method: 'PUT', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  const before = `${s.building} ${s.room}`
  Object.assign(s, payload, { updateTime: db.nowText() })
  if (payload.building || payload.room) s.dormStatus = s.dormStatus === 'UNASSIGNED' ? 'ASSIGNED' : s.dormStatus
  pushAudit('DORM', id, '编辑宿舍信息', `${s.name}：${before || '未分配'} → ${s.building} ${s.room}`, before, `${s.building} ${s.room}`)
  return envelope({ id })
}

export async function batchConfirmCheckin(ids = []) {
  if (shouldTryReal()) {
    try { return envelope(await request('/orientation/dorms/confirm', { method: 'POST', body: { ids } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  ids.forEach((id) => {
    const s = db.orientationStudents.find((x) => x.id === id)
    if (s && s.dormStatus !== 'EXCEPTION') {
      s.dormStatus = 'CHECKED_IN'
      s.checkinTime = s.checkinTime || db.nowText()
      s.steps.DORM = 'DONE'
      s.updateTime = db.nowText()
    }
  })
  pushAudit('DORM', ids.join(','), '批量确认入住', `批量确认 ${ids.length} 名新生宿舍入住`)
  return envelope({ count: ids.length })
}

export async function markDormException(id, { note }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/dorms/${id}/exception`, { method: 'POST', body: { note } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.orientationStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  if (!note || note.trim().length < 5) return fail('异常说明不少于 5 个字')
  const before = s.dormStatus
  s.dormStatus = 'EXCEPTION'
  s.exceptionNote = note
  s.updateTime = db.nowText()
  pushAudit('DORM', id, '标记入住异常', `${s.name}：${note}`, before, 'EXCEPTION')
  return envelope({ id })
}

/* ---------------- 迎新异常 ---------------- */
export async function getExceptionStudents(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/exceptions', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', exceptionType = '', status = '', riskLevel = '', page = 1, pageSize = 10 } = params
  const scopedIds = new Set(scopeFilter(db.orientationStudents).map((s) => s.id))
  let list = db.exceptionStudents.filter(
    (e) =>
      scopedIds.has(e.studentId) &&
      (kw(e.name, keyword) || kw(e.description, keyword)) &&
      (!exceptionType || e.exceptionType === exceptionType) &&
      (!status || e.status === status) &&
      (!riskLevel || e.riskLevel === riskLevel)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getExceptionDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/exceptions/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const e = db.exceptionStudents.find((x) => x.id === id)
  if (!e) return fail('异常记录不存在')
  const student = db.orientationStudents.find((s) => s.id === e.studentId)
  const audits = db.auditLogs.filter((a) => a.bizId === id || a.bizId === e.studentId)
  return envelope({ exception: clone(e), student: student ? maskStudent(clone(student)) : null, auditLogs: clone(audits) })
}

export async function addExceptionFollowUp(id, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/exceptions/${id}/followup`, { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const e = db.exceptionStudents.find((x) => x.id === id)
  if (!e) return fail('异常记录不存在')
  if (!payload?.content) return fail('跟进内容为必填项')
  const role = currentRole()
  const fid = `ori-ef-${Date.now()}`
  e.followUps.unshift({
    id: fid,
    followTime: db.nowText(),
    way: payload.way || 'PHONE',
    content: payload.content,
    operator: `${role.roleName}（演示账号）`,
    status: 'ACTIVE',
    voidReason: ''
  })
  e.lastFollowTime = db.nowText()
  if (e.status === 'OPEN') e.status = 'PROCESSING'
  pushAudit('EXCEPTION', id, '新增跟进', `${e.name}：${payload.content}`)
  return envelope({ id: fid })
}

export async function updateExceptionFollowUp(id, followId, payload) {
  await delay()
  const e = db.exceptionStudents.find((x) => x.id === id)
  if (!e) return fail('异常记录不存在')
  const f = e.followUps.find((x) => x.id === followId)
  if (!f) return fail('跟进记录不存在')
  Object.assign(f, payload)
  pushAudit('EXCEPTION', id, '编辑跟进', `${e.name} 跟进记录更新`)
  return envelope({ id: followId })
}

export async function resolveException(id, { note = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/exceptions/${id}/resolve`, { method: 'POST', body: { note } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const e = db.exceptionStudents.find((x) => x.id === id)
  if (!e) return fail('异常记录不存在')
  const before = e.status
  e.status = 'RESOLVED'
  e.lastFollowTime = db.nowText()
  const s = db.orientationStudents.find((x) => x.id === e.studentId)
  if (s && s.riskLevel === 'HIGH') s.riskLevel = 'MEDIUM'
  pushAudit('EXCEPTION', id, '标记已处理', `${e.name} 异常已处理${note ? '：' + note : ''}`, before, 'RESOLVED')
  return envelope({ id })
}

export async function escalateException(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/exceptions/${id}/escalate`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const e = db.exceptionStudents.find((x) => x.id === id)
  if (!e) return fail('异常记录不存在')
  if (!reason || reason.trim().length < 5) return fail('升级说明不少于 5 个字')
  const before = e.status
  e.status = 'ESCALATED'
  e.riskLevel = 'HIGH'
  const s = db.orientationStudents.find((x) => x.id === e.studentId)
  if (s) s.riskLevel = 'HIGH'
  pushAudit('EXCEPTION', id, '升级风险', `${e.name}：${reason}`, before, 'ESCALATED')
  return envelope({ id })
}

/* ---------------- 导入 / 导出 ---------------- */
export async function validateImport(templateKey, fileName = '') {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  const rows = [
    { row: 2, data: 'LQ2026010013 / 沈心怡 / 3301022008xxxx / 软件技术', valid: true, error: '' },
    { row: 3, data: 'LQ2026010014 / 韩子墨 / 3301022007xxxx / 软件技术', valid: true, error: '' },
    { row: 4, data: 'LQ2026010015 / （空姓名） / 3301022009xxxx / 大数据技术', valid: false, error: '姓名为必填项' },
    { row: 5, data: 'LQ2026010013 / 重复编号 / 3301022006xxxx / 软件技术', valid: false, error: '录取编号与第 2 行重复' }
  ]
  return envelope({ fileName: fileName || tpl.fileName, total: rows.length, validCount: rows.filter((r) => r.valid).length, rows })
}

export async function confirmImport(templateKey, { validCount = 0, fileName = '' } = {}) {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  pushAudit('IMPORT', templateKey, '执行导入', `${tpl.name}：导入 ${validCount} 条校验通过数据（${fileName}），失败数据未导入`)
  return envelope({ imported: validCount, skipped: 0, receiptId: `ori-imp-${Date.now()}` })
}

export async function createExport(listKey, payload = {}) {
  await delay(400)
  const role = currentRole()
  if (!payload.auditConfirmed) return fail('请先勾选导出审计确认')
  const masked = payload.mask !== false
  const detail = `导出${listKey}（范围：${payload.scope || 'FILTERED'}；字段组：${(payload.fieldGroups || []).join('/') || '默认'}；${masked ? '敏感字段已脱敏' : '未脱敏'}；含水印）`
  pushAudit('EXPORT', listKey, '导出数据', detail)
  return envelope({
    fileName: `${db.tenantBrandConfig.schoolName}-${listKey}-${Date.now()}.xlsx`,
    masked,
    watermarkText: `${db.tenantBrandConfig.schoolName} · ${role.roleName} · ${db.nowText()}`,
    auditId: db.auditLogs[0].id
  })
}

/* ---------------- 审计日志 ---------------- */
export async function getAuditLogs(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/audit-logs', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { bizType = '', keyword = '', page = 1, pageSize = 20 } = params
  let list = db.auditLogs.filter((a) => (!bizType || a.bizType === bizType) && (kw(a.detail, keyword) || kw(a.operator, keyword)))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

/* ---------------- 迎新批次（真实后端 /orientation/batches；离线兜底 mock） ---------------- */
const _mockBatches = [
  {
    id: 'b1', batchName: '2026 级新生迎新', batchNo: 'ORI-2026', year: '2026',
    startDate: '2026-09-01T00:00:00', endDate: '', reportStartDate: '2026-09-01T00:00:00',
    reportEndDate: '2026-09-15T00:00:00', status: 'ACTIVE', statusLabel: '进行中',
    plannedCount: 3200, remark: '秋季迎新', updateTime: ''
  }
]

export async function getOrientationBatches(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/orientation/batches', { params: params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', status = '', page = 1, pageSize = 20 } = params
  const list = _mockBatches.filter((b) => (kw(b.batchName, keyword) || kw(b.batchNo, keyword)) && (!status || b.status === status))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createOrientationBatch(payload = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request('/orientation/batches', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload.batchName || !payload.batchNo) return fail('批次名称与批次编号必填')
  if (_mockBatches.some((b) => b.batchNo === payload.batchNo)) return fail(`批次编号 ${payload.batchNo} 已存在`)
  const b = { id: 'b' + Date.now(), status: 'DRAFT', statusLabel: '草稿', plannedCount: payload.plannedCount || 0, remark: '', ...payload }
  _mockBatches.unshift(b)
  return envelope({ id: b.id })
}

export async function updateOrientationBatch(id, payload = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/batches/${id}`, { method: 'PUT', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const b = _mockBatches.find((x) => x.id === id)
  if (b) Object.assign(b, payload)
  return envelope({ id: id })
}

export async function activateOrientationBatch(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/batches/${id}/activate`, { method: 'POST' })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const b = _mockBatches.find((x) => x.id === id)
  if (b) { b.status = 'ACTIVE'; b.statusLabel = '进行中' }
  return envelope({ id: id, status: 'ACTIVE' })
}

export async function closeOrientationBatch(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/batches/${id}/close`, { method: 'POST' })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const b = _mockBatches.find((x) => x.id === id)
  if (b) { b.status = 'CLOSED'; b.statusLabel = '已结束' }
  return envelope({ id: id, status: 'CLOSED' })
}

export async function voidOrientationBatch(id, reason) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/orientation/batches/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 字')
  const i = _mockBatches.findIndex((x) => x.id === id)
  if (i >= 0) _mockBatches.splice(i, 1)
  return envelope({ id: id })
}

/* ---------------- 现场报到点 / 流程配置 / 迎新通知 / 迎新归档（真实后端 + 离线兜底） ---------------- */
const _mockPoints = [{ id: 'p1', name: '东门报到点', location: '东大门', capacity: 300, inCharge: '王老师', status: 'ENABLED', statusLabel: '启用', remark: '', updateTime: '' }]
const _mockFlow = [
  { id: 'f1', stepKey: 'ACTIVATE', stepName: '账号激活', enabled: true, required: true, sortOrder: 0 },
  { id: 'f2', stepKey: 'INFO', stepName: '信息核对', enabled: true, required: true, sortOrder: 1 },
  { id: 'f3', stepKey: 'MATERIAL', stepName: '材料上传', enabled: true, required: true, sortOrder: 2 },
  { id: 'f4', stepKey: 'PAYMENT', stepName: '缴费/绿色通道', enabled: true, required: true, sortOrder: 3 },
  { id: 'f5', stepKey: 'DORM', stepName: '宿舍确认', enabled: true, required: true, sortOrder: 4 },
  { id: 'f6', stepKey: 'CHECKIN', stepName: '现场报到', enabled: true, required: true, sortOrder: 5 },
  { id: 'f7', stepKey: 'ARCHIVE', stepName: '归档', enabled: true, required: false, sortOrder: 6 }
]
const _mockNotices = []
const _mockArchives = []
const _list = (arr, params) => {
  const { keyword = '', status = '', page = 1, pageSize = 20 } = params || {}
  let l = arr.filter((x) => (!keyword || (x.name || x.title || x.archiveName || '').includes(keyword)) && (!status || x.status === status))
  const total = l.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(l.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getCheckinPoints(params = {}) {
  if (shouldTryReal()) { try { const d = await request('/orientation/checkin-points', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); return _list(_mockPoints, params)
}
export async function createCheckinPoint(payload) {
  if (shouldTryReal()) { try { return envelope(await request('/orientation/checkin-points', { method: 'POST', body: payload })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); if (!payload.name) return fail('报到点名称必填'); _mockPoints.unshift({ id: 'p' + Date.now(), status: 'ENABLED', statusLabel: '启用', ...payload }); return envelope({ id: 'ok' })
}
export async function updateCheckinPoint(id, payload) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/checkin-points/${id}`, { method: 'PUT', body: payload })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const p = _mockPoints.find((x) => x.id === id); if (p) Object.assign(p, payload); return envelope({ id })
}
export async function toggleCheckinPoint(id) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/checkin-points/${id}/toggle`, { method: 'POST' })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const p = _mockPoints.find((x) => x.id === id); if (p) { p.status = p.status === 'ENABLED' ? 'DISABLED' : 'ENABLED'; p.statusLabel = p.status === 'ENABLED' ? '启用' : '停用' } return envelope({ id, status: p ? p.status : '' })
}
export async function deleteCheckinPoint(id) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/checkin-points/${id}/delete`, { method: 'POST' })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const i = _mockPoints.findIndex((x) => x.id === id); if (i >= 0) _mockPoints.splice(i, 1); return envelope({ id })
}

export async function getFlowConfig() {
  if (shouldTryReal()) { try { return envelope(await request('/orientation/flow-config')) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); return envelope(clone(_mockFlow))
}
export async function updateFlowConfig(id, payload) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/flow-config/${id}`, { method: 'PUT', body: payload })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const f = _mockFlow.find((x) => x.id === id); if (f) Object.assign(f, payload); return envelope({ id, enabled: f ? f.enabled : true })
}

export async function getNoticeTasks(params = {}) {
  if (shouldTryReal()) { try { const d = await request('/orientation/notices', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); return _list(_mockNotices, params)
}
export async function createNoticeTask(payload) {
  if (shouldTryReal()) { try { return envelope(await request('/orientation/notices', { method: 'POST', body: payload })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); if (!payload.title) return fail('通知标题必填'); const ch = payload.channel || 'INAPP'; _mockNotices.unshift({ id: 'n' + Date.now(), status: 'PENDING', statusLabel: '待发送', channelLabel: { INAPP: '站内通知', SMS: '短信', EMAIL: '邮件', MINIAPP: '小程序' }[ch] || ch, sentCount: 0, failReason: '', ...payload, channel: ch }); return envelope({ id: 'ok' })
}
export async function sendNoticeTask(id) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/notices/${id}/send`, { method: 'POST' })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const n = _mockNotices.find((x) => x.id === id); if (n) { if (n.channel === 'INAPP') { n.status = 'SENT'; n.statusLabel = '已发送'; n.sentCount = 1 } else { n.status = 'DISABLED'; n.statusLabel = '渠道未配置'; n.failReason = '该渠道未配置' } } return envelope({ id, status: n ? n.status : '', failReason: n ? n.failReason : '' })
}

export async function getArchives(params = {}) {
  if (shouldTryReal()) { try { const d = await request('/orientation/archives', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); return _list(_mockArchives, params)
}
export async function createArchive(payload) {
  if (shouldTryReal()) { try { return envelope(await request('/orientation/archives', { method: 'POST', body: payload })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); if (!payload.archiveName) return fail('归档名称必填'); _mockArchives.unshift({ id: 'a' + Date.now(), status: 'PENDING', statusLabel: '待归档', itemCount: 0, archivedBy: '', ...payload }); return envelope({ id: 'ok' })
}
export async function runArchive(id) {
  if (shouldTryReal()) { try { return envelope(await request(`/orientation/archives/${id}/run`, { method: 'POST' })) } catch (e) { if (e.biz) return fail(e.message, e.code) } }
  await delay(); const a = _mockArchives.find((x) => x.id === id); if (a) { a.status = 'DONE'; a.statusLabel = '已归档'; a.itemCount = 10 } return envelope({ id, status: 'DONE', itemCount: 10 })
}
