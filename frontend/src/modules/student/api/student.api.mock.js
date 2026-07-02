/**
 * 01 学生主档 — mock API（默认实现，与 contract 15 接口逐一对齐）
 * 写操作真实变更内存状态并追加时间线/审计；导出走 security export guard + audit。
 * 页面禁止直引本文件（必须经 provider）。
 */
import { STUDENT_ERROR_CODES as E } from './student.contract'
import {
  STUDENT_STATUS_LABELS,
  IDENTITY_VERIFY_STATUS,
  ACADEMIC_STATUS,
  DATA_QUALITY_STATUS,
  ACCOUNT_BIND_STATUS
} from '../constants/student.constants'
import * as db from '../mock/student.mock'
import { validateRejectReason } from '@/modules/workflow/helpers/approval.helpers'
import {
  validateExportRequest,
  createExportAuditEvent,
  sendAuditEventToBackend,
  createAuditEvent
} from '@/security'

const delay = (ms = 160) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `stu-mock-${Date.now()}-${++seq}`
})
const fail = (code, message) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))
const kw = (t, k) => !k || String(t || '').includes(k)

function guard() {
  if (db.mockFlags.forceError) return fail(E.SERVER_ERROR, '模拟服务端错误')
  return null
}

function findStudent(id) {
  return db.students.find((s) => s.studentId === id)
}

function pushTimeline(studentId, type, title, operator, detail = '') {
  ;(db.timelines[studentId] = db.timelines[studentId] || []).unshift({
    time: db.nowText(),
    type,
    title,
    operator,
    detail
  })
}

function pushAudit(studentId, operator, action, before = '', after = '') {
  ;(db.auditLogs[studentId] = db.auditLogs[studentId] || []).unshift({
    time: db.nowText(),
    operator,
    action,
    before,
    after
  })
}

const OPERATOR = '学校管理员'

/* 1. 概览 */
export async function getStudentOverview() {
  await delay()
  const err = guard()
  if (err) return err
  const s = db.students
  const recentStatusChanges = Object.entries(db.timelines)
    .flatMap(([sid, list]) => list.filter((t) => t.type === 'STATUS').map((t) => ({ ...t, studentId: sid, name: findStudent(sid)?.name })))
    .slice(0, 5)
  const recentVerifies = Object.entries(db.timelines)
    .flatMap(([sid, list]) => list.filter((t) => t.type === 'IDENTITY').map((t) => ({ ...t, studentId: sid, name: findStudent(sid)?.name })))
    .slice(0, 5)
  return envelope({
    totalCount: s.length,
    activeCount: s.filter((x) => x.studentStatus === 'ACTIVE').length,
    pendingVerifyCount: s.filter((x) => x.identityVerifyStatus === IDENTITY_VERIFY_STATUS.PENDING).length,
    dataMissingCount: s.filter((x) => x.dataQualityTags.includes(DATA_QUALITY_STATUS.MISSING_REQUIRED)).length,
    academicWarningCount: s.filter((x) => x.academicStatus === ACADEMIC_STATUS.WARNING).length,
    accountUnboundCount: s.filter((x) => x.bindStatus === ACCOUNT_BIND_STATUS.UNBOUND).length,
    recentStatusChanges,
    recentVerifies
  })
}

/* 2. 列表 */
export async function getStudentList(params = {}) {
  await delay()
  const err = guard()
  if (err) return err
  if (db.mockFlags.forceEmpty) return envelope({ list: [], total: 0 })
  let list = db.students
  const f = params
  if (f.keyword) list = list.filter((s) => kw(s.name, f.keyword) || kw(s.studentNo, f.keyword) || (s.phone && s.phone.endsWith(f.keyword)))
  if (f.collegeId) list = list.filter((s) => s.collegeId === f.collegeId)
  if (f.majorId) list = list.filter((s) => s.majorId === f.majorId)
  if (f.classId) list = list.filter((s) => s.classId === f.classId)
  if (f.grade) list = list.filter((s) => s.grade === f.grade)
  if (f.studentStatus) list = list.filter((s) => s.studentStatus === f.studentStatus)
  if (f.academicStatus) list = list.filter((s) => s.academicStatus === f.academicStatus)
  if (f.identityVerifyStatus) list = list.filter((s) => s.identityVerifyStatus === f.identityVerifyStatus)
  if (f.accountStatus) list = list.filter((s) => s.accountStatus === f.accountStatus)
  const page = Number(f.page) || 1
  const pageSize = Number(f.pageSize) || 10
  return envelope({ list: clone(list.slice((page - 1) * pageSize, page * pageSize)), total: list.length })
}

/* 3/4. 详情与档案 */
export async function getStudentDetail(studentId) {
  await delay()
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  // 查看详情留痕（detail 经 security sanitize 脱敏）
  await sendAuditEventToBackend(
    createAuditEvent('SENSITIVE_VIEW', '查看学生详情', { studentId }, { targetType: 'STUDENT', targetId: studentId })
  )
  return envelope(clone(s))
}

export async function getStudentProfile(studentId) {
  await delay(100)
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  return envelope(clone(s))
}

/* 5. 身份信息 */
export async function getStudentIdentity(studentId) {
  await delay(100)
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  return envelope({
    studentId: s.studentId,
    name: s.name,
    idCard: s.idCard,
    identityVerifyStatus: s.identityVerifyStatus,
    idCardExpireDate: s.idCardExpireDate,
    verifyRecords: clone(db.verifyRecords[studentId] || [])
  })
}

/* 6. 核验通过 */
export async function verifyStudentIdentity(studentId) {
  await delay()
  const err = guard()
  if (err) return err
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  if (s.identityVerifyStatus === IDENTITY_VERIFY_STATUS.VERIFIED) return fail(E.ALREADY_FINAL, '该学生身份已认证，不可重复核验')
  const before = s.identityVerifyStatus
  s.identityVerifyStatus = IDENTITY_VERIFY_STATUS.VERIFIED
  s.updatedAt = db.nowText()
  ;(db.verifyRecords[studentId] = db.verifyRecords[studentId] || []).unshift({ time: db.nowText(), operator: OPERATOR, action: 'APPROVE', comment: '' })
  pushTimeline(studentId, 'IDENTITY', '身份核验通过', OPERATOR)
  pushAudit(studentId, OPERATOR, '身份核验通过', before, 'VERIFIED')
  await sendAuditEventToBackend(createAuditEvent('APPROVAL', '身份核验通过', { studentId }, { targetType: 'STUDENT', targetId: studentId }))
  return envelope(clone(s))
}

/* 7. 核验退回（复用 workflow validateRejectReason：必填≥5字） */
export async function rejectStudentIdentity(studentId, payload = {}) {
  await delay()
  const err = guard()
  if (err) return err
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  const check = validateRejectReason(payload.reason)
  if (!check.valid) return fail(E.REJECT_REASON_TOO_SHORT, check.message)
  const before = s.identityVerifyStatus
  s.identityVerifyStatus = IDENTITY_VERIFY_STATUS.REJECTED
  s.updatedAt = db.nowText()
  const reason = String(payload.reason).trim()
  ;(db.verifyRecords[studentId] = db.verifyRecords[studentId] || []).unshift({ time: db.nowText(), operator: OPERATOR, action: 'REJECT', comment: reason })
  pushTimeline(studentId, 'IDENTITY', '身份核验退回', OPERATOR, reason)
  pushAudit(studentId, OPERATOR, '身份核验退回', before, 'REJECTED')
  await sendAuditEventToBackend(createAuditEvent('APPROVAL', '身份核验退回', { studentId, reason }, { targetType: 'STUDENT', targetId: studentId }))
  return envelope(clone(s))
}

/* 8/9. 监护人 */
export async function getStudentGuardians(studentId) {
  await delay(100)
  if (!findStudent(studentId)) return fail(E.NOT_FOUND, '学生不存在')
  return envelope({ list: clone(db.guardians.filter((g) => g.studentId === studentId)) })
}

export async function saveStudentGuardians(studentId, payload = {}) {
  await delay()
  const err = guard()
  if (err) return err
  if (!findStudent(studentId)) return fail(E.NOT_FOUND, '学生不存在')
  const incoming = Array.isArray(payload.guardians) ? payload.guardians : null
  if (!incoming) return fail(E.INVALID_PARAM, '监护人数据格式非法')
  for (let i = db.guardians.length - 1; i >= 0; i--) {
    if (db.guardians[i].studentId === studentId) db.guardians.splice(i, 1)
  }
  incoming.forEach((g, idx) =>
    db.guardians.push({ ...g, studentId, guardianId: g.guardianId || `g-${studentId}-${idx + 1}` })
  )
  pushTimeline(studentId, 'GUARDIAN', '监护人信息更新', OPERATOR)
  pushAudit(studentId, OPERATOR, '监护人变更', '', `${incoming.length} 位联系人`)
  await sendAuditEventToBackend(
    createAuditEvent('PERMISSION_CHANGE', '监护人信息更新', { studentId, count: incoming.length }, { targetType: 'STUDENT', targetId: studentId })
  )
  return envelope({ list: clone(db.guardians.filter((g) => g.studentId === studentId)) })
}

/* 10. 状态变更（原因必填） */
export async function changeStudentStatus(studentId, payload = {}) {
  await delay()
  const err = guard()
  if (err) return err
  const s = findStudent(studentId)
  if (!s) return fail(E.NOT_FOUND, '学生不存在')
  const target = payload.targetStatus
  if (!STUDENT_STATUS_LABELS[target]) return fail(E.INVALID_PARAM, '非法的目标状态')
  const reason = String(payload.reason || '').trim()
  if (!reason) return fail(E.CHANGE_REASON_REQUIRED, '状态变更原因必填')
  const before = s.studentStatus
  s.studentStatus = target
  s.updatedAt = db.nowText()
  pushTimeline(studentId, 'STATUS', `状态变更：${STUDENT_STATUS_LABELS[before]} → ${STUDENT_STATUS_LABELS[target]}`, OPERATOR, reason)
  pushAudit(studentId, OPERATOR, '学生状态变更', before, target)
  await sendAuditEventToBackend(
    createAuditEvent('APPROVAL', '学生状态变更', { studentId, before, after: target, reason }, { targetType: 'STUDENT', targetId: studentId })
  )
  return envelope(clone(s))
}

/* 11. 时间线 */
export async function getStudentTimeline(studentId) {
  await delay(100)
  if (!findStudent(studentId)) return fail(E.NOT_FOUND, '学生不存在')
  return envelope({ list: clone(db.timelines[studentId] || []) })
}

/* 12. 字典 */
export async function getStudentOptions() {
  await delay(60)
  return envelope({
    colleges: clone(db.colleges),
    majors: clone(db.majors),
    classes: clone(db.classes),
    grades: clone(db.grades),
    academicYears: clone(db.academicYears),
    terms: clone(db.terms)
  })
}

/* 13. 导入校验（预留 mock，不解析真实文件） */
export async function validateStudentImport() {
  await delay(300)
  const err = guard()
  if (err) return err
  const result = {
    totalRows: 120,
    validRows: 116,
    errorRows: 4,
    errors: [
      { row: 12, field: 'idCard', message: '身份证号格式错误' },
      { row: 45, field: 'classId', message: '班级不存在于字典' },
      { row: 78, field: 'phone', message: '手机号重复' },
      { row: 99, field: 'name', message: '姓名为空' }
    ]
  }
  await sendAuditEventToBackend(createAuditEvent('UPLOAD', '学生导入校验（mock）', { totalRows: result.totalRows, errorRows: result.errorRows }))
  return envelope(result)
}

/* 14. 导出（经 security export guard + 审计；不产真实文件） */
export async function exportStudents(payload = {}) {
  await delay(300)
  const err = guard()
  if (err) return err
  const req = {
    exportType: payload.exportType || 'LIST',
    rowCount: Number(payload.rowCount) || db.students.length,
    purpose: payload.purpose || '',
    module: 'STUDENT'
  }
  const check = validateExportRequest(req)
  if (!check.allowed) return fail(E.NO_PERMISSION, check.reason)
  const evt = createExportAuditEvent(req)
  await sendAuditEventToBackend(evt)
  return envelope({ taskId: `export-${Date.now()}`, rowCount: req.rowCount, watermark: true })
}

/* 15. 审计记录 */
export async function getStudentAuditLogs(studentId) {
  await delay(100)
  if (!findStudent(studentId)) return fail(E.NOT_FOUND, '学生不存在')
  return envelope({ list: clone(db.auditLogs[studentId] || []) })
}
