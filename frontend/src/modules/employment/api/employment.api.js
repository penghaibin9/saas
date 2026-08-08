/**
 * 就业服务中心生产 API facade（A3 / P0-05）。
 *
 * 正式 /admin/employment/** 路由只允许访问真实 HTTP 服务：
 * - 禁止 import @/mocks/employment/**；
 * - 禁止 shouldTryReal → mock fallback；
 * - 禁止浏览器内存业务写入与假审计；
 * - 尚无正式后端合同的能力统一 fail-closed，并从正式动作配置隐藏。
 */
import { currentUserFromToken, request } from '@/services/http/client'
import { setPermissionPatterns, setRbacLoadFailed } from '@/security/permissionGate'

function ok(data, message = 'ok') {
  return Promise.resolve({ code: 0, data, message })
}

function fail(message, bizCode = 'UNSUPPORTED_ACTION') {
  return Promise.resolve({ code: 1, bizCode, data: null, message })
}

function toErr(error, fallback = '真实接口不可用，请稍后重试') {
  return {
    code: Number(error?.code) === 0 ? 1 : Number(error?.code || 1),
    bizCode: error?.bizCode || error?.errorCode || 'REQUEST_FAILED',
    data: null,
    message: error?.message || fallback
  }
}

async function call(fn, fallback) {
  try {
    return ok(await fn())
  } catch (error) {
    return toErr(error, fallback)
  }
}

async function callList(path, params = {}, fallback = '列表加载失败') {
  try {
    const data = await request(path, { params })
    return ok({
      list: data?.items || [],
      total: Number(data?.total || 0),
      page: Number(data?.page || params.page || 1),
      pageSize: Number(data?.pageSize || params.pageSize || 20)
    })
  } catch (error) {
    return toErr(error, fallback)
  }
}

function hasPermission(patterns = [], code) {
  const list = Array.isArray(patterns) ? patterns.map(String) : []
  if (list.includes('*') || list.includes(code)) return true
  return list.some((pattern) => {
    if (pattern.endsWith('.*')) return code === pattern.slice(0, -2) || code.startsWith(pattern.slice(0, -1))
    if (pattern.startsWith('*.')) return code.endsWith(pattern.slice(1))
    return false
  })
}

function action(patterns, code, reason, { visible = true, readonly = false, readonlyReason = '' } = {}) {
  const permitted = !!code && hasPermission(patterns, code)
  const allowed = permitted && !readonly
  return {
    visible: !!visible,
    allowed,
    reason: allowed ? '' : (readonly && permitted ? (readonlyReason || '当前学校为只读环境') : reason)
  }
}

function unsupportedAction(reason) {
  return { visible: false, allowed: false, reason }
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]))
  }
  return value
}

function idempotencyHeaders(actionName, payload = {}) {
  const raw = JSON.stringify(canonical({ actionName, payload }))
  let hash = 2166136261
  for (let i = 0; i < raw.length; i += 1) {
    hash ^= raw.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return { 'Idempotency-Key': `employment-${actionName}-${(hash >>> 0).toString(16).padStart(8, '0')}` }
}

const STATUS_OPTIONS = {
  destinationType: [
    { value: 'SIGNED', label: '签约就业' },
    { value: 'FLEXIBLE', label: '灵活就业' },
    { value: 'FURTHER_STUDY', label: '升学' },
    { value: 'ENLISTED', label: '入伍' },
    { value: 'STARTUP', label: '自主创业' },
    { value: 'FREELANCE', label: '自由职业' },
    { value: 'UNEMPLOYED', label: '待就业' }
  ],
  verifyStatus: [
    { value: 'PENDING_VERIFY', label: '待核验' },
    { value: 'VERIFIED', label: '已核验' },
    { value: 'RETURNED', label: '已退回' }
  ],
  materialStatus: [
    { value: 'SUBMITTED', label: '待审核' },
    { value: 'REVIEWING', label: '审核中' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '退回补充' },
    { value: 'REJECTED', label: '已驳回' }
  ],
  materialType: [
    { value: 'AGREEMENT', label: '就业协议' },
    { value: 'CONTRACT', label: '劳动合同' },
    { value: 'OFFER', label: '录用通知' },
    { value: 'STUDY_PROOF', label: '升学证明' },
    { value: 'ENLIST_PROOF', label: '入伍证明' },
    { value: 'STARTUP_PROOF', label: '创业证明' },
    { value: 'OTHER', label: '其他材料' }
  ],
  helpLevel: [
    { value: 'NORMAL', label: '常规跟进' },
    { value: 'KEY_HELP', label: '重点帮扶' }
  ],
  recordStatus: [
    { value: 'ACTIVE', label: '有效' },
    { value: 'VOIDED', label: '已作废' }
  ],
  followUpWay: [
    { value: 'PHONE', label: '电话联系' },
    { value: 'FACE', label: '面谈' },
    { value: 'RECOMMEND', label: '岗位推荐' },
    { value: 'VISIT', label: '走访' }
  ],
  followUpStatus: [
    { value: 'OPEN', label: '跟进中' },
    { value: 'CLOSED', label: '已闭环' },
    { value: 'VOIDED', label: '已作废' }
  ],
  companyStatus: [
    { value: 'ACTIVE', label: '合作中' },
    { value: 'DISABLED', label: '已停用' }
  ],
  jobStatus: [
    { value: 'OPEN', label: '招聘中' },
    { value: 'CLOSED', label: '已停止' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ]
}

const FIELD_COLUMNS = {
  studentList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'studentNo', title: '学号', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'destinationType', title: '去向类型', default: true },
    { key: 'companyName', title: '单位 / 院校', default: true },
    { key: 'jobTitle', title: '岗位', default: false },
    { key: 'salaryRange', title: '薪资区间', sensitive: true, default: false },
    { key: 'phone', title: '手机号', sensitive: true, default: false },
    { key: 'verifyStatus', title: '核验状态', default: true },
    { key: 'materialStatus', title: '材料状态', default: true },
    { key: 'helpLevel', title: '帮扶级别', default: true },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  materialList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'materialType', title: '材料类型', default: true },
    { key: 'fileName', title: '材料文件', default: true },
    { key: 'submitTime', title: '提交时间', default: true },
    { key: 'status', title: '审核状态', default: true },
    { key: 'reviewer', title: '审核人', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  unemployedList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'unemployedReason', title: '未就业原因', default: true },
    { key: 'helpLevel', title: '帮扶级别', default: true },
    { key: 'riskLevel', title: '风险', default: true },
    { key: 'assignedTeacher', title: '负责老师', default: true },
    { key: 'lastFollowUpTime', title: '最近跟进', default: true },
    { key: 'followUpCount', title: '跟进次数', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  followUpList: [
    { key: 'studentName', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'followTime', title: '跟进时间', default: true },
    { key: 'way', title: '跟进方式', default: true },
    { key: 'content', title: '跟进内容', default: true },
    { key: 'result', title: '结果', default: true },
    { key: 'operator', title: '记录人', default: false },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ]
}

const BATCH_ACTIONS = {
  studentList: [
    { key: 'batchMarkStatus', label: '批量标记去向', permission: 'employment.record.batchMarkStatus' }
  ],
  materialList: [],
  unemployedList: [
    { key: 'batchAssign', label: '批量分配就业老师', permission: 'employment.unemployed.assign' }
  ],
  followUpList: []
}

const EXPORT_GROUPS = {
  studentList: [{ key: 'base', label: '就业台账', fields: ['姓名', '学号', '班级', '去向', '单位', '核验', '帮扶'] }],
  materialList: [{ key: 'base', label: '就业台账导出', fields: ['当前正式导出按就业学生台账生成'] }],
  unemployedList: [{ key: 'base', label: '就业台账导出', fields: ['当前正式导出按就业学生台账生成'] }],
  followUpList: [{ key: 'base', label: '就业台账导出', fields: ['当前正式导出按就业学生台账生成'] }]
}

function exportOptions(listKey) {
  return {
    scopes: [{ value: 'SCOPE_ALL', label: '当前账号数据范围内全部' }],
    fieldGroups: EXPORT_GROUPS[listKey] || EXPORT_GROUPS.studentList,
    maskDefault: true,
    idCardPlainForbidden: true,
    watermarkNote: '文件由服务端生成，按当前 dataScope 收敛，敏感字段脱敏并记录导出用途。',
    auditNotice: '本次导出将写入服务端审计，请填写真实用途。',
    purposeRequired: true
  }
}

function permissionActions(patterns, readonlyTenant, readonlyReason) {
  const opts = { readonly: readonlyTenant, readonlyReason }
  return {
    'employment.record.view': action(patterns, 'employment.student.view', '无就业学生查看权限'),
    'employment.record.create': action(patterns, 'employment.student.manage', '无就业学生维护权限', opts),
    'employment.record.edit': action(patterns, 'employment.student.manage', '无就业学生维护权限', opts),
    'employment.record.void': action(patterns, 'employment.student.manage', '无就业学生维护权限', opts),
    'employment.record.import': unsupportedAction('就业导入尚未接入正式文件任务链'),
    'employment.record.export': action(patterns, 'employment.export', '无就业数据导出权限', opts),
    'employment.record.batchRemind': unsupportedAction('批量提醒尚未接入正式消息发送链'),
    'employment.record.batchMarkStatus': action(patterns, 'employment.student.manage', '无就业学生维护权限', opts),
    'employment.material.review': action(patterns, 'employment.material.approve', '无就业材料审核权限', opts),
    'employment.material.export': action(patterns, 'employment.export', '无就业数据导出权限', opts),
    'employment.followup.create': action(patterns, 'employment.followup.manage', '无就业跟进维护权限', opts),
    'employment.followup.edit': unsupportedAction('跟进记录编辑尚无正式后端合同；请新增更正记录或作废重建'),
    'employment.followup.void': action(patterns, 'employment.followup.manage', '无就业跟进维护权限', opts),
    'employment.followup.export': action(patterns, 'employment.export', '无就业数据导出权限', opts),
    'employment.unemployed.assign': action(patterns, 'employment.unemployed.assign', '无就业老师分配权限', opts),
    'employment.unemployed.markEmployed': action(patterns, 'employment.unemployed.manage', '无未就业学生维护权限', opts),
    'employment.unemployed.markKeyHelp': action(patterns, 'employment.unemployed.manage', '无未就业学生维护权限', opts),
    'employment.unemployed.export': action(patterns, 'employment.export', '无就业数据导出权限', opts),
    'employment.company.create': action(patterns, 'employment.company.manage', '无企业维护权限', opts),
    'employment.company.edit': unsupportedAction('企业编辑尚无正式后端合同'),
    'employment.company.disable': action(patterns, 'employment.company.manage', '无企业维护权限', opts),
    'employment.company.import': unsupportedAction('企业导入尚未接入正式文件任务链'),
    'employment.company.export': action(patterns, 'employment.export', '无就业数据导出权限', opts),
    'employment.job.create': action(patterns, 'employment.job.manage', '无岗位维护权限', opts),
    'employment.job.edit': unsupportedAction('岗位编辑尚无正式后端合同'),
    'employment.job.disable': action(patterns, 'employment.job.manage', '无岗位维护权限', opts),
    'employment.audit.view': action(patterns, 'employment.audit.view', '无就业审计查看权限'),
    'employment.columns.setting': action(patterns, 'employment.student.view', '无就业学生查看权限')
  }
}

export async function getEmploymentContext() {
  const tokenUser = currentUserFromToken() || {}
  let schoolName = '管理端'
  let platformDisplayName = '高校学生全生命周期管理平台'
  let roleName = tokenUser.currentRoleCode || tokenUser.userType || '当前身份'
  let roleCode = tokenUser.currentRoleCode || ''
  let permissionPatterns = []
  let readonlyTenant = false
  let readonlyReason = ''
  let permissionServiceError = ''
  let currentRole = { roleId: roleCode, roleCode, roleName }

  try {
    const me = await request('/auth/me')
    schoolName = me?.tenantName || me?.user?.tenantName || me?.tenant?.name || schoolName
    platformDisplayName = me?.platformDisplayName || platformDisplayName
    const realName = me?.realName || me?.user?.realName || ''
    try {
      const rc = await request('/rbac/current-context')
      setRbacLoadFailed(false)
      permissionPatterns = Array.isArray(rc?.permissionPatterns) ? rc.permissionPatterns : []
      readonlyTenant = !!rc?.readonlyTenant
      readonlyReason = rc?.readonlyReason || ''
      const cr = rc?.currentRole || {}
      roleName = cr.roleName || roleName
      roleCode = cr.roleCode || roleCode
      currentRole = {
        roleId: cr.contextId || roleCode,
        roleCode,
        roleName: realName ? `${realName} · ${roleName}` : roleName,
        contextId: cr.contextId || ''
      }
    } catch (error) {
      permissionServiceError = error?.message || '权限服务加载失败'
      setRbacLoadFailed(true, permissionServiceError)
      permissionPatterns = []
    }
  } catch (error) {
    permissionServiceError = error?.message || '身份服务加载失败'
    setRbacLoadFailed(true, permissionServiceError)
  }

  setPermissionPatterns(permissionPatterns)
  const roReason = readonlyReason || '当前学校为只读环境，禁止业务写入'
  return ok({
    tenantBrandConfig: {
      schoolName,
      platformDisplayName,
      watermarkText: `${schoolName} · 就业服务中心`
    },
    roles: [],
    currentRole,
    dataScope: { code: 'SERVER_ENFORCED', name: '按当前身份配置的后端数据范围' },
    permissionPatterns,
    permissionActions: permissionActions(permissionPatterns, readonlyTenant, roReason),
    permissionServiceError,
    readonlyTenant,
    readonlyReason: readonlyTenant ? roReason : ''
  })
}

export function switchEmploymentRole() {
  return fail('就业模块不提供本地角色切换；请使用全局身份切换，服务端会重新签发权限上下文', 'USE_GLOBAL_ROLE_SWITCH')
}

export function getStatusOptions() {
  return ok(STATUS_OPTIONS)
}

export function getFilterOptions() {
  return call(() => request('/employment/options'), '就业筛选条件加载失败')
}

export function getFieldColumns(listKey) {
  return ok(FIELD_COLUMNS[listKey] || [])
}

export function getBatchActions(listKey) {
  return ok(BATCH_ACTIONS[listKey] || [])
}

export function getImportTemplate() {
  return ok(null, '正式就业导入未开放')
}

export function getExportOptions(listKey) {
  return ok(exportOptions(listKey))
}

export function getEmploymentDashboard() {
  return call(() => request('/employment/dashboard'), '就业看板加载失败')
}

export function getEmploymentStudents(params = {}) {
  return callList('/employment/students', params, '就业学生列表加载失败')
}

export function getEmploymentStudentDetail(id) {
  return call(() => request(`/employment/students/${id}`), '就业学生详情加载失败')
}

export function createEmploymentRecord(payload) {
  return call(() => request('/employment/students', {
    method: 'POST', body: payload, headers: idempotencyHeaders('student-create', payload)
  }), '新增就业记录失败')
}

export function updateEmploymentRecord(id, payload) {
  return call(() => request(`/employment/students/${id}`, {
    method: 'PUT', body: payload, headers: idempotencyHeaders('student-update', { id, ...payload })
  }), '更新就业记录失败')
}

export function voidEmploymentRecord(id, { reason }) {
  return call(() => request(`/employment/students/${id}/void`, {
    method: 'POST', body: { reason }, headers: idempotencyHeaders('student-void', { id, reason })
  }), '作废就业记录失败')
}

export function batchRemindStudents() {
  return fail('批量提醒尚未接入正式消息发送链，已禁止浏览器内存假成功')
}

export function batchMarkDestination(ids = [], destinationType) {
  const body = { ids, destinationType }
  return call(() => request('/employment/students/mark-destination', {
    method: 'POST', body, headers: idempotencyHeaders('mark-destination', body)
  }), '批量标记就业去向失败')
}

export function getEmploymentMaterials(params = {}) {
  return callList('/employment/materials', params, '就业材料列表加载失败')
}

export function getMaterialReviewDetail(id) {
  return call(() => request(`/employment/materials/${id}`), '就业材料详情加载失败')
}

export function approveMaterial(id, { comment = '' } = {}) {
  const body = { comment }
  return call(() => request(`/employment/materials/${id}/approve`, {
    method: 'POST', body, headers: idempotencyHeaders('material-approve', { id, ...body })
  }), '材料审核通过失败')
}

export function returnMaterial(id, { reason }) {
  const body = { reason }
  return call(() => request(`/employment/materials/${id}/return`, {
    method: 'POST', body, headers: idempotencyHeaders('material-return', { id, ...body })
  }), '材料退回失败')
}

export function batchReviewMaterials() {
  return fail('材料批量审核尚无正式批量事务合同，已关闭该入口')
}

export function getUnemployedStudents(params = {}) {
  return callList('/employment/unemployed', params, '未就业学生列表加载失败')
}

export function markEmployed(ids = []) {
  const body = { ids }
  return call(() => request('/employment/unemployed/mark-employed', {
    method: 'POST', body, headers: idempotencyHeaders('mark-employed', body)
  }), '标记已就业失败')
}

export function markKeyHelp(ids = []) {
  const body = { ids }
  return call(() => request('/employment/unemployed/mark-key-help', {
    method: 'POST', body, headers: idempotencyHeaders('mark-key-help', body)
  }), '标记重点帮扶失败')
}

export function assignEmploymentTeacher(ids = [], { teacher }) {
  const body = { ids, teacher }
  return call(() => request('/employment/unemployed/assign-teacher', {
    method: 'POST', body, headers: idempotencyHeaders('assign-teacher', body)
  }), '分配就业老师失败')
}

export function getFollowUpRecords(params = {}) {
  return callList('/employment/followups', params, '就业跟进列表加载失败')
}

export function createFollowUp(payload) {
  return call(() => request('/employment/followups', {
    method: 'POST', body: payload, headers: idempotencyHeaders('followup-create', payload)
  }), '新增就业跟进失败')
}

export function updateFollowUp() {
  return fail('跟进记录编辑尚无正式后端合同；请作废错误记录后新增一条更正记录')
}

export function voidFollowUp(id, { reason }) {
  const body = { reason }
  return call(() => request(`/employment/followups/${id}/void`, {
    method: 'POST', body, headers: idempotencyHeaders('followup-void', { id, reason })
  }), '作废就业跟进失败')
}

export function getCompanies(params = {}) {
  return callList('/employment/companies', params, '企业列表加载失败')
}

export function createCompany(payload) {
  return call(() => request('/employment/companies', { method: 'POST', body: payload }), '新增企业失败')
}

export function updateCompany() {
  return fail('企业编辑尚无正式后端合同，已禁止内存修改')
}

export function disableCompany(id, { reason }) {
  return call(() => request(`/employment/companies/${id}/disable`, { method: 'POST', body: { reason } }), '停用企业失败')
}

export function getJobs(params = {}) {
  return callList('/employment/jobs', params, '岗位列表加载失败')
}

export function createJob(payload) {
  return call(() => request('/employment/jobs', { method: 'POST', body: payload }), '新增岗位失败')
}

export function updateJob() {
  return fail('岗位编辑尚无正式后端合同，已禁止内存修改')
}

export function disableJob(id, { reason }) {
  return call(() => request(`/employment/jobs/${id}/disable`, { method: 'POST', body: { reason } }), '停用岗位失败')
}

export function getCompanyRelatedStudents() {
  return fail('企业关联就业学生聚合尚无正式后端合同')
}

export function validateImport() {
  return fail('就业导入尚未接入正式文件任务链，已禁止本地模拟校验')
}

export function confirmImport() {
  return fail('就业导入尚未接入正式文件任务链，已禁止本地模拟导入')
}

export function createExport(listKey, payload = {}) {
  const purpose = String(payload.purpose || '').trim()
  if (purpose.length < 5) return fail('导出用途必填且不少于 5 个字', 'VALIDATION_ERROR')
  if (payload.scope && payload.scope !== 'SCOPE_ALL') {
    return fail('当前正式就业导出仅支持“当前账号数据范围内全部”；筛选/选中冻结导出尚未开放', 'UNSUPPORTED_EXPORT_SCOPE')
  }
  const body = { purpose }
  return call(async () => {
    const data = await request('/export/domain/employment', {
      method: 'POST', body, headers: idempotencyHeaders('export', { listKey, purpose })
    })
    return {
      ...data,
      downloadUrl: data?.taskId ? `/api/v1/export/tasks/${data.taskId}/download` : '',
      watermarkText: data?.securityNotice || '服务端水印与审计已启用',
      auditId: data?.taskId || ''
    }
  }, '就业数据导出失败')
}

export function getAuditLogs(params = {}) {
  return callList('/employment/audit-logs', params, '就业审计加载失败')
}
