/**
 * 04 学业过程中心 — mock API（页面唯一数据入口，接真实后端时仅替换本文件实现）。
 * 契约：
 *  - 返回 envelope：{ code, message, data, timestamp, requestId }，code=0 成功。
 *  - 所有写操作（新增/编辑/作废/关闭/升级/批量/导入/导出）真实变更内存 mock 并写入审计日志。
 *  - 删除一律逻辑作废（recordStatus = VOIDED），禁止物理删除。
 *  - 数据范围：CLASS 只见本班（CL01/CL02）、COLLEGE 见本院（C01）、COURSE 见任教课程学生、SCHOOL 见全部。
 *  - 敏感字段（手机号/身份证）出口一律脱敏，页面不得反解。
 */
import * as db from '@/mocks/academic/academic.mock'
import { maskPhone, maskIdCard } from '@/security'
import { request, shouldTryReal } from '@/services/http/client'

const delay = (ms = 150) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `acad-mock-${Date.now()}-${++seq}`
})
const fail = (message, code = 1) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))
const kw = (t, k) => !k || String(t || '').includes(k)

/* ---------------- 上下文 ---------------- */
const currentRole = () => db.roles.find((r) => r.roleId === db.state.currentRoleId) || db.roles[0]
const rolePerm = () => db.permissionActionsByRole[db.state.currentRoleId] || db.permissionActionsByRole.COLLEGE_ADMIN

/** 权限动作快照：{ key: { allowed, visible, reason } } */
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

export async function getAcademicContext() {
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

export async function switchAcademicRole(roleId) {
  await delay(60)
  if (!db.roles.some((r) => r.roleId === roleId)) return fail('角色不存在')
  db.state.currentRoleId = roleId
  return getAcademicContext()
}

/* ---------------- 数据范围过滤 ---------------- */
const TEACHER_COURSE_IDS = ['crs-001', 'crs-002']

function scopeStudentIds() {
  const role = currentRole()
  if (role.dataScope.code === 'COURSE') {
    const ids = new Set(db.gradeRecords.filter((g) => TEACHER_COURSE_IDS.includes(g.courseId)).map((g) => g.studentId))
    return (s) => ids.has(s.id)
  }
  if (role.dataScope.code === 'CLASS') return (s) => ['CL01', 'CL02'].includes(s.classId)
  if (role.dataScope.code === 'COLLEGE') return (s) => s.collegeId === 'C01'
  return () => true
}

function scopeFilterStudents(list) {
  return list.filter(scopeStudentIds())
}

function scopeFilterByStudent(list) {
  const inScope = scopeStudentIds()
  const map = new Map(db.academicStudents.map((s) => [s.id, s]))
  return list.filter((row) => {
    const s = map.get(row.studentId)
    return s ? inScope(s) : false
  })
}

/* ---------------- 审计 ---------------- */
function pushAudit(bizType, bizId, action, detail, before = '', after = '') {
  const role = currentRole()
  db.auditLogs.unshift({
    id: `acad-a-${Date.now()}-${++seq}`,
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

/* ---------------- 看板（指标按数据范围动态计算，体现角色差异） ---------------- */
export async function getAcademicDashboard() {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/dashboard')) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const students = scopeFilterStudents(db.academicStudents).filter((s) => s.recordStatus === 'ACTIVE')
  const warnings = scopeFilterByStudent(db.academicWarnings).filter((w) => w.recordStatus === 'ACTIVE')
  const makeups = scopeFilterByStudent(db.makeupExamRecords).filter((m) => m.recordStatus === 'ACTIVE')
  const retakes = scopeFilterByStudent(db.retakeRecords).filter((r) => r.recordStatus === 'ACTIVE')
  const credits = scopeFilterByStudent(db.creditRecords)
  const closed = warnings.filter((w) => w.status === 'CLOSED').length
  const kpis = [
    { key: 'total', label: '在册学生', value: String(students.length), trend: '', trendQuality: 'neutral' },
    { key: 'warning', label: '学业预警学生', value: String(new Set(warnings.filter((w) => w.status !== 'CLOSED').map((w) => w.studentId)).size), trend: '+1 本周', trendQuality: 'bad' },
    { key: 'failed', label: '挂科学生', value: String(students.filter((s) => s.failedCount > 0).length), trend: '', trendQuality: 'neutral' },
    { key: 'creditGap', label: '学分滞后', value: String(credits.filter((c) => c.status !== 'ON_TRACK').length), trend: '其中严重滞后 ' + credits.filter((c) => c.status === 'SEVERE').length, trendQuality: 'bad' },
    { key: 'makeup', label: '待补考', value: String(makeups.filter((m) => m.status === 'PENDING_EXAM').length), trend: '9 月初开考', trendQuality: 'neutral' },
    { key: 'retake', label: '重修在办', value: String(retakes.filter((r) => r.status !== 'PASSED').length), trend: '', trendQuality: 'neutral' },
    { key: 'pending', label: '待处理预警', value: String(warnings.filter((w) => w.status === 'PENDING_HANDLE').length), trend: '超 3 天未领取 2 条', trendQuality: 'bad' },
    { key: 'closeRate', label: '预警闭环率', value: warnings.length ? Math.round((closed / warnings.length) * 100) + '%' : '—', trend: '', trendQuality: 'good' }
  ]
  return envelope({ ...clone(db.dashboardSummary), kpis })
}

/* ---------------- 学业学生台账 ---------------- */
function maskStudent(s) {
  return { ...s, phone: maskPhone(s.phone), idCard: maskIdCard(s.idCard) }
}

export async function getAcademicStudents(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/students', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', classId = '', warningLevel = '', academicStatus = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterStudents(db.academicStudents)
  list = list.filter(
    (s) =>
      (kw(s.name, keyword) || kw(s.studentNo, keyword)) &&
      (!classId || s.classId === classId) &&
      (!warningLevel || s.warningLevel === warningLevel) &&
      (!academicStatus || s.academicStatus === academicStatus) &&
      (recordStatus ? s.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskStudent), total, page, pageSize })
}

export async function getStudentAcademicDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/students/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.academicStudents.find((x) => x.id === id)
  if (!s) return fail('学生学业档案不存在，或不在当前数据范围内')
  const grades = db.gradeRecords.filter((g) => g.studentId === id)
  const credit = db.creditRecords.find((c) => c.studentId === id) || null
  const exams = db.examRecords.filter((e) => e.studentId === id)
  const makeups = db.makeupExamRecords.filter((m) => m.studentId === id)
  const retakes = db.retakeRecords.filter((r) => r.studentId === id)
  const warnings = db.academicWarnings.filter((w) => w.studentId === id)
  const warningIds = warnings.map((w) => w.id)
  const interventions = db.interventionRecords.filter((i) => warningIds.includes(i.warningId))
  const audits = db.auditLogs.filter(
    (a) => a.bizId === id || warningIds.includes(a.bizId) || interventions.some((i) => i.id === a.bizId) || grades.some((g) => g.id === a.bizId)
  )
  return envelope({
    student: maskStudent(clone(s)),
    grades: clone(grades),
    credit: clone(credit),
    exams: clone(exams),
    makeups: clone(makeups),
    retakes: clone(retakes),
    warnings: clone(warnings),
    interventions: clone(interventions),
    auditLogs: clone(audits)
  })
}

export async function createAcademicRecord(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/students', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.name || !payload?.studentNo) return fail('姓名与学号为必填项')
  const id = `acad-s-${Date.now()}`
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
    gpa: 0,
    avgScore: 0,
    failedCount: 0,
    obtainedCredits: Number(payload.obtainedCredits || 0),
    requiredCredits: Number(payload.requiredCredits || 120),
    makeupCount: 0,
    retakeCount: 0,
    warningLevel: 'NONE',
    warningCount: 0,
    academicStatus: 'NORMAL',
    recordStatus: 'ACTIVE',
    voidReason: '',
    updateTime: db.nowText(),
    ...payload,
    classId,
    className: db.filterOptions.classes.find((c) => c.value === classId)?.label || payload.className || ''
  }
  db.academicStudents.unshift(record)
  pushAudit('RECORD', id, '新增学业记录', `${record.name}（${record.studentNo}）· ${record.className}`, '', 'ACTIVE')
  return envelope({ id })
}

export async function updateAcademicRecord(id, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/students/${id}`, { method: 'PUT', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.academicStudents.find((x) => x.id === id)
  if (!s) return fail('学业记录不存在')
  const before = `学分 ${s.obtainedCredits}/${s.requiredCredits}；状态 ${s.academicStatus}`
  Object.assign(s, payload, { updateTime: db.nowText() })
  pushAudit('RECORD', id, '编辑学业信息', `${s.name} 学业信息更新`, before, `学分 ${s.obtainedCredits}/${s.requiredCredits}；状态 ${s.academicStatus}`)
  return envelope({ id })
}

export async function voidAcademicRecord(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/students/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const s = db.academicStudents.find((x) => x.id === id)
  if (!s) return fail('学业记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  s.recordStatus = 'VOIDED'
  s.voidReason = reason.trim()
  s.updateTime = db.nowText()
  pushAudit('RECORD', id, '作废学业记录', `${s.name}：${reason.trim()}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

export async function batchRemindStudents(ids = [], scene = '学业进度更新') {
  await delay()
  if (!ids.length) return fail('请先选择学生')
  pushAudit('RECORD', ids.join(','), '批量提醒', `向 ${ids.length} 名学生发送「${scene}」提醒（站内信 + 小程序）`)
  return envelope({ count: ids.length })
}

/* ---------------- 课程摘要 ---------------- */
export async function getCourseRecords(params = {}) {
  await delay()
  const { keyword = '', term = '', nature = '', page = 1, pageSize = 10 } = params
  let list = db.courseRecords.filter(
    (c) => (kw(c.courseName, keyword) || kw(c.teacherName, keyword)) && (!term || c.term === term) && (!nature || c.nature === nature)
  )
  const role = currentRole()
  if (role.dataScope.code === 'COURSE') list = list.filter((c) => TEACHER_COURSE_IDS.includes(c.id))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

/* ---------------- 成绩记录 ---------------- */
export async function getGradeRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/grades', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', courseId = '', term = '', passStatus = '', examType = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterByStudent(db.gradeRecords)
  const role = currentRole()
  if (role.dataScope.code === 'COURSE') list = list.filter((g) => TEACHER_COURSE_IDS.includes(g.courseId))
  list = list.filter(
    (g) =>
      (kw(g.name, keyword) || kw(g.courseName, keyword)) &&
      (!courseId || g.courseId === courseId) &&
      (!term || g.term === term) &&
      (!passStatus || g.passStatus === passStatus) &&
      (!examType || g.examType === examType) &&
      (recordStatus ? g.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createGradeRecord(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/grades', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.studentId || !payload?.courseId || payload.score === undefined || payload.score === '') {
    return fail('学生、课程与成绩为必填项')
  }
  const s = db.academicStudents.find((x) => x.id === payload.studentId)
  const c = db.courseRecords.find((x) => x.id === payload.courseId)
  if (!s || !c) return fail('学生或课程不存在')
  const score = Number(payload.score)
  if (Number.isNaN(score) || score < 0 || score > 100) return fail('成绩必须为 0-100 的数字')
  const id = `acad-g-${Date.now()}`
  db.gradeRecords.unshift({
    id,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    courseId: c.id,
    courseName: c.courseName,
    term: payload.term || c.term,
    nature: c.nature,
    creditValue: c.credit,
    score,
    passStatus: score >= 60 ? 'PASSED' : 'FAILED',
    examType: payload.examType || 'FINAL',
    sourceBatch: '手工录入',
    recordStatus: 'ACTIVE',
    voidReason: '',
    updateTime: db.nowText()
  })
  pushAudit('GRADE', id, '新增成绩记录', `${s.name} · ${c.courseName} · ${score} 分`, '', score >= 60 ? 'PASSED' : 'FAILED')
  return envelope({ id })
}

export async function updateGradeRecord(id, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/grades/${id}`, { method: 'PUT', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.gradeRecords.find((x) => x.id === id)
  if (!g) return fail('成绩记录不存在')
  if (!payload?.reason || payload.reason.trim().length < 5) return fail('成绩变更原因必填且不少于 5 个字')
  const score = Number(payload.score)
  if (Number.isNaN(score) || score < 0 || score > 100) return fail('成绩必须为 0-100 的数字')
  const before = `${g.score} 分 / ${g.passStatus}`
  g.score = score
  g.passStatus = score >= 60 ? 'PASSED' : 'FAILED'
  g.updateTime = db.nowText()
  pushAudit('GRADE', id, '成绩变更', `${g.name} · ${g.courseName}：${payload.reason.trim()}`, before, `${g.score} 分 / ${g.passStatus}`)
  return envelope({ id })
}

export async function voidGradeRecord(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/grades/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const g = db.gradeRecords.find((x) => x.id === id)
  if (!g) return fail('成绩记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  g.recordStatus = 'VOIDED'
  g.voidReason = reason.trim()
  g.updateTime = db.nowText()
  pushAudit('GRADE', id, '作废成绩记录', `${g.name} · ${g.courseName}：${reason.trim()}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

/* ---------------- 学分修读 ---------------- */
export async function getCreditRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/credits', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', classId = '', status = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterByStudent(db.creditRecords)
  list = list.filter((c) => kw(c.name, keyword) && (!classId || c.classId === classId) && (!status || c.status === status))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

/* ---------------- 补考 / 重修 ---------------- */
export async function getMakeupExamRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/makeups', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', status = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterByStudent(db.makeupExamRecords)
  list = list.filter(
    (m) =>
      (kw(m.name, keyword) || kw(m.courseName, keyword)) &&
      (!status || m.status === status) &&
      (recordStatus ? m.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getRetakeRecords(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/retakes', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', status = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterByStudent(db.retakeRecords)
  list = list.filter(
    (r) =>
      (kw(r.name, keyword) || kw(r.courseName, keyword)) &&
      (!status || r.status === status) &&
      (recordStatus ? r.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createMakeupRecord(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/makeups', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.studentId || !payload?.courseId) return fail('学生与课程为必填项')
  const s = db.academicStudents.find((x) => x.id === payload.studentId)
  const c = db.courseRecords.find((x) => x.id === payload.courseId)
  if (!s || !c) return fail('学生或课程不存在')
  const id = `acad-mk-${Date.now()}`
  db.makeupExamRecords.unshift({
    id,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    collegeId: s.collegeId,
    courseId: c.id,
    courseName: c.courseName,
    term: payload.term || c.term,
    originScore: Number(payload.originScore || 0),
    examDate: payload.examDate || '待安排',
    status: 'PENDING_EXAM',
    remindCount: 0,
    recordStatus: 'ACTIVE',
    voidReason: '',
    updateTime: db.nowText()
  })
  s.makeupCount += 1
  pushAudit('MAKEUP', id, '新增补考记录', `${s.name} · ${c.courseName}（原 ${payload.originScore || 0} 分）`, '', 'PENDING_EXAM')
  return envelope({ id })
}

export async function updateMakeupStatus(id, { status }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/makeups/${id}/status`, { method: 'PUT', body: { status } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const m = db.makeupExamRecords.find((x) => x.id === id)
  if (!m) return fail('补考记录不存在')
  const label = db.statusOptions.makeupStatus.find((o) => o.value === status)?.label
  if (!label) return fail('非法状态')
  const before = m.status
  m.status = status
  m.updateTime = db.nowText()
  pushAudit('MAKEUP', id, '更新补考状态', `${m.name} · ${m.courseName} → ${label}`, before, status)
  return envelope({ id })
}

export async function updateRetakeStatus(id, { status }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/retakes/${id}/status`, { method: 'PUT', body: { status } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const r = db.retakeRecords.find((x) => x.id === id)
  if (!r) return fail('重修记录不存在')
  const label = db.statusOptions.retakeStatus.find((o) => o.value === status)?.label
  if (!label) return fail('非法状态')
  const before = r.status
  r.status = status
  r.updateTime = db.nowText()
  pushAudit('RETAKE', id, '更新重修状态', `${r.name} · ${r.courseName} → ${label}`, before, status)
  return envelope({ id })
}

export async function voidMakeupRecord(id, { reason }) {
  await delay()
  const m = db.makeupExamRecords.find((x) => x.id === id)
  if (!m) return fail('补考记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  m.recordStatus = 'VOIDED'
  m.voidReason = reason.trim()
  m.updateTime = db.nowText()
  pushAudit('MAKEUP', id, '作废补考记录', `${m.name} · ${m.courseName}：${reason.trim()}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

export async function batchRemindMakeup(ids = []) {
  await delay()
  if (!ids.length) return fail('请先选择记录')
  ids.forEach((id) => {
    const m = db.makeupExamRecords.find((x) => x.id === id)
    if (m) m.remindCount += 1
  })
  pushAudit('MAKEUP', ids.join(','), '批量提醒补考/重修', `向 ${ids.length} 名学生发送考核提醒（站内信 + 小程序）`)
  return envelope({ count: ids.length })
}

/* ---------------- 学业预警 ---------------- */
export async function getAcademicWarnings(params = {}) {
  if (shouldTryReal()) {
    try { const d = await request('/academic/warnings', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { keyword = '', type = '', level = '', status = '', classId = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilterByStudent(db.academicWarnings)
  list = list.filter(
    (w) =>
      (kw(w.name, keyword) || kw(w.code, keyword) || kw(w.reason, keyword)) &&
      (!type || w.type === type) &&
      (!level || w.level === level) &&
      (!status || w.status === status) &&
      (!classId || w.classId === classId) &&
      (recordStatus ? w.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getWarningDetail(id) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${id}`)) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === id)
  if (!w) return fail('预警不存在或不在当前数据范围内')
  const student = db.academicStudents.find((s) => s.id === w.studentId)
  const interventions = db.interventionRecords.filter((i) => i.warningId === id)
  const audits = db.auditLogs.filter((a) => a.bizId === id || interventions.some((i) => i.id === a.bizId))
  return envelope({
    warning: clone(w),
    student: student ? maskStudent(clone(student)) : null,
    extras: clone(db.warningDetailExtras[id] || { relatedGrades: [], relatedCredits: '', historyWarnings: [], suggestion: '' }),
    interventions: clone(interventions),
    auditLogs: clone(audits)
  })
}

export async function createWarning(payload) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/warnings', { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!payload?.studentId || !payload?.type || !payload?.reason) return fail('学生、预警类型与触发原因为必填项')
  if (payload.reason.trim().length < 5) return fail('触发原因不少于 5 个字')
  const s = db.academicStudents.find((x) => x.id === payload.studentId)
  if (!s) return fail('学生不存在')
  const id = `acad-w-${Date.now()}`
  const code = `AW-2026-${String(Math.floor(Math.random() * 9000) + 1000)}`
  db.academicWarnings.unshift({
    id,
    code,
    studentId: s.id,
    name: s.name,
    classId: s.classId,
    className: s.className,
    collegeId: s.collegeId,
    type: payload.type,
    level: payload.level || 'MEDIUM',
    reason: payload.reason.trim(),
    sourceRule: '人工上报',
    owner: payload.owner || `${currentRole().userName}（${currentRole().roleName}）`,
    ownerId: payload.ownerId || '',
    status: 'PENDING_HANDLE',
    triggerTime: db.nowText(),
    deadline: payload.deadline || '',
    overdue: false,
    remindCount: 0,
    recordStatus: 'ACTIVE',
    voidReason: ''
  })
  s.warningCount += 1
  if (s.academicStatus === 'NORMAL') s.academicStatus = 'WARNING'
  pushAudit('WARNING', id, '新增学业预警', `${s.name} · ${payload.reason.trim()}`, '', 'PENDING_HANDLE')
  return envelope({ id, code })
}

export async function updateWarningLevel(id, { level, reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${id}/level`, { method: 'PUT', body: { level, reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === id)
  if (!w) return fail('预警不存在')
  if (!reason || reason.trim().length < 5) return fail('调整原因必填且不少于 5 个字')
  const label = db.statusOptions.warningLevel.find((o) => o.value === level)?.label
  if (!label) return fail('非法等级')
  const before = w.level
  w.level = level
  pushAudit('WARNING', id, '调整预警等级', `${w.name} · ${w.code}：${reason.trim()}`, before, level)
  return envelope({ id })
}

export async function voidWarning(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${id}/void`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === id)
  if (!w) return fail('预警不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字（如误报说明）')
  w.recordStatus = 'VOIDED'
  w.voidReason = reason.trim()
  pushAudit('WARNING', id, '作废预警（误报）', `${w.name} · ${w.code}：${reason.trim()}`, w.status, 'VOIDED')
  return envelope({ id })
}

export async function assignWarnings(ids = [], { ownerId, ownerName }) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/warnings/assign', { method: 'POST', body: { ids, ownerId, ownerName } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!ids.length) return fail('请先选择预警')
  if (!ownerName) return fail('请选择跟进人')
  ids.forEach((id) => {
    const w = db.academicWarnings.find((x) => x.id === id)
    if (w) {
      w.owner = ownerName
      w.ownerId = ownerId || ''
      if (w.status === 'PENDING_HANDLE') w.status = 'PROCESSING'
    }
  })
  pushAudit('WARNING', ids.join(','), '批量分配跟进人', `${ids.length} 条预警分配给 ${ownerName}`)
  return envelope({ count: ids.length })
}

export async function remindWarnings(ids = []) {
  if (shouldTryReal()) {
    try { return envelope(await request('/academic/warnings/remind', { method: 'POST', body: { ids } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  if (!ids.length) return fail('请先选择预警')
  ids.forEach((id) => {
    const w = db.academicWarnings.find((x) => x.id === id)
    if (w) w.remindCount += 1
  })
  pushAudit('WARNING', ids.join(','), '批量提醒', `向 ${ids.length} 条预警的学生/跟进人发送提醒`)
  return envelope({ count: ids.length })
}

export async function createIntervention(warningId, payload) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${warningId}/interventions`, { method: 'POST', body: payload })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === warningId)
  if (!w) return fail('预警不存在')
  if (!payload?.content || payload.content.trim().length < 5) return fail('跟进内容必填且不少于 5 个字')
  const id = `acad-i-${Date.now()}`
  const wayLabelMap = { TALK: '当面谈话', PHONE: '电话联系', FAMILY: '家校联系', PLAN: '帮扶计划' }
  db.interventionRecords.unshift({
    id,
    warningId,
    studentName: w.name,
    time: db.nowText(),
    way: payload.way || 'TALK',
    wayLabel: wayLabelMap[payload.way || 'TALK'],
    content: payload.content.trim(),
    result: payload.result || '',
    nextPlan: payload.nextPlan || '',
    operator: `${currentRole().userName}（${currentRole().roleName}）`,
    status: 'OPEN',
    voidReason: ''
  })
  if (w.status === 'PENDING_HANDLE') w.status = 'PROCESSING'
  pushAudit('INTERVENTION', id, '新增跟进记录', `${w.name} · ${payload.content.trim()}`, '', 'OPEN')
  return envelope({ id })
}

export async function closeWarning(id, { result }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${id}/close`, { method: 'POST', body: { result } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === id)
  if (!w) return fail('预警不存在')
  if (!result || result.trim().length < 5) return fail('关闭说明必填且不少于 5 个字')
  const before = w.status
  w.status = 'CLOSED'
  w.closeResult = result.trim()
  const s = db.academicStudents.find((x) => x.id === w.studentId)
  if (s && !db.academicWarnings.some((x) => x.studentId === s.id && x.recordStatus === 'ACTIVE' && x.status !== 'CLOSED')) {
    s.academicStatus = 'NORMAL'
    s.warningLevel = 'NONE'
  }
  pushAudit('WARNING', id, '关闭预警', `${w.name} · ${w.code}：${result.trim()}（结果已同步学生端）`, before, 'CLOSED')
  return envelope({ id })
}

export async function escalateWarning(id, { reason }) {
  if (shouldTryReal()) {
    try { return envelope(await request(`/academic/warnings/${id}/escalate`, { method: 'POST', body: { reason } })) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const w = db.academicWarnings.find((x) => x.id === id)
  if (!w) return fail('预警不存在')
  if (!reason || reason.trim().length < 5) return fail('升级说明必填且不少于 5 个字')
  const before = `${w.status}/${w.level}`
  w.status = 'ESCALATED'
  w.level = 'HIGH'
  w.owner = '学院学业帮扶专班'
  pushAudit('WARNING', id, '升级预警', `${w.name} · ${w.code}：${reason.trim()}（已转学院学业帮扶专班）`, before, 'ESCALATED/HIGH')
  return envelope({ id })
}

/* ---------------- 导入 / 导出 ---------------- */
export async function validateImport(templateKey, fileName = '') {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  const rows =
    templateKey === 'gradeList'
      ? [
          { row: 2, data: '2023010101 / Web前端开发 / 2025-2026-2 / 92', valid: true, error: '' },
          { row: 3, data: '2023010104 / Java程序设计 / 2025-2026-2 / 48', valid: true, error: '' },
          { row: 4, data: '2023010105 / 数据结构 / 2025-2026-2 / 76', valid: false, error: '课程「数据结构」不在本学期课程库' },
          { row: 5, data: '2023019999 / Web前端开发 / 2025-2026-2 / 88', valid: false, error: '学号不在当前数据范围内' }
        ]
      : [
          { row: 2, data: '2023010115 / 宋雨霏 / 软件2301班 / 120', valid: true, error: '' },
          { row: 3, data: '2023010116 / 韩立诚 / 软件2301班 / 120', valid: true, error: '' },
          { row: 4, data: '2023010117 / 何嘉树 / （空班级）/ 120', valid: false, error: '班级为必填项' }
        ]
  return envelope({ fileName: fileName || tpl.fileName, total: rows.length, validCount: rows.filter((r) => r.valid).length, rows })
}

export async function confirmImport(templateKey, { validCount = 0, fileName = '' } = {}) {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  pushAudit('IMPORT', templateKey, '执行导入', `${tpl.name}：导入 ${validCount} 条校验通过数据（${fileName}），失败数据未导入，回执已生成`)
  return envelope({ imported: validCount, skipped: 0, receiptId: `acad-imp-${Date.now()}` })
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
    try { const d = await request('/academic/audit-logs', { params }); return envelope({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }) }
    catch (e) { if (e.biz) return fail(e.message, e.code) }
  }
  await delay()
  const { bizType = '', keyword = '', page = 1, pageSize = 20 } = params
  let list = db.auditLogs.filter((a) => (!bizType || a.bizType === bizType) && (kw(a.detail, keyword) || kw(a.operator, keyword)))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}
