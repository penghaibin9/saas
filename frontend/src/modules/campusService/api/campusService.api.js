/**
 * 03 在校服务中心 — mock API（页面唯一数据入口，接真实后端时仅替换本文件实现）。
 * 契约：
 *  - 返回 envelope：{ code, message, data, timestamp, requestId }，code=0 成功。
 *  - 所有写操作（新增/编辑/作废/审批/退回/分派/办结/批量/导入/导出）真实变更内存 mock 并写入审计日志。
 *  - 删除一律逻辑作废（recordStatus = VOIDED），禁止物理删除；退回类操作原因必填。
 *  - 数据范围：CLASS 本班（CL01/CL02）、COLLEGE 本院（C01）、DORM 所辖楼栋（B3/B5）、SCHOOL 全部。
 *  - 敏感收敛：手机号/身份证脱敏；资助金额区间化；困难材料与心理记录仅授权角色可见且查看留痕。
 */
import * as db from '@/mocks/campusService/campusService.mock'
import { maskPhone, maskIdCard } from '@/security'
import { request, shouldTryReal } from '@/services/http/client'

const delay = (ms = 150) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `svc-mock-${Date.now()}-${++seq}`
})
const fail = (message, code = 1) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))
const kw = (t, k) => !k || String(t || '').includes(k)
/** 旧奖助/违纪页写操作禁止静默回落内存 mock（已迁 13A 正式链路） */
const refuseLegacyMockWrite = (biz) =>
  fail(`${biz}已迁至学工中心正式模块，本页 mock 写操作已关闭；请从学工菜单进入正式工作台`, 410)

/* ---------------- 上下文 ---------------- */
const currentRole = () => db.roles.find((r) => r.roleId === db.state.currentRoleId) || db.roles[0]
const rolePerm = () => db.permissionActionsByRole[db.state.currentRoleId] || db.permissionActionsByRole.COUNSELOR

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

export async function getCampusServiceContext() {
  await delay(80)
  const role = currentRole()
  return envelope({
    tenantBrandConfig: clone(db.tenantBrandConfig),
    currentRole: clone(role),
    roles: clone(db.roles),
    dataScope: clone(role.dataScope),
    permissionActions: buildPermissionActions(),
    statusOptions: clone(db.statusOptions),
    filterOptions: clone(db.filterOptions)
  })
}

export async function switchCampusServiceRole(roleId) {
  await delay(60)
  if (!db.roles.some((r) => r.roleId === roleId)) return fail('角色不存在')
  db.state.currentRoleId = roleId
  return getCampusServiceContext()
}

/* ---------------- 数据范围过滤 ---------------- */
function studentInScope() {
  const role = currentRole()
  if (role.dataScope.code === 'CLASS') return (s) => ['CL01', 'CL02'].includes(s.classId)
  if (role.dataScope.code === 'COLLEGE') return (s) => s.collegeId === 'C01'
  if (role.dataScope.code === 'DORM') return (s) => ['B3', 'B5'].includes(s.buildingId)
  return () => true
}

function scopeStudents(list) {
  return list.filter(studentInScope())
}

function scopeByStudent(list) {
  const inScope = studentInScope()
  const map = new Map(db.serviceStudents.map((s) => [s.id, s]))
  return list.filter((row) => {
    const s = map.get(row.studentId)
    return s ? inScope(s) : false
  })
}

/* ---------------- 审计 ---------------- */
function pushAudit(bizType, bizId, action, detail, before = '', after = '') {
  const role = currentRole()
  db.auditLogs.unshift({
    id: `svc-a-${Date.now()}-${++seq}`,
    time: db.nowText(),
    operator: `${role.userName}（演示账号）`,
    roleName: role.roleName,
    bizType,
    bizId,
    action,
    detail,
    before,
    after
  })
}

/* ---------------- 配置类 ---------------- */
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

/* ---------------- 看板（按数据范围动态计算） ---------------- */
export async function getCampusServiceDashboard() {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/dashboard')) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const students = scopeStudents(db.serviceStudents).filter((s) => s.recordStatus === 'ACTIVE')
  const leaves = scopeByStudent(db.leaveApplications).filter((l) => l.recordStatus === 'ACTIVE')
  const grants = scopeByStudent(db.grantApplications).filter((g) => g.recordStatus === 'ACTIVE')
  const dormEx = scopeByStudent(db.dormitoryExceptionRecords).filter((d) => d.recordStatus === 'ACTIVE')
  const orders = scopeByStudent(db.serviceWorkOrders).filter((w) => w.recordStatus === 'ACTIVE')
  const done = orders.filter((w) => ['COMPLETED', 'CLOSED'].includes(w.status)).length
  const kpis = [
    { key: 'students', label: '在校学生', value: String(students.length), trend: '', trendQuality: 'neutral' },
    { key: 'pendingLeave', label: '待审批请假', value: String(leaves.filter((l) => l.status === 'PENDING_REVIEW').length), trend: '今日新增 2', trendQuality: 'bad' },
    { key: 'pendingGrant', label: '待审核资助', value: String(grants.filter((g) => ['PENDING_REVIEW', 'REVIEWING'].includes(g.status)).length), trend: '', trendQuality: 'neutral' },
    { key: 'dormException', label: '宿舍异常待处理', value: String(dormEx.filter((d) => d.status !== 'COMPLETED').length), trend: '含夜不归宿 1', trendQuality: 'bad' },
    { key: 'workOrders', label: '在办工单', value: String(orders.filter((w) => !['COMPLETED', 'CLOSED'].includes(w.status)).length), trend: '逾期 ' + orders.filter((w) => w.overdue).length, trendQuality: orders.some((w) => w.overdue) ? 'bad' : 'neutral' },
    { key: 'keyCare', label: '重点关怀学生', value: String(students.filter((s) => s.careLevel !== 'NORMAL').length), trend: '', trendQuality: 'neutral' },
    { key: 'doneRate', label: '本月办结率', value: orders.length ? Math.round((done / orders.length) * 100) + '%' : '—', trend: '', trendQuality: 'good' },
    { key: 'satisfaction', label: '学生满意度', value: '4.8 / 5', trend: '近30天评价 23 条', trendQuality: 'good' }
  ]
  return envelope({ ...clone(db.dashboardSummary), kpis })
}

/* ---------------- 在校学生服务台账 ---------------- */
function maskStudent(s) {
  return { ...s, phone: maskPhone(s.phone), idCard: maskIdCard(s.idCard) }
}

export async function getServiceStudents(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/students', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', classId = '', careLevel = '', riskLevel = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeStudents(db.serviceStudents)
  list = list.filter(
    (s) =>
      (kw(s.name, keyword) || kw(s.studentNo, keyword)) &&
      (!classId || s.classId === classId) &&
      (!careLevel || s.careLevel === careLevel) &&
      (!riskLevel || s.riskLevel === riskLevel) &&
      (recordStatus ? s.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskStudent), total, page, pageSize })
}

export async function getStudentServiceDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/students/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.serviceStudents.find((x) => x.id === id)
  if (!s) return fail('学生服务档案不存在，或不在当前数据范围内')
  const canViewMental = buildPermissionActions()['campus.mental.view']
  const leaves = db.leaveApplications.filter((l) => l.studentId === id)
  const grants = db.grantApplications.filter((g) => g.studentId === id)
  const dorm = db.dormitoryRecords.find((d) => d.studentId === id) || null
  const dormExceptions = db.dormitoryExceptionRecords.filter((d) => d.studentId === id)
  const disciplines = db.disciplineRecords.filter((d) => d.studentId === id)
  const mentals = db.mentalHealthRecords
    .filter((m) => m.studentId === id)
    .map((m) => (canViewMental && canViewMental.visible && canViewMental.allowed ? m : { ...m, summary: '（涉密：仅授权角色可见）', counselorNote: '（涉密）' }))
  const orders = db.serviceWorkOrders.filter((w) => w.studentId === id)
  const ids = [id, ...leaves.map((l) => l.id), ...grants.map((g) => g.id), ...disciplines.map((d) => d.id), ...orders.map((w) => w.id)]
  const audits = db.auditLogs.filter((a) => ids.includes(a.bizId))
  if (canViewMental && canViewMental.visible && canViewMental.allowed && mentals.length) {
    pushAudit('MENTAL', id, '查看心理关怀记录', `${s.name} 心理记录被查看（涉密访问留痕）`)
  }
  return envelope({
    student: maskStudent(clone(s)),
    leaves: clone(leaves),
    grants: clone(grants).map(maskGrant),
    dorm: clone(dorm),
    dormExceptions: clone(dormExceptions),
    disciplines: clone(disciplines),
    mentals: clone(mentals),
    workOrders: clone(orders),
    auditLogs: clone(audits)
  })
}

export async function createServiceRecord(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/students', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.name || !payload?.studentNo) return fail('姓名与学号为必填项')
  const id = `svc-s-${Date.now()}`
  const classId = payload.classId || 'CL01'
  const record = {
    id,
    studentId: id,
    gender: '—',
    collegeId: classId === 'CL04' ? 'C02' : 'C01',
    collegeName: classId === 'CL04' ? '智能制造学院' : '信息工程学院',
    majorName: '—',
    grade: '2023级',
    phone: '',
    idCard: '',
    counselor: '—',
    buildingId: 'B3',
    building: db.filterOptions.buildings[0].label,
    room: payload.room || '—',
    leaveCount: 0,
    pendingLeave: 0,
    grantSummary: '无申请',
    disciplineCount: 0,
    workOrderCount: 0,
    mentalFlag: false,
    careLevel: payload.careLevel || 'NORMAL',
    riskLevel: 'LOW',
    recordStatus: 'ACTIVE',
    voidReason: '',
    updateTime: db.nowText(),
    ...payload,
    classId,
    className: db.filterOptions.classes.find((c) => c.value === classId)?.label || ''
  }
  db.serviceStudents.unshift(record)
  pushAudit('RECORD', id, '新增服务记录', `${record.name}（${record.studentNo}）· ${record.className}`, '', 'ACTIVE')
  return envelope({ id })
}

export async function updateServiceRecord(id, payload) {
  await delay()
  const s = db.serviceStudents.find((x) => x.id === id)
  if (!s) return fail('服务记录不存在')
  const before = `宿舍 ${s.building}${s.room}；关怀 ${s.careLevel}`
  Object.assign(s, payload, { updateTime: db.nowText() })
  pushAudit('RECORD', id, '编辑服务信息', `${s.name} 服务信息更新`, before, `宿舍 ${s.building}${s.room}；关怀 ${s.careLevel}`)
  return envelope({ id })
}

export async function voidServiceRecord(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/students/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.serviceStudents.find((x) => x.id === id)
  if (!s) return fail('服务记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  s.recordStatus = 'VOIDED'
  s.voidReason = reason.trim()
  s.updateTime = db.nowText()
  pushAudit('RECORD', id, '作废服务记录', `${s.name}：${reason.trim()}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

export async function batchRemindServiceStudents(ids = [], scene = '在校服务事项') {
  await delay()
  if (!ids.length) return fail('请先选择学生')
  pushAudit('RECORD', ids.join(','), '批量提醒', `向 ${ids.length} 名学生发送「${scene}」提醒（站内信 + 小程序）`)
  return envelope({ count: ids.length })
}

/* ---------------- 请假审批 ---------------- */
export async function getLeaveApplications(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/leaves', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', status = '', classId = '', page = 1, pageSize = 10 } = params
  let list = scopeByStudent(db.leaveApplications)
  list = list.filter(
    (l) =>
      (kw(l.name, keyword) || kw(l.code, keyword)) &&
      (!type || l.type === type) &&
      (!status || l.status === status) &&
      (!classId || l.classId === classId)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getLeaveApplicationDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/leaves/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const l = db.leaveApplications.find((x) => x.id === id)
  if (!l) return fail('请假申请不存在或不在当前数据范围内')
  const student = db.serviceStudents.find((s) => s.id === l.studentId)
  const history = db.leaveApplications.filter((x) => x.studentId === l.studentId && x.id !== id).map((x) => `${x.code} · ${x.duration} · ${x.status}`)
  const audits = db.auditLogs.filter((a) => a.bizId === id)
  return envelope({ leave: clone(l), student: student ? maskStudent(clone(student)) : null, history, auditLogs: clone(audits) })
}

export async function approveLeave(id, { comment = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/leaves/${id}/approve`, { method: 'POST', body: { comment } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const l = db.leaveApplications.find((x) => x.id === id)
  if (!l) return fail('请假申请不存在')
  const before = l.status
  const role = currentRole()
  Object.assign(l, { status: 'APPROVED', reviewer: role.userName, reviewTime: db.nowText(), returnReason: '' })
  pushAudit('LEAVE', id, '审批通过', `${l.code} ${l.name} · ${l.duration}${comment ? '（' + comment + '）' : ''}，结果已同步学生端`, before, 'APPROVED')
  return envelope({ id })
}

export async function returnLeave(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/leaves/${id}/return`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const l = db.leaveApplications.find((x) => x.id === id)
  if (!l) return fail('请假申请不存在')
  if (!reason || reason.trim().length < 5) return fail('退回原因必填且不少于 5 个字')
  const before = l.status
  const role = currentRole()
  Object.assign(l, { status: 'RETURNED', reviewer: role.userName, reviewTime: db.nowText(), returnReason: reason.trim() })
  pushAudit('LEAVE', id, '退回修改', `${l.code} ${l.name}：${reason.trim()}（原因已同步学生端）`, before, 'RETURNED')
  return envelope({ id })
}

export async function batchApproveLeaves(ids = []) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/leaves/batch-approve', { method: 'POST', body: { ids } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!ids.length) return fail('请先选择申请')
  let count = 0
  for (const id of ids) {
    const l = db.leaveApplications.find((x) => x.id === id)
    if (l && l.status === 'PENDING_REVIEW') {
      await approveLeave(id, { comment: '批量通过' })
      count++
    }
  }
  pushAudit('LEAVE', ids.join(','), '批量审批通过', `批量通过 ${count} 条待审批请假`)
  return envelope({ count })
}

/* ---------------- 奖助 / 资助审核 ---------------- */
function maskGrant(g) {
  return { ...g, amount: undefined, amountDisplay: g.amountRange }
}

export async function getGrantApplications(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/grants', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', status = '', page = 1, pageSize = 10 } = params
  let list = scopeByStudent(db.grantApplications)
  list = list.filter(
    (g) => (kw(g.name, keyword) || kw(g.code, keyword)) && (!type || g.type === type) && (!status || g.status === status)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskGrant), total, page, pageSize })
}

export async function getGrantApplicationDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/grants/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.grantApplications.find((x) => x.id === id)
  if (!g) return fail('资助申请不存在或不在当前数据范围内')
  const student = db.serviceStudents.find((s) => s.id === g.studentId)
  const pa = buildPermissionActions()['campus.grant.viewMaterial']
  const canViewMaterial = !!(pa && pa.visible && pa.allowed)
  const materials = canViewMaterial
    ? ['家庭经济情况调查表.pdf', '低保证明.jpg', '个人申请书.docx'].slice(0, g.materialSensitive ? 3 : 1)
    : []
  if (canViewMaterial && g.materialSensitive) {
    pushAudit('GRANT', id, '查看困难材料', `${g.code} ${g.name} 困难帮扶材料被查看（敏感访问留痕）`)
  }
  const audits = db.auditLogs.filter((a) => a.bizId === id)
  return envelope({
    grant: maskGrant(clone(g)),
    student: student ? maskStudent(clone(student)) : null,
    materials,
    materialHint: canViewMaterial ? '' : '家庭经济困难材料仅资助老师等授权角色可见，查看将写入审计日志',
    auditLogs: clone(audits)
  })
}

export async function approveGrant(id, { comment = '' } = {}) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/grants/${id}/approve`, { method: 'POST', body: { comment } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code); return fail(e.message || '审核失败') }
  }
  return refuseLegacyMockWrite('奖助审批')
}

export async function returnGrant(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/grants/${id}/return`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code); return fail(e.message || '退回失败') }
  }
  return refuseLegacyMockWrite('奖助退回')
}

export async function batchApproveGrants(ids = []) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/grants/batch-approve', { method: 'POST', body: { ids } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code); return fail(e.message || '批量审核失败') }
  }
  return refuseLegacyMockWrite('奖助批量审批')
}

/* ---------------- 宿舍住宿与异常 ---------------- */
function dormScope(list) {
  const role = currentRole()
  if (role.dataScope.code === 'DORM') return list.filter((d) => ['B3', 'B5'].includes(d.buildingId))
  if (role.dataScope.code === 'CLASS') {
    const ids = new Set(db.serviceStudents.filter((s) => ['CL01', 'CL02'].includes(s.classId)).map((s) => s.id))
    return list.filter((d) => ids.has(d.studentId))
  }
  if (role.dataScope.code === 'COLLEGE') return list.filter((d) => d.collegeId === 'C01')
  return list
}

export async function getDormitoryRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/dorm-records', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', buildingId = '', status = '', page = 1, pageSize = 10 } = params
  let list = dormScope(db.dormitoryRecords)
  list = list.filter(
    (d) => (kw(d.name, keyword) || kw(d.room, keyword)) && (!buildingId || d.buildingId === buildingId) && (!status || d.status === status)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createDormitoryRecord(payload) {
  await delay()
  if (!payload?.studentId || !payload?.buildingId || !payload?.room) return fail('学生、楼栋与房间为必填项')
  const s = db.serviceStudents.find((x) => x.id === payload.studentId)
  if (!s) return fail('学生不存在')
  const building = db.filterOptions.buildings.find((b) => b.value === payload.buildingId)
  const id = `svc-d-${Date.now()}`
  db.dormitoryRecords.unshift({
    id,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    collegeId: s.collegeId,
    buildingId: payload.buildingId,
    building: building ? building.label : '',
    room: payload.room,
    bed: payload.bed || '1',
    checkinDate: payload.checkinDate || db.nowText().slice(0, 10),
    status: 'IN',
    exceptionCount: 0,
    recordStatus: 'ACTIVE',
    voidReason: '',
    updateTime: db.nowText()
  })
  s.buildingId = payload.buildingId
  s.building = building ? building.label : s.building
  s.room = `${payload.room}-${payload.bed || '1'}`
  pushAudit('DORM', id, '新增住宿记录', `${s.name} 入住 ${building ? building.label : ''}${payload.room}-${payload.bed || '1'}`, '', 'IN')
  return envelope({ id })
}

export async function updateDormitoryRecord(id, payload) {
  await delay()
  const d = db.dormitoryRecords.find((x) => x.id === id)
  if (!d) return fail('住宿记录不存在')
  const before = `${d.building}${d.room}-${d.bed} / ${d.status}`
  Object.assign(d, payload, { updateTime: db.nowText() })
  if (payload.buildingId) {
    const building = db.filterOptions.buildings.find((b) => b.value === payload.buildingId)
    if (building) d.building = building.label
  }
  pushAudit('DORM', id, '编辑住宿信息', `${d.name} 住宿信息更新`, before, `${d.building}${d.room}-${d.bed} / ${d.status}`)
  return envelope({ id })
}

export async function getDormitoryExceptions(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/dorm-exceptions', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', status = '', buildingId = '', page = 1, pageSize = 10 } = params
  let list = dormScope(db.dormitoryExceptionRecords)
  list = list.filter(
    (d) =>
      (kw(d.name, keyword) || kw(d.code, keyword)) &&
      (!type || d.type === type) &&
      (!status || d.status === status) &&
      (!buildingId || d.buildingId === buildingId)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function markDormException(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/dorm-exceptions', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.studentId || !payload?.type || !payload?.detail) return fail('学生、异常类型与情况说明为必填项')
  if (payload.detail.trim().length < 5) return fail('情况说明不少于 5 个字')
  const s = db.serviceStudents.find((x) => x.id === payload.studentId)
  if (!s) return fail('学生不存在')
  const typeLabel = db.statusOptions.dormExceptionType.find((t) => t.value === payload.type)?.label || ''
  const id = `svc-de-${Date.now()}`
  db.dormitoryExceptionRecords.unshift({
    id,
    code: `DE-2026-${String(Math.floor(Math.random() * 9000) + 1000)}`,
    studentId: s.id,
    name: s.name,
    className: s.className,
    collegeId: s.collegeId,
    buildingId: s.buildingId,
    building: s.building,
    room: s.room.split('-')[0],
    type: payload.type,
    typeLabel,
    happenTime: db.nowText(),
    detail: payload.detail.trim(),
    status: 'PENDING_HANDLE',
    handler: '',
    handleNote: '',
    handleTime: '',
    recordStatus: 'ACTIVE',
    voidReason: ''
  })
  const dorm = db.dormitoryRecords.find((x) => x.studentId === s.id)
  if (dorm) dorm.exceptionCount += 1
  pushAudit('DORM_EXCEPTION', id, '标记宿舍异常', `${s.name} · ${typeLabel}：${payload.detail.trim()}`, '', 'PENDING_HANDLE')
  return envelope({ id })
}

export async function handleDormException(id, { note, complete }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/dorm-exceptions/${id}/handle`, { method: 'POST', body: { note, complete } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const d = db.dormitoryExceptionRecords.find((x) => x.id === id)
  if (!d) return fail('异常记录不存在')
  if (!note || note.trim().length < 5) return fail('处理说明必填且不少于 5 个字')
  const before = d.status
  const role = currentRole()
  d.status = complete ? 'COMPLETED' : 'PROCESSING'
  d.handler = `${role.userName}（${role.roleName}）`
  d.handleNote = note.trim()
  d.handleTime = db.nowText()
  pushAudit('DORM_EXCEPTION', id, complete ? '办结宿舍异常' : '跟进宿舍异常', `${d.code} ${d.name}：${note.trim()}`, before, d.status)
  return envelope({ id, status: d.status })
}

/* ---------------- 违纪 / 处分 ---------------- */
export async function getDisciplineRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/disciplines', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', status = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeByStudent(db.disciplineRecords)
  list = list.filter(
    (d) =>
      (kw(d.name, keyword) || kw(d.code, keyword) || kw(d.reason, keyword)) &&
      (!type || d.type === type) &&
      (!status || d.status === status) &&
      (recordStatus ? d.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createDisciplineRecord(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/disciplines', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code); return fail(e.message || '登记失败') }
  }
  return refuseLegacyMockWrite('违纪处分登记')
}

export async function updateDisciplineRecord(id, payload) {
  return refuseLegacyMockWrite('违纪处分编辑')
}

export async function voidDisciplineRecord(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/disciplines/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code); return fail(e.message || '作废失败') }
  }
  return refuseLegacyMockWrite('违纪处分作废')
}

/* ---------------- 服务工单 ---------------- */
export async function getServiceWorkOrders(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/work-orders', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', status = '', priority = '', page = 1, pageSize = 10 } = params
  let list = scopeByStudent(db.serviceWorkOrders)
  const role = currentRole()
  if (role.roleId === 'PSYCH_TEACHER') list = list.filter((w) => w.type === 'CARE')
  list = list.filter(
    (w) =>
      (kw(w.name, keyword) || kw(w.code, keyword) || kw(w.title, keyword)) &&
      (!type || w.type === type) &&
      (!status || w.status === status) &&
      (!priority || w.priority === priority)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getWorkOrderDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/work-orders/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.serviceWorkOrders.find((x) => x.id === id)
  if (!w) return fail('工单不存在或不在当前数据范围内')
  const student = db.serviceStudents.find((s) => s.id === w.studentId)
  const audits = db.auditLogs.filter((a) => a.bizId === id)
  return envelope({
    order: clone(w),
    student: student ? maskStudent(clone(student)) : null,
    trail: clone(db.workOrderTrails[id] || []),
    auditLogs: clone(audits)
  })
}

export async function createWorkOrder(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/work-orders', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.studentId || !payload?.title || !payload?.type) return fail('学生、标题与类型为必填项')
  const s = db.serviceStudents.find((x) => x.id === payload.studentId)
  if (!s) return fail('学生不存在')
  const id = `svc-w-${Date.now()}`
  db.serviceWorkOrders.unshift({
    id,
    code: `WO-2026-${String(Math.floor(Math.random() * 9000) + 1000)}`,
    title: payload.title,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    collegeId: s.collegeId,
    type: payload.type,
    priority: payload.priority || 'MEDIUM',
    handlerId: '',
    handler: '',
    status: 'PENDING_HANDLE',
    overdue: false,
    slaHint: 'SLA 48 小时',
    createTime: db.nowText(),
    updateTime: db.nowText(),
    closeTime: '',
    detail: payload.detail || '',
    recordStatus: 'ACTIVE',
    voidReason: ''
  })
  db.workOrderTrails[id] = [{ title: `${currentRole().userName} · 代学生登记工单`, desc: payload.detail || '', time: db.nowText(), tone: 'processing' }]
  s.workOrderCount += 1
  pushAudit('WORKORDER', id, '新增工单', `${s.name} · ${payload.title}`, '', 'PENDING_HANDLE')
  return envelope({ id })
}

export async function updateWorkOrder(id, payload) {
  await delay()
  const w = db.serviceWorkOrders.find((x) => x.id === id)
  if (!w) return fail('工单不存在')
  const before = `${w.title}/${w.priority}`
  Object.assign(w, payload, { updateTime: db.nowText() })
  pushAudit('WORKORDER', id, '编辑工单', `${w.code}：标题/优先级更新`, before, `${w.title}/${w.priority}`)
  return envelope({ id })
}

export async function assignWorkOrders(ids = [], { handlerId }) {
  if (shouldTryReal()) {
    try { return envelope(await request('/campus-service/work-orders/assign', { method: 'POST', body: { ids, handler: handlerId } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!ids.length) return fail('请先选择工单')
  const handler = db.filterOptions.handlers.find((h) => h.value === handlerId)
  if (!handler) return fail('请选择处理人')
  ids.forEach((id) => {
    const w = db.serviceWorkOrders.find((x) => x.id === id)
    if (w) {
      w.handlerId = handlerId
      w.handler = handler.label
      if (w.status === 'PENDING_HANDLE') w.status = 'PROCESSING'
      w.updateTime = db.nowText()
      ;(db.workOrderTrails[id] = db.workOrderTrails[id] || []).push({
        title: `分派给 ${handler.label}`,
        desc: `由 ${currentRole().userName} 分派`,
        time: db.nowText(),
        tone: 'processing'
      })
    }
  })
  pushAudit('WORKORDER', ids.join(','), '批量分派工单', `${ids.length} 个工单分派给 ${handler.label}`)
  return envelope({ count: ids.length })
}

export async function handleWorkOrder(id, { note, close }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/work-orders/${id}/handle`, { method: 'POST', body: { note, close } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.serviceWorkOrders.find((x) => x.id === id)
  if (!w) return fail('工单不存在')
  if (!note || note.trim().length < 5) return fail('处理说明必填且不少于 5 个字')
  const before = w.status
  const role = currentRole()
  w.status = close ? 'COMPLETED' : 'PROCESSING'
  w.updateTime = db.nowText()
  if (close) {
    w.closeTime = db.nowText()
    w.overdue = false
    w.slaHint = '已办结'
  }
  ;(db.workOrderTrails[id] = db.workOrderTrails[id] || []).push({
    title: `${role.userName} · ${close ? '办结工单' : '处理进展'}`,
    desc: note.trim(),
    time: db.nowText(),
    tone: close ? 'success' : 'processing'
  })
  pushAudit('WORKORDER', id, close ? '办结工单' : '处理工单', `${w.code}：${note.trim()}（进展已同步学生端）`, before, w.status)
  return envelope({ id, status: w.status })
}

export async function closeWorkOrder(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/campus-service/work-orders/${id}/close`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.serviceWorkOrders.find((x) => x.id === id)
  if (!w) return fail('工单不存在')
  if (!reason || reason.trim().length < 5) return fail('关闭说明必填且不少于 5 个字')
  const before = w.status
  w.status = 'CLOSED'
  w.closeTime = db.nowText()
  w.updateTime = db.nowText()
  ;(db.workOrderTrails[id] = db.workOrderTrails[id] || []).push({
    title: `${currentRole().userName} · 关闭工单`,
    desc: reason.trim(),
    time: db.nowText(),
    tone: 'default'
  })
  pushAudit('WORKORDER', id, '关闭工单', `${w.code}：${reason.trim()}`, before, 'CLOSED')
  return envelope({ id })
}

/* ---------------- 心理关怀（涉密） ---------------- */
export async function getMentalHealthRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/mental-records', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const pa = buildPermissionActions()['campus.mental.view']
  if (!pa || !pa.visible) return fail('该数据为涉密内容，当前角色不可见', 403)
  if (!pa.allowed) return fail(pa.reason || '当前角色无权查看心理关怀记录', 403)
  const { keyword = '', page = 1, pageSize = 10 } = params
  let list = scopeByStudent(db.mentalHealthRecords).filter((m) => kw(m.name, keyword))
  pushAudit('MENTAL', 'mentalList', '查看心理关怀列表', '心理关怀记录列表被查看（涉密访问留痕）')
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

/* ---------------- 导入 / 导出 ---------------- */
export async function validateImport(templateKey, fileName = '') {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  const rows =
    templateKey === 'dormList'
      ? [
          { row: 2, data: '2023010101 / 3号宿舍楼 / 312 / 1', valid: true, error: '' },
          { row: 3, data: '2023010102 / 5号宿舍楼 / 520 / 2', valid: true, error: '' },
          { row: 4, data: '2023010199 / 9号宿舍楼 / 101 / 1', valid: false, error: '楼栋「9号宿舍楼」不存在' }
        ]
      : [
          { row: 2, data: '2023010115 / 宋雨霏 / 软件2301班', valid: true, error: '' },
          { row: 3, data: '2023010116 / 韩立诚 / 软件2301班', valid: true, error: '' },
          { row: 4, data: '2023019999 / 陌生学生 / 软件2309班', valid: false, error: '班级不存在或学号不在数据范围内' }
        ]
  return envelope({ fileName: fileName || tpl.fileName, total: rows.length, validCount: rows.filter((r) => r.valid).length, rows })
}

export async function confirmImport(templateKey, { validCount = 0, fileName = '' } = {}) {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  pushAudit('IMPORT', templateKey, '执行导入', `${tpl.name}：导入 ${validCount} 条校验通过数据（${fileName}），失败数据未导入，回执已生成`)
  return envelope({ imported: validCount, skipped: 0, receiptId: `svc-imp-${Date.now()}` })
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
    watermarkText: `${db.tenantBrandConfig.schoolName} · ${role.userName} · ${db.nowText()}`,
    auditId: db.auditLogs[0].id
  })
}

/* ---------------- 审计日志 ---------------- */
export async function getAuditLogs(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/campus-service/audit-logs', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { bizType = '', keyword = '', page = 1, pageSize = 20 } = params
  let list = db.auditLogs.filter((a) => (!bizType || a.bizType === bizType) && (kw(a.detail, keyword) || kw(a.operator, keyword)))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}
