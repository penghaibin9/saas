/**
 * 07 就业服务中心 — mock API（页面唯一数据入口，接真实后端时仅替换本文件实现）。
 * 约定：
 *  - 返回 envelope：{ code, message, data, timestamp, requestId }
 *  - 所有写操作（新增/编辑/作废/审核/批量/导入/导出）真实变更内存 mock 并写入审计日志。
 *  - 删除一律逻辑作废，禁止物理删除。
 *  - 数据范围：辅导员(CLASS)只见本班，学院角色(COLLEGE)见本院，SCHOOL 见全部。
 */
import * as db from '@/mocks/employment/employment.mock'
import { maskPhone, maskIdCard, maskSalary } from '@/security'

const delay = (ms = 160) => new Promise((r) => setTimeout(r, ms))
let seq = 0
const envelope = (data, code = 0, message = 'ok') => ({
  code,
  message,
  data,
  timestamp: Date.now(),
  requestId: `emp-mock-${Date.now()}-${++seq}`
})
const fail = (message, code = 1) => envelope(null, code, message)
const clone = (v) => JSON.parse(JSON.stringify(v))
const kw = (t, k) => !k || String(t || '').includes(k)

/* ---------------- 上下文 ---------------- */
const currentRole = () => db.roles.find((r) => r.roleId === db.state.currentRoleId) || db.roles[0]

const rolePerm = () => db.permissionActionsByRole[db.state.currentRoleId] || db.permissionActionsByRole.EMP_TEACHER

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

export async function getEmploymentContext() {
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

export async function switchEmploymentRole(roleId) {
  await delay(60)
  if (!db.roles.some((r) => r.roleId === roleId)) return fail('角色不存在')
  db.state.currentRoleId = roleId
  return getEmploymentContext()
}

/* ---------------- 数据范围过滤 ---------------- */
function scopeFilter(list) {
  const role = currentRole()
  if (role.dataScope.code === 'CLASS') return list.filter((s) => ['CL01', 'CL02'].includes(s.classId))
  if (role.dataScope.code === 'COLLEGE') return list.filter((s) => s.collegeId === 'C01')
  return list
}

/* ---------------- 审计 ---------------- */
function pushAudit(bizType, bizId, action, detail, before = '', after = '') {
  const role = currentRole()
  db.auditLogs.unshift({
    id: `emp-a-${Date.now()}-${++seq}`,
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
export async function getEmploymentDashboard() {
  await delay()
  return envelope(clone(db.dashboardSummary))
}

/* ---------------- 就业学生台账 ---------------- */
function maskStudent(s) {
  return { ...s, phone: maskPhone(s.phone), idCard: maskIdCard(s.idCard), salaryRange: s.salaryRange ? maskSalary(s.salaryRange) : '' }
}

export async function getEmploymentStudents(params = {}) {
  await delay()
  const { keyword = '', classId = '', destinationType = '', verifyStatus = '', helpLevel = '', recordStatus = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.employmentStudents)
  list = list.filter(
    (s) =>
      (kw(s.name, keyword) || kw(s.studentNo, keyword) || kw(s.companyName, keyword)) &&
      (!classId || s.classId === classId) &&
      (!destinationType || s.destinationType === destinationType) &&
      (!verifyStatus || s.verifyStatus === verifyStatus) &&
      (!helpLevel || s.helpLevel === helpLevel) &&
      (recordStatus ? s.recordStatus === recordStatus : true)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)).map(maskStudent), total, page, pageSize })
}

export async function getEmploymentStudentDetail(id) {
  await delay()
  const s = db.employmentStudents.find((x) => x.id === id)
  if (!s) return fail('学生就业记录不存在')
  const materials = db.employmentMaterials.filter((m) => m.studentId === id)
  const followUps = db.followUpRecords.filter((f) => f.studentId === id)
  const audits = db.auditLogs.filter((a) => a.bizId === id || materials.some((m) => m.id === a.bizId) || followUps.some((f) => f.id === a.bizId))
  return envelope({ student: maskStudent(clone(s)), materials: clone(materials), followUps: clone(followUps), auditLogs: clone(audits) })
}

export async function createEmploymentRecord(payload) {
  await delay()
  if (!payload?.name || !payload?.studentNo) return fail('姓名与学号为必填项')
  const id = `emp-s-${Date.now()}`
  const record = {
    id,
    studentId: id,
    grade: '2026届',
    gender: '—',
    collegeId: 'C01',
    collegeName: db.filterOptions.colleges[0].label,
    majorName: '—',
    classId: payload.classId || 'CL01',
    className: db.filterOptions.classes.find((c) => c.value === (payload.classId || 'CL01'))?.label || '',
    phone: payload.phone || '',
    idCard: '',
    contractType: '',
    signDate: payload.signDate || '',
    isMatchMajor: true,
    fromInternship: false,
    verifyStatus: 'PENDING_VERIFY',
    materialStatus: 'SUBMITTED',
    helpLevel: 'NORMAL',
    riskLevel: 'LOW',
    recordStatus: 'ACTIVE',
    voidReason: '',
    counselor: '—',
    employmentTeacher: '—',
    unemployedReason: '',
    lastFollowUpTime: '',
    followUpCount: 0,
    updateTime: db.nowText(),
    ...payload
  }
  db.employmentStudents.unshift(record)
  pushAudit('RECORD', id, '新增就业记录', `${record.name}（${record.studentNo}）· ${record.companyName || '未填单位'}`, '', 'ACTIVE')
  return envelope({ id })
}

export async function updateEmploymentRecord(id, payload) {
  await delay()
  const s = db.employmentStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  const before = `${s.destinationType}/${s.companyName || '-'}`
  Object.assign(s, payload, { updateTime: db.nowText() })
  pushAudit('RECORD', id, '编辑就业信息', `${s.name} 就业信息更新`, before, `${s.destinationType}/${s.companyName || '-'}`)
  return envelope({ id })
}

export async function voidEmploymentRecord(id, { reason }) {
  await delay()
  const s = db.employmentStudents.find((x) => x.id === id)
  if (!s) return fail('记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  s.recordStatus = 'VOIDED'
  s.voidReason = reason
  s.updateTime = db.nowText()
  pushAudit('RECORD', id, '作废就业记录', `${s.name}：${reason}`, 'ACTIVE', 'VOIDED')
  return envelope({ id })
}

export async function batchRemindStudents(ids = []) {
  await delay()
  pushAudit('RECORD', ids.join(','), '批量提醒', `向 ${ids.length} 名学生发送就业填报/更新提醒`)
  return envelope({ count: ids.length })
}

export async function batchMarkDestination(ids = [], destinationType) {
  await delay()
  const label = db.statusOptions.destinationType.find((d) => d.value === destinationType)?.label || destinationType
  ids.forEach((id) => {
    const s = db.employmentStudents.find((x) => x.id === id)
    if (s) {
      s.destinationType = destinationType
      s.verifyStatus = 'PENDING_VERIFY'
      s.updateTime = db.nowText()
    }
  })
  pushAudit('RECORD', ids.join(','), '批量标记去向', `${ids.length} 名学生去向标记为「${label}」，待核验`)
  return envelope({ count: ids.length })
}

/* ---------------- 材料审核 ---------------- */
export async function getEmploymentMaterials(params = {}) {
  await delay()
  const { keyword = '', status = '', materialType = '', page = 1, pageSize = 10 } = params
  const scopedIds = new Set(scopeFilter(db.employmentStudents).map((s) => s.id))
  let list = db.employmentMaterials.filter(
    (m) => scopedIds.has(m.studentId) && (kw(m.name, keyword) || kw(m.fileName, keyword)) && (!status || m.status === status) && (!materialType || m.materialType === materialType)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function getMaterialReviewDetail(id) {
  await delay()
  const m = db.employmentMaterials.find((x) => x.id === id)
  if (!m) return fail('材料不存在')
  const student = db.employmentStudents.find((s) => s.id === m.studentId)
  const history = db.auditLogs.filter((a) => a.bizId === id)
  return envelope({ material: clone(m), student: student ? maskStudent(clone(student)) : null, auditLogs: clone(history) })
}

export async function approveMaterial(id, { comment = '' } = {}) {
  await delay()
  const m = db.employmentMaterials.find((x) => x.id === id)
  if (!m) return fail('材料不存在')
  const before = m.status
  const role = currentRole()
  Object.assign(m, { status: 'APPROVED', reviewer: role.roleName, reviewTime: db.nowText(), returnReason: '' })
  const s = db.employmentStudents.find((x) => x.id === m.studentId)
  if (s) {
    s.materialStatus = 'APPROVED'
    s.verifyStatus = 'VERIFIED'
    s.updateTime = db.nowText()
  }
  pushAudit('MATERIAL', id, '审核通过', `通过《${m.fileName}》${comment ? ' · ' + comment : ''}`, before, 'APPROVED')
  return envelope({ id })
}

export async function returnMaterial(id, { reason }) {
  await delay()
  const m = db.employmentMaterials.find((x) => x.id === id)
  if (!m) return fail('材料不存在')
  if (!reason || reason.trim().length < 5) return fail('退回原因不少于 5 个字')
  const before = m.status
  const role = currentRole()
  Object.assign(m, { status: 'RETURNED', reviewer: role.roleName, reviewTime: db.nowText(), returnReason: reason })
  const s = db.employmentStudents.find((x) => x.id === m.studentId)
  if (s) {
    s.materialStatus = 'RETURNED'
    s.verifyStatus = 'RETURNED'
    s.updateTime = db.nowText()
  }
  pushAudit('MATERIAL', id, '退回材料', `退回《${m.fileName}》：${reason}`, before, 'RETURNED')
  return envelope({ id })
}

export async function batchReviewMaterials(ids = [], { pass, reason = '' }) {
  await delay()
  if (!pass && (!reason || reason.trim().length < 5)) return fail('批量退回必须填写原因（不少于 5 个字）')
  for (const id of ids) {
    if (pass) await approveMaterial(id, { comment: '批量通过' })
    else await returnMaterial(id, { reason })
  }
  pushAudit('MATERIAL', ids.join(','), pass ? '批量通过材料' : '批量退回材料', `${ids.length} 份材料${pass ? '通过' : `退回：${reason}`}`)
  return envelope({ count: ids.length })
}

/* ---------------- 未就业学生 ---------------- */
export async function getUnemployedStudents(params = {}) {
  await delay()
  const { keyword = '', helpLevel = '', riskLevel = '', page = 1, pageSize = 10 } = params
  let list = scopeFilter(db.employmentStudents).filter(
    (s) =>
      s.destinationType === 'UNEMPLOYED' &&
      s.recordStatus === 'ACTIVE' &&
      (kw(s.name, keyword) || kw(s.studentNo, keyword)) &&
      (!helpLevel || s.helpLevel === helpLevel) &&
      (!riskLevel || s.riskLevel === riskLevel)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({
    list: clone(list.slice(start, start + pageSize)).map((s) => ({ ...maskStudent(s), assignedTeacher: s.employmentTeacher })),
    total,
    page,
    pageSize
  })
}

export async function markEmployed(ids = []) {
  await delay()
  ids.forEach((id) => {
    const s = db.employmentStudents.find((x) => x.id === id)
    if (s) {
      s.destinationType = 'SIGNED'
      s.verifyStatus = 'PENDING_VERIFY'
      s.helpLevel = 'NORMAL'
      s.riskLevel = 'LOW'
      s.updateTime = db.nowText()
    }
  })
  pushAudit('RECORD', ids.join(','), '标记已就业', `${ids.length} 名学生标记为已就业（待核验）`, 'UNEMPLOYED', 'SIGNED')
  return envelope({ count: ids.length })
}

export async function markKeyHelp(ids = []) {
  await delay()
  ids.forEach((id) => {
    const s = db.employmentStudents.find((x) => x.id === id)
    if (s) {
      s.helpLevel = 'KEY_HELP'
      s.riskLevel = 'HIGH'
      s.updateTime = db.nowText()
    }
  })
  pushAudit('RECORD', ids.join(','), '标记重点帮扶', `${ids.length} 名学生纳入重点帮扶`, 'NORMAL', 'KEY_HELP')
  return envelope({ count: ids.length })
}

export async function assignEmploymentTeacher(ids = [], { teacher }) {
  await delay()
  if (!teacher) return fail('请选择就业老师')
  ids.forEach((id) => {
    const s = db.employmentStudents.find((x) => x.id === id)
    if (s) {
      s.employmentTeacher = teacher
      s.updateTime = db.nowText()
    }
  })
  pushAudit('RECORD', ids.join(','), '批量分配就业老师', `${ids.length} 名未就业学生分配给 ${teacher}`)
  return envelope({ count: ids.length })
}

/* ---------------- 跟进记录 ---------------- */
export async function getFollowUpRecords(params = {}) {
  await delay()
  const { keyword = '', status = '', page = 1, pageSize = 10 } = params
  const scopedIds = new Set(scopeFilter(db.employmentStudents).map((s) => s.id))
  let list = db.followUpRecords.filter(
    (f) => scopedIds.has(f.studentId) && (kw(f.studentName, keyword) || kw(f.content, keyword)) && (!status || f.status === status)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createFollowUp(payload) {
  await delay()
  if (!payload?.studentId || !payload?.content) return fail('学生与跟进内容为必填项')
  const s = db.employmentStudents.find((x) => x.id === payload.studentId)
  const id = `emp-f-${Date.now()}`
  db.followUpRecords.unshift({
    id,
    studentId: payload.studentId,
    studentName: s?.name || payload.studentName || '',
    className: s?.className || '',
    followTime: db.nowText(),
    way: payload.way || 'PHONE',
    content: payload.content,
    result: payload.result || '',
    nextPlan: payload.nextPlan || '',
    operator: `${currentRole().roleName}（演示账号）`,
    status: 'OPEN',
    voidReason: ''
  })
  if (s) {
    s.lastFollowUpTime = db.nowText()
    s.followUpCount += 1
  }
  pushAudit('FOLLOWUP', id, '新增跟进', `${s?.name || ''}：${payload.content}`, '', 'OPEN')
  return envelope({ id })
}

export async function updateFollowUp(id, payload) {
  await delay()
  const f = db.followUpRecords.find((x) => x.id === id)
  if (!f) return fail('跟进记录不存在')
  Object.assign(f, payload)
  pushAudit('FOLLOWUP', id, '编辑跟进', `${f.studentName} 跟进记录更新`)
  return envelope({ id })
}

export async function voidFollowUp(id, { reason }) {
  await delay()
  const f = db.followUpRecords.find((x) => x.id === id)
  if (!f) return fail('跟进记录不存在')
  if (!reason || reason.trim().length < 5) return fail('作废原因不少于 5 个字')
  f.status = 'VOIDED'
  f.voidReason = reason
  pushAudit('FOLLOWUP', id, '作废跟进', `${f.studentName}：${reason}`, 'OPEN', 'VOIDED')
  return envelope({ id })
}

/* ---------------- 企业与岗位 ---------------- */
export async function getCompanies(params = {}) {
  await delay()
  const { keyword = '', status = '', page = 1, pageSize = 10 } = params
  let list = db.companyList.filter((c) => (kw(c.name, keyword) || kw(c.industry, keyword)) && (!status || c.status === status))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createCompany(payload) {
  await delay()
  if (!payload?.name || !payload?.creditCode) return fail('企业名称与统一社会信用代码为必填项')
  const id = `emp-c-${Date.now()}`
  db.companyList.unshift({
    id,
    contactPerson: '',
    contactPhone: '',
    nature: '',
    city: '',
    cooperationLevel: '常规合作',
    status: 'ACTIVE',
    disableReason: '',
    jobCount: 0,
    hiredCount: 0,
    ...payload
  })
  pushAudit('COMPANY', id, '新增企业', payload.name, '', 'ACTIVE')
  return envelope({ id })
}

export async function updateCompany(id, payload) {
  await delay()
  const c = db.companyList.find((x) => x.id === id)
  if (!c) return fail('企业不存在')
  Object.assign(c, payload)
  pushAudit('COMPANY', id, '编辑企业', `${c.name} 信息更新`)
  return envelope({ id })
}

export async function disableCompany(id, { reason }) {
  await delay()
  const c = db.companyList.find((x) => x.id === id)
  if (!c) return fail('企业不存在')
  if (!reason || reason.trim().length < 5) return fail('停用原因不少于 5 个字')
  c.status = 'DISABLED'
  c.disableReason = reason
  db.jobList.filter((j) => j.companyId === id).forEach((j) => (j.status = 'CLOSED'))
  pushAudit('COMPANY', id, '停用企业', `${c.name}：${reason}`, 'ACTIVE', 'DISABLED')
  return envelope({ id })
}

export async function getJobs(params = {}) {
  await delay()
  const { keyword = '', status = '', companyId = '', page = 1, pageSize = 10 } = params
  let list = db.jobList.filter(
    (j) => (kw(j.title, keyword) || kw(j.companyName, keyword)) && (!status || j.status === status) && (!companyId || j.companyId === companyId)
  )
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}

export async function createJob(payload) {
  await delay()
  if (!payload?.title || !payload?.companyId) return fail('岗位名称与所属企业为必填项')
  const c = db.companyList.find((x) => x.id === payload.companyId)
  const id = `emp-j-${Date.now()}`
  db.jobList.unshift({
    id,
    companyName: c?.name || '',
    category: '',
    salaryRange: '',
    headcount: 1,
    signedCount: 0,
    status: 'OPEN',
    disableReason: '',
    publishTime: db.nowText().slice(0, 10),
    ...payload
  })
  if (c) c.jobCount += 1
  pushAudit('JOB', id, '新增岗位', `${c?.name || ''} · ${payload.title}`, '', 'OPEN')
  return envelope({ id })
}

export async function updateJob(id, payload) {
  await delay()
  const j = db.jobList.find((x) => x.id === id)
  if (!j) return fail('岗位不存在')
  Object.assign(j, payload)
  pushAudit('JOB', id, '编辑岗位', `${j.companyName} · ${j.title} 信息更新`)
  return envelope({ id })
}

export async function disableJob(id, { reason }) {
  await delay()
  const j = db.jobList.find((x) => x.id === id)
  if (!j) return fail('岗位不存在')
  if (!reason || reason.trim().length < 5) return fail('停用原因不少于 5 个字')
  j.status = 'CLOSED'
  j.disableReason = reason
  pushAudit('JOB', id, '停用岗位', `${j.companyName} · ${j.title}：${reason}`, 'OPEN', 'CLOSED')
  return envelope({ id })
}

export async function getCompanyRelatedStudents(companyId) {
  await delay()
  const c = db.companyList.find((x) => x.id === companyId)
  if (!c) return fail('企业不存在')
  const students = scopeFilter(db.employmentStudents).filter((s) => s.companyName === c.name && s.recordStatus === 'ACTIVE')
  const jobs = db.jobList.filter((j) => j.companyId === companyId)
  return envelope({ company: clone(c), students: clone(students).map(maskStudent), jobs: clone(jobs) })
}

/* ---------------- 导入 / 导出 ---------------- */
export async function validateImport(templateKey, fileName = '') {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  /* 模拟解析结果：部分行校验失败 */
  const rows =
    templateKey === 'studentList'
      ? [
          { row: 2, data: '2023010115 / 宋雨霏 / 签约就业 / 杭州云启科技', valid: true, error: '' },
          { row: 3, data: '2023010116 / 韩立诚 / 签约就业 / 宁波数联智能', valid: true, error: '' },
          { row: 4, data: '2023010117 / 何嘉树 / （空） / 未知企业', valid: false, error: '去向类型为必填项' },
          { row: 5, data: '2023019999 / 陌生学生 / 升学 / —', valid: false, error: '学号不在当前数据范围内' }
        ]
      : [
          { row: 2, data: '苏州启航电子有限公司 / 91320500MA1XXXX', valid: true, error: '' },
          { row: 3, data: '（空企业名）/ 913205XX', valid: false, error: '企业名称为必填项；信用代码格式错误' }
        ]
  return envelope({ fileName: fileName || tpl.fileName, total: rows.length, validCount: rows.filter((r) => r.valid).length, rows })
}

export async function confirmImport(templateKey, { validCount = 0, fileName = '' } = {}) {
  await delay(400)
  const tpl = db.importTemplates[templateKey]
  if (!tpl) return fail('导入模板不存在')
  pushAudit('IMPORT', templateKey, '执行导入', `${tpl.name}：导入 ${validCount} 条校验通过数据（${fileName}），失败数据未导入`)
  return envelope({ imported: validCount, skipped: 0, receiptId: `emp-imp-${Date.now()}` })
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
  await delay()
  const { bizType = '', keyword = '', page = 1, pageSize = 20 } = params
  let list = db.auditLogs.filter((a) => (!bizType || a.bizType === bizType) && (kw(a.detail, keyword) || kw(a.operator, keyword)))
  const total = list.length
  const start = (page - 1) * pageSize
  return envelope({ list: clone(list.slice(start, start + pageSize)), total, page, pageSize })
}
