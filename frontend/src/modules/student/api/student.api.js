/**
 * 学生中心生产 API facade。
 *
 * A2 / P0-02 + P0-03：正式学生路由只允许访问真实 HTTP/领域服务。
 * 本文件禁止 import mocks/**、roleProfiles、mockStudents，也禁止浏览器内存业务写入。
 * 未具备真实服务端能力的动作一律 fail-closed，并给出正确业务入口。
 */
import { request } from '@/services/http/client'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

function ok(data, message = 'ok') {
  return Promise.resolve({ code: 0, data, message })
}

function fail(message, bizCode = 'UNSUPPORTED_ACTION') {
  return Promise.resolve({ code: 1, bizCode, data: null, message })
}

function errorResult(error, fallback = '请求失败，请稍后重试') {
  return {
    code: Number(error?.code) === 0 ? 1 : Number(error?.code || 1),
    bizCode: error?.bizCode || error?.errorCode || 'REQUEST_FAILED',
    data: null,
    message: error?.message || fallback
  }
}

async function safe(fn, fallback) {
  try {
    return await fn()
  } catch (error) {
    return errorResult(error, fallback)
  }
}

function hasPermission(patterns = [], code) {
  const list = Array.isArray(patterns) ? patterns.map(String) : []
  if (list.includes('*') || list.includes(code)) return true
  return list.some((pattern) => {
    if (!pattern.endsWith('.*')) return false
    return code.startsWith(pattern.slice(0, -1))
  })
}

function action(visible, allowed, reason = '') {
  return { visible: !!visible, allowed: !!allowed, reason: allowed ? '' : reason }
}

const STATUS_OPTIONS = {
  studentStatus: [
    { value: 'ADMITTED', label: '已录取' },
    { value: 'ACTIVE', label: '在读' },
    { value: 'SUSPENDED', label: '休学/保留学籍' },
    { value: 'GRADUATED', label: '已毕业' },
    { value: 'DROPPED', label: '退学' },
    { value: 'VOIDED', label: '已作废' },
    { value: 'UNKNOWN', label: '未知' }
  ],
  studentStatusFlow: [
    { value: 'ADMITTED', label: '已录取' },
    { value: 'ACTIVE', label: '在读' },
    { value: 'SUSPENDED', label: '休学/保留学籍' },
    { value: 'GRADUATED', label: '已毕业' },
    { value: 'DROPPED', label: '退学' }
  ],
  identityVerifyStatus: [
    { value: 'NOT_CONFIGURED', label: '核验服务未配置' },
    { value: 'UNKNOWN', label: '未知' },
    { value: 'PENDING', label: '待核验' },
    { value: 'VERIFIED', label: '已核验' },
    { value: 'REJECTED', label: '未通过' },
    { value: 'ABNORMAL', label: '异常' }
  ],
  accountBindStatus: [
    { value: 'UNKNOWN', label: '未知' },
    { value: 'BOUND', label: '已绑定' },
    { value: 'UNBOUND', label: '未绑定' },
    { value: 'SUSPENDED', label: '已暂停' }
  ],
  riskLevel: [
    { value: 'NONE', label: '无' },
    { value: 'LOW', label: '低' },
    { value: 'MEDIUM', label: '中' },
    { value: 'HIGH', label: '高' }
  ],
  riskTagType: [
    { value: 'ACADEMIC_WARNING', label: '学业预警' },
    { value: 'LEAVE_OVERDUE', label: '请假异常' },
    { value: 'DORM', label: '宿舍' },
    { value: 'MENTAL', label: '心理' },
    { value: 'DISCIPLINE', label: '违纪' },
    { value: 'INTERNSHIP', label: '实习' },
    { value: 'GRADUATION_DESIGN', label: '毕业设计' },
    { value: 'EMPLOYMENT', label: '就业' },
    { value: 'FAMILY', label: '家庭' },
    { value: 'MANUAL', label: '人工登记' }
  ]
}

const FIELD_COLUMNS = {
  studentList: [
    { key: 'student', title: '学生', visible: true, locked: true },
    { key: 'orgPath', title: '班级 / 学院 / 专业', visible: true, locked: false },
    { key: 'phone', title: '手机号', visible: true, locked: false },
    { key: 'idCard', title: '身份证号', visible: false, locked: false },
    { key: 'studentStatus', title: '学籍状态', visible: true, locked: false },
    { key: 'identityVerifyStatus', title: '身份核验', visible: true, locked: false },
    { key: 'riskLevel', title: '风险', visible: true, locked: false },
    { key: 'dataCompleteness', title: '主档完整度', visible: true, locked: false },
    { key: 'actions', title: '操作', visible: true, locked: true }
  ]
}

const EXPORT_OPTIONS = {
  scopes: [
    { value: 'CURRENT_SCOPE', label: '当前数据范围', desc: '按当前账号 dataScope 导出全部可见学生' },
    { value: 'SELECTED', label: '仅导出所选', desc: '需要服务端支持精确 ID 冻结后才能执行' }
  ],
  fieldGroups: [
    {
      key: 'basic', label: '基础信息', fields: [
        { key: 'name', label: '姓名', sensitive: false },
        { key: 'studentNo', label: '学号', sensitive: false },
        { key: 'orgPath', label: '组织归属', sensitive: false },
        { key: 'studentStatus', label: '学籍状态', sensitive: false }
      ]
    },
    {
      key: 'sensitive', label: '敏感信息', fields: [
        { key: 'phone', label: '手机号', sensitive: true },
        { key: 'idCard', label: '身份证号', sensitive: true }
      ]
    }
  ],
  purposes: [
    { value: 'WORK', label: '日常工作核对' },
    { value: 'REPORT', label: '正式报表材料' },
    { value: 'AUDIT', label: '审计 / 检查' }
  ]
}

const STAGE_TO_STATUS = {
  ADMITTED: 'ADMITTED',
  ORIENTATION: 'ADMITTED',
  ENROLLED: 'ACTIVE',
  IN_SCHOOL: 'ACTIVE',
  INTERNSHIP: 'ACTIVE',
  GRADUATION_DESIGN: 'ACTIVE',
  EMPLOYMENT: 'ACTIVE',
  SUSPENDED: 'SUSPENDED',
  GRADUATED: 'GRADUATED',
  DROPPED: 'DROPPED',
  WITHDRAWN: 'DROPPED'
}

function coreCompleteness(row = {}) {
  // 仅使用真实接口已经返回的主档字段计算“核心字段完整度”，绝不补固定 90%。
  const fields = [
    ['studentNo', row.studentNo],
    ['name', row.realName || row.name],
    ['gender', row.gender],
    ['collegeId', row.collegeId],
    ['majorId', row.majorId],
    ['classId', row.classId],
    ['grade', row.grade]
  ]
  const missingFields = fields.filter(([, value]) => !String(value ?? '').trim()).map(([key]) => key)
  return {
    value: Math.round(((fields.length - missingFields.length) / fields.length) * 100),
    missingFields
  }
}

function studentRow(row = {}) {
  const completeness = Number.isFinite(Number(row.dataCompleteness))
    ? { value: Number(row.dataCompleteness), missingFields: row.missingFields || [] }
    : coreCompleteness(row)
  const phoneMasked = row.phoneMasked === '1**********' ? '' : (row.phoneMasked || row.phone || '')
  return {
    studentId: String(row.studentId || row.id || ''),
    id: String(row.studentId || row.id || ''),
    studentNo: row.studentNo || '',
    name: row.realName || row.name || '',
    realName: row.realName || row.name || '',
    gender: row.gender || '',
    collegeId: String(row.collegeId || ''),
    collegeName: row.collegeName || '',
    majorId: String(row.majorId || ''),
    majorName: row.majorName || '',
    classId: String(row.classId || ''),
    className: row.className || '',
    grade: row.grade || '',
    counselorName: row.counselorName || '—',
    phone: phoneMasked,
    idCard: row.idCardMasked || row.idCard || '',
    studentStatus: row.isDeleted ? 'VOIDED' : (row.studentStatusUi || STAGE_TO_STATUS[row.currentStage] || row.studentStatus || 'UNKNOWN'),
    identityVerifyStatus: row.identityVerifyStatus || 'NOT_CONFIGURED',
    accountBindStatus: row.accountBindStatus || 'UNKNOWN',
    riskLevel: row.riskLevel || 'NONE',
    dataCompleteness: completeness.value,
    missingFields: completeness.missingFields,
    supportedActions: Array.isArray(row.supportedActions) ? row.supportedActions : [],
    enrollDate: row.enrollDate || '',
    version: Number(row.version ?? 0),
    voided: !!row.isDeleted || row.studentStatus === 'VOIDED',
    voidReason: row.voidReason || '',
    updatedAt: String(row.updatedAt || '').replace('T', ' ').slice(0, 16)
  }
}

function detailRow(row = {}) {
  return {
    ...studentRow(row),
    contacts: Array.isArray(row.contacts) ? row.contacts : [],
    timeline: Array.isArray(row.timeline) ? row.timeline : [],
    statusHistory: Array.isArray(row.statusHistory) ? row.statusHistory : [],
    identityRecords: [],
    corrections: [],
    riskTags: [],
    auditTrail: [],
    orientation: { steps: [] },
    serviceRecords: [],
    academic: { gpa: '—', earnedCredits: 0, requiredCredits: 0, courses: [], warningLevel: '' },
    internship: null,
    graduationDesign: null,
    employment: null,
    capabilityStatus: {
      identityVerification: 'NOT_CONFIGURED',
      crossModule360Aggregation: 'PARTIAL'
    }
  }
}

function fromBackendStatusChange(x = {}) {
  return {
    id: x.changeId,
    studentId: x.studentId,
    studentName: x.realName || '',
    className: x.toClassId ? `班级#${x.toClassId}` : '',
    fromStatus: x.fromStatus || '',
    toStatus: x.toStatus || '',
    reason: x.reason || '',
    auditStatus: x.status,
    operatedAt: x.effectiveDate || x.updatedAt || '',
    operator: x.operatorName || '',
    roleName: x.operatorRole || '',
    attachment: '',
    version: x.version
  }
}

const CORRECTION_STATUS_TO_UI = { PENDING: 'PENDING_REVIEW', APPROVED: 'APPROVED', REJECTED: 'RETURNED' }
const CORRECTION_STATUS_TO_API = { PENDING_REVIEW: 'PENDING', APPROVED: 'APPROVED', RETURNED: 'REJECTED' }
function fromBackendCorrection(r = {}) {
  return {
    id: r.correctionId,
    studentId: r.studentId,
    studentName: r.realName || '',
    studentNo: r.studentNo || '',
    className: r.className || '',
    fieldKey: r.fieldKey,
    fieldLabel: r.fieldLabel,
    oldValue: r.oldValue,
    newValue: r.newValue,
    sensitive: !!r.sensitive,
    reason: r.reason || '',
    attachments: (r.materialFileIds || []).map((fid) => `附件#${fid}`),
    channel: r.channel || '教务发起',
    submitTime: r.createdAt || '',
    status: CORRECTION_STATUS_TO_UI[r.status] || r.status,
    reviewer: r.reviewerName || '',
    reviewTime: r.reviewedAt || '',
    reviewComment: r.reviewNote || ''
  }
}

const RISK_SOURCE_LABEL = {
  LEAVE_OVERDUE: '请假异常', ACADEMIC_WARNING: '学业预警', DORM: '宿舍', MENTAL: '心理',
  DISCIPLINE: '违纪', INTERNSHIP: '实习', GRADUATION_DESIGN: '毕业设计',
  EMPLOYMENT: '就业', FAMILY: '家庭', MANUAL: '人工创建'
}
function fromBackendRisk(x = {}) {
  return {
    id: x.riskId,
    studentId: x.studentId,
    studentName: x.realName || '',
    studentNo: x.studentNo || '',
    className: '',
    tagType: x.source,
    tagTypeLabel: RISK_SOURCE_LABEL[x.source] || x.source,
    level: x.riskLevel,
    title: x.title || '',
    description: x.detail || '',
    source: x.source,
    sourceLabel: RISK_SOURCE_LABEL[x.source] || x.source,
    status: x.status,
    statusLabel: x.statusLabel || x.status,
    owner: x.ownerName || '',
    ownerId: x.ownerId || '',
    mentalMasked: !!x.mentalMasked,
    createdAt: x.createdAt || '',
    voidReason: '',
    followUps: [],
    version: x.version
  }
}

function permissionActions(patterns = []) {
  const view = hasPermission(patterns, 'student.profile.view')
  const manage = hasPermission(patterns, 'student.profile.manage')
  const create = manage || hasPermission(patterns, 'student.profile.create')
  const update = manage || hasPermission(patterns, 'student.profile.update')
  const restore = manage || hasPermission(patterns, 'student.profile.restore')
  const exportAllowed = hasPermission(patterns, 'student.export')
  const importAllowed = hasPermission(patterns, 'systemAdmin.user.import') || hasPermission(patterns, 'academicAffairs.roster.import')
  const auditAllowed = hasPermission(patterns, 'systemAdmin.audit.sensitive.view') || hasPermission(patterns, 'systemAdmin.audit.view')
  return {
    viewList: action(view, view, '无学生主档查看权限'),
    createStudent: action(create, create, '无学生主档新增权限'),
    editStudent: action(update, update, '无学生主档维护权限'),
    voidStudent: action(update, update, '无学生主档维护权限'),
    restoreStudent: action(restore, restore, '无学生主档恢复权限'),
    viewSensitive: action(view, hasPermission(patterns, 'student.profile.sensitive.view'), '敏感字段仅授权岗位可查看'),
    importStudents: action(importAllowed, importAllowed, '学生批量导入请使用系统管理/教务正式导入链路'),
    exportStudents: action(exportAllowed, exportAllowed, '无学生数据导出权限'),
    viewAudit: action(auditAllowed, auditAllowed, '无敏感审计查看权限'),
    columnSettings: action(view, view, '无学生主档查看权限'),
    changeStatus: action(view, view, ''),
    batchChangeStatus: action(false, false, '学籍异动必须逐人走教务审批，不提供批量直改'),
    exportStatusRecords: action(exportAllowed, exportAllowed, '无学生数据导出权限'),
    batchAssignClass: action(false, false, '班级变更必须走教务中心“学籍异动”审批'),
    batchAssignCounselor: action(false, false, '辅导员责任按班级维护，请到学工中心“辅导员责任关系”办理'),
    batchRemind: action(false, false, '学生批量提醒尚未接入真实通知投递链路'),
    identityReview: action(false, false, '第三方身份核验服务当前未配置'),
    identityAbnormal: action(false, false, '第三方身份核验服务当前未配置')
  }
}

function normalizeClassOptions(payload) {
  const rows = payload?.items || payload?.list || []
  return rows.map((row) => ({
    value: String(row.classId || row.id || ''),
    label: row.className || row.name || `班级#${row.classId || row.id}`,
    collegeId: String(row.collegeId || ''),
    collegeName: row.collegeName || '',
    majorId: String(row.majorId || ''),
    majorName: row.majorName || '',
    grade: row.grade || ''
  })).filter((x) => x.value)
}

async function buildContext() {
  const [brand, ctx, todoSummary, classesResult] = await Promise.all([
    request('/tenant/brand'),
    request('/rbac/current-context'),
    request('/todos/summary').catch(() => null),
    request('/student-affairs/classes', { params: { page: 1, pageSize: 200 } }).catch(() => null)
  ])
  const patterns = Array.isArray(ctx?.permissionPatterns) ? ctx.permissionPatterns : []
  const classes = normalizeClassOptions(classesResult)
  const colleges = [...new Map(classes.filter((x) => x.collegeId).map((x) => [x.collegeId, { value: x.collegeId, label: x.collegeName || `学院#${x.collegeId}` }])).values()]
  const majors = [...new Map(classes.filter((x) => x.majorId).map((x) => [x.majorId, { value: x.majorId, label: x.majorName || `专业#${x.majorId}` }])).values()]
  const grades = [...new Set(classes.map((x) => x.grade).filter(Boolean))].sort().map((x) => ({ value: x, label: x }))
  const role = ctx?.currentRole || {}
  const scope = ctx?.dataScope || {}
  return {
    tenantBrandConfig: {
      schoolName: brand?.schoolName || '',
      platformName: brand?.platformDisplayName || '',
      platformDisplayName: brand?.platformDisplayName || brand?.schoolName || '',
      watermarkText: brand?.watermarkText || brand?.schoolName || ''
    },
    currentRole: {
      ...role,
      roleCode: role.roleCode || '',
      roleName: role.roleName || '—',
      userName: role.userName || role.realName || ''
    },
    dataScope: {
      ...scope,
      scopeName: scope.scopeName || scope.name || '未声明数据范围',
      name: scope.scopeName || scope.name || '未声明数据范围'
    },
    permissionPatterns: patterns,
    moduleEntitlements: Array.isArray(ctx?.moduleEntitlements) ? ctx.moduleEntitlements : [],
    moduleStates: ctx?.moduleStates || {},
    moduleAccessHealthy: ctx?.moduleAccessHealthy !== false,
    moduleAccessError: ctx?.moduleAccessError || '',
    readonlyTenant: !!ctx?.readonlyTenant,
    readonlyReason: ctx?.readonlyReason || '',
    permissionActions: permissionActions(patterns),
    supportedActions: permissionActions(patterns),
    statusOptions: STATUS_OPTIONS,
    filterOptions: { colleges, majors, classes, grades, counselors: [] },
    pendingCount: Number(todoSummary?.pending || 0),
    identityVerificationCapability: {
      status: 'NOT_CONFIGURED',
      message: '第三方实名/人脸核验服务当前未配置；新生人工信息核验请使用数字迎新。'
    },
    realApi: true,
    ctxKey: [
      role.contextId || '', role.permissionVersion || '', role.roleCode || '',
      [...patterns].sort().join(','),
      ...(Array.isArray(ctx?.moduleEntitlements) ? [[...ctx.moduleEntitlements].sort().join(',')] : [''])
    ].join('|')
  }
}

export const studentApi = {
  async getContext() {
    return safe(async () => ok(await buildContext()), '学生中心权限上下文加载失败')
  },

  async getDashboardSummary() {
    return safe(async () => {
      const [students, changes, audits] = await Promise.all([
        this.getStudents({ page: 1, pageSize: 1 }),
        this.getStatusRecords({ page: 1, pageSize: 5 }),
        this.getAuditLogs({ page: 1, pageSize: 5 })
      ])
      if (students.code !== 0) return students
      const total = Number(students.data?.total || 0)
      return ok({
        stats: [
          { key: 'total', label: '当前范围学生', value: total },
          { key: 'identity', label: '身份核验服务', value: '未配置', tone: 'default' }
        ],
        flow: [],
        todos: [],
        recentChanges: changes.code === 0 ? (changes.data?.list || []) : [],
        recentAudits: audits.code === 0 ? (audits.data?.list || []) : [],
        asOf: new Date().toISOString(),
        qualityFlags: ['IDENTITY_VERIFICATION_NOT_CONFIGURED', 'CROSS_MODULE_360_PARTIAL']
      })
    }, '学生中心看板加载失败')
  },

  async getStudents(params = {}) {
    return safe(async () => {
      const data = await request('/students', {
        params: {
          page: params.page || 1,
          pageSize: params.pageSize || 10,
          keyword: params.keyword || undefined,
          collegeId: params.collegeId || undefined,
          majorId: params.majorId || undefined,
          className: params.className || undefined,
          studentStatus: params.studentStatus || undefined,
          riskLevel: params.riskLevel || undefined,
          includeVoided: params.includeVoided ? 1 : undefined
        }
      })
      let rows = (data?.items || []).map(studentRow)
      if (params.identityVerifyStatus) rows = rows.filter((row) => row.identityVerifyStatus === params.identityVerifyStatus)
      return ok({ list: rows, total: Number(data?.total || 0), page: data?.page || params.page || 1, pageSize: data?.pageSize || params.pageSize || 10 })
    }, '学生主档列表加载失败')
  },

  async getStudentDetail(studentId) {
    return safe(async () => ok(detailRow(await request(`/students/${studentId}`))), '学生主档详情加载失败')
  },

  async createStudent(payload = {}) {
    return safe(async () => {
      const data = await request('/students', {
        method: 'POST',
        body: {
          studentNo: payload.studentNo,
          realName: payload.name,
          gender: payload.gender || null,
          collegeId: payload.collegeId || null,
          majorId: payload.majorId || null,
          classId: payload.classId || null,
          grade: payload.grade || null,
          phone: payload.phone || null,
          idCard: payload.idCard || null
        }
      })
      return ok(studentRow(data))
    }, '学生建档失败')
  },

  async updateStudent(studentId, payload = {}) {
    if (payload.classId || payload.collegeId || payload.majorId) {
      return fail('学院/专业/班级属于学籍事实，必须走 教务中心 › 学籍异动，不允许在主档编辑页直接改写。', 'ACADEMIC_STATUS_CHANGE_REQUIRED')
    }
    if (Object.prototype.hasOwnProperty.call(payload, 'idCard')) {
      return fail('身份证更正必须走学生信息更正审核链，不能在普通主档编辑中直接覆盖。', 'PROFILE_CORRECTION_REQUIRED')
    }
    if (payload.expectedVersion === undefined || payload.expectedVersion === null) {
      return fail('缺少主档版本号，请刷新后重试。', 'VERSION_REQUIRED')
    }
    return safe(async () => {
      const data = await request(`/students/${studentId}`, {
        method: 'PUT',
        body: {
          expectedVersion: payload.expectedVersion,
          realName: payload.name,
          gender: payload.gender,
          grade: payload.grade,
          phone: payload.phone
        }
      })
      return ok(studentRow(data))
    }, '学生主档更新失败')
  },

  async voidStudent(studentId, { reason } = {}) {
    const note = String(reason || '').trim()
    if (note.length < 5) return fail('作废原因必填且不少于 5 个字', 'VALIDATION_ERROR')
    return safe(async () => ok(await request(`/students/${studentId}/void`, { method: 'POST', body: { reason: note } })), '学生主档作废失败')
  },

  async restoreStudent({ studentNo, reason } = {}) {
    const note = String(reason || '').trim()
    if (note.length < 5) return fail('恢复原因必填且不少于 5 个字', 'VALIDATION_ERROR')
    return safe(async () => ok(studentRow(await request('/students/restore', { method: 'POST', body: { studentNo, reason: note } }))), '学生主档恢复失败')
  },

  batchAssignClass() {
    return fail('批量分班已从学生主档下线：班级变更必须逐人走 教务中心 › 学籍异动，保留历史事实与审批轨迹。', 'ACADEMIC_STATUS_CHANGE_REQUIRED')
  },
  batchAssignCounselor() {
    return fail('辅导员责任关系按班级维护，请到 学工中心 › 辅导员责任关系 办理。', 'COUNSELOR_ASSIGNMENT_REQUIRED')
  },
  batchRemind() {
    return fail('学生批量提醒尚未接入真实通知投递链路，已禁止产生假成功。', 'NOT_IMPLEMENTED')
  },

  async getStatusRecords(params = {}) {
    return safe(async () => {
      const res = await academicAffairsApi.getStatusChanges({ dateFrom: params.dateFrom || '', page: params.page || 1, pageSize: params.pageSize || 20 })
      if (res.code !== 0) return res
      let list = (res.data?.list || []).map(fromBackendStatusChange)
      if (params.keyword) list = list.filter((row) => row.studentName.includes(params.keyword))
      if (params.toStatus) list = list.filter((row) => row.toStatus === params.toStatus)
      return ok({ list, total: Number(res.data?.total || list.length), page: res.data?.page || 1, pageSize: res.data?.pageSize || params.pageSize || 20 })
    }, '学籍异动台账加载失败')
  },
  changeStatus() {
    return fail('学籍状态只能由 教务中心 › 学籍异动 的多级审批终审生效，本页不提供直接写入。', 'ACADEMIC_STATUS_CHANGE_REQUIRED')
  },
  batchChangeStatus() {
    return fail('批量直改学籍状态已禁用；每名学生必须保留独立异动申请、审批与历史事实。', 'ACADEMIC_STATUS_CHANGE_REQUIRED')
  },

  getIdentityRecords(params = {}) {
    return ok({
      list: [], total: 0, page: params.page || 1, pageSize: params.pageSize || 20,
      capabilityStatus: 'NOT_CONFIGURED',
      notice: '身份核验依赖第三方实名/人脸核验服务，当前环境未配置；新生人工信息核验请到“数字迎新 › 信息核验”。'
    })
  },
  reviewIdentityRecord() {
    return fail('第三方身份核验服务未配置，无真实核验记录可复核。', 'CAPABILITY_NOT_CONFIGURED')
  },
  markIdentityAbnormal() {
    return fail('第三方身份核验服务未配置；如需记录学生身份存疑，请在学生风险标签登记人工风险。', 'CAPABILITY_NOT_CONFIGURED')
  },

  async getCorrections(params = {}) {
    return safe(async () => {
      const res = await academicAffairsApi.getRosterCorrections({
        status: params.status ? (CORRECTION_STATUS_TO_API[params.status] || params.status) : '',
        page: params.page || 1,
        pageSize: params.pageSize || 20
      })
      if (res.code !== 0) return res
      let list = (res.data?.list || []).map(fromBackendCorrection)
      if (params.keyword) list = list.filter((row) => row.studentName.includes(params.keyword) || String(row.fieldLabel || '').includes(params.keyword))
      if (params.channel) list = list.filter((row) => row.channel === params.channel)
      return ok({ list, total: Number(res.data?.total || list.length), page: res.data?.page || 1, pageSize: res.data?.pageSize || params.pageSize || 20 })
    }, '学生信息更正列表加载失败')
  },
  async getCorrectionDetail(id) {
    const res = await this.getCorrections({ page: 1, pageSize: 200 })
    if (res.code !== 0) return res
    const hit = (res.data?.list || []).find((row) => String(row.id) === String(id))
    return hit ? ok(hit) : fail('更正申请不存在', 'NOT_FOUND')
  },
  async reviewCorrection(id, { action: reviewAction, reason } = {}) {
    const note = String(reason || '').trim()
    if (reviewAction === 'RETURN' && note.length < 5) return fail('退回原因必填且不少于 5 个字', 'VALIDATION_ERROR')
    if (!['APPROVE', 'RETURN'].includes(reviewAction)) return fail('非法的审核动作', 'VALIDATION_ERROR')
    return safe(async () => {
      const res = await academicAffairsApi.reviewRosterCorrection(id, reviewAction === 'APPROVE' ? 'APPROVE' : 'REJECT', note)
      return res.code === 0 ? ok(fromBackendCorrection(res.data || {})) : res
    }, '学生信息更正审核失败')
  },

  async getRiskTags(params = {}) {
    return safe(async () => {
      const res = await studentAffairsApi.getRisks({
        source: params.tagType || '', status: params.status || '', riskLevel: params.level || '',
        page: params.page || 1, pageSize: params.pageSize || 20
      })
      if (res.code !== 0) return res
      const raw = res.data || {}
      let list = (raw.items || raw.list || []).map(fromBackendRisk)
      if (params.keyword) list = list.filter((row) => row.studentName.includes(params.keyword) || row.title.includes(params.keyword))
      return ok({ list, total: Number(raw.total ?? list.length), page: raw.page || 1, pageSize: raw.pageSize || params.pageSize || 20 })
    }, '学生风险列表加载失败')
  },
  async createRiskTag(payload = {}) {
    const title = String(payload.title || '').trim()
    if (title.length < 4) return fail('标签标题必填且不少于 4 个字', 'VALIDATION_ERROR')
    if (!payload.tagType) return fail('请选择风险类型', 'VALIDATION_ERROR')
    return safe(async () => {
      const res = await studentAffairsApi.createRisk({
        studentId: String(payload.studentId), source: payload.tagType,
        riskLevel: payload.level || 'MEDIUM', title, detail: String(payload.description || '').trim()
      })
      return res.code === 0 ? ok(fromBackendRisk(res.data || {})) : res
    }, '新增学生风险失败')
  },
  updateRiskTag() {
    return fail('风险记录成立后不可覆盖原始内容，请通过“跟进”补充说明，或关闭后重新登记。', 'IMMUTABLE_RISK_FACT')
  },
  async voidRiskTag(id, { reason } = {}) {
    const conclusion = String(reason || '').trim()
    if (conclusion.length < 5) return fail('关闭结论必填且不少于 5 个字', 'VALIDATION_ERROR')
    return safe(async () => {
      const cur = await studentAffairsApi.getRiskDetail(id)
      if (cur.code !== 0) return cur
      const res = await studentAffairsApi.closeRisk(id, conclusion, cur.data?.version)
      return res.code === 0 ? ok(fromBackendRisk(res.data || {})) : res
    }, '关闭学生风险失败')
  },
  async addRiskFollowUp(id, { note } = {}) {
    const content = String(note || '').trim()
    if (content.length < 5) return fail('跟进内容必填且不少于 5 个字', 'VALIDATION_ERROR')
    return safe(async () => {
      const cur = await studentAffairsApi.getRiskDetail(id)
      if (cur.code !== 0) return cur
      const res = await studentAffairsApi.followRisk(id, content, cur.data?.version)
      return res.code === 0 ? ok(fromBackendRisk(res.data || {})) : res
    }, '学生风险跟进失败')
  },
  batchRemindRisk() {
    return fail('风险批量提醒尚无真实消息投递端点，请在风险详情逐条分派或转办。', 'NOT_IMPLEMENTED')
  },

  getImportTemplates() {
    return fail('学生主档不再维护独立导入模板；请使用 系统管理 › 学生导入与账号开通，或 教务中心 › 学籍导入。', 'MOVED_TO_AUTHORITATIVE_IMPORT')
  },
  validateImport() {
    return fail('旧学生主档导入预检已下线，请使用正式身份/学籍导入任务中心。', 'MOVED_TO_AUTHORITATIVE_IMPORT')
  },
  confirmImport() {
    return fail('旧学生主档导入确认已下线，禁止浏览器内存制造导入成功。', 'MOVED_TO_AUTHORITATIVE_IMPORT')
  },

  getExportOptions() {
    return ok(EXPORT_OPTIONS)
  },
  async createExport({ scope, fieldKeys = [], purpose, remark } = {}) {
    const scopeDef = EXPORT_OPTIONS.scopes.find((x) => x.value === scope)
    const purposeDef = EXPORT_OPTIONS.purposes.find((x) => x.value === purpose)
    if (!scopeDef) return fail('请选择导出范围', 'VALIDATION_ERROR')
    if (!fieldKeys.length) return fail('请至少选择一个导出字段', 'VALIDATION_ERROR')
    if (!purposeDef) return fail('导出用途必选（用于审计留痕）', 'VALIDATION_ERROR')
    if (scope === 'SELECTED') {
      return fail('“仅导出所选”尚未有服务端冻结 ID 集合的正式接口，已禁止把当前范围导出伪装成所选导出。', 'SELECTED_EXPORT_NOT_SUPPORTED')
    }
    return safe(async () => {
      const purposeText = `${purposeDef.label}${remark ? `：${remark}` : ''}`
      const task = await request('/export/students', { method: 'POST', body: { purpose: purposeText } })
      return ok({
        id: String(task.taskId || ''), type: 'EXPORT', typeLabel: '导出', title: scopeDef.label,
        fileName: task.fileName || '', totalRows: Number(task.rowCount || 0), successRows: Number(task.rowCount || 0),
        failedRows: 0, status: task.status || 'SUCCESS', operator: '', roleName: '',
        time: new Date().toISOString().slice(0, 16).replace('T', ' '), masked: true, watermark: true,
        auditId: task.auditId || '', downloadUrl: task.downloadUrl || ''
      })
    }, '学生数据导出失败')
  },
  getTransferTasks() {
    // 旧 transferTasks 是浏览器内存。正式接口暂无“学生导出任务列表”，因此明确返回真实空态而非伪造历史。
    return ok([])
  },
  async getAuditLogs(params = {}) {
    return safe(async () => {
      const data = await request('/audit/logs', { params: { page: params.page || 1, pageSize: params.pageSize || 10 } })
      let list = (data?.items || []).map((row) => ({
        id: String(row.auditId || row.id || ''),
        time: String(row.occurredAt || row.createdAt || '').replace('T', ' ').slice(0, 19),
        operator: row.actorName || row.operatorName || '—',
        roleName: row.currentRole || '',
        action: row.action || '',
        targetName: row.resource || '',
        detail: row.detail ? JSON.stringify(row.detail) : '',
        result: row.result || ''
      }))
      if (params.keyword) list = list.filter((row) => row.targetName.includes(params.keyword) || row.action.includes(params.keyword))
      return ok({ list, total: Number(data?.total || list.length), page: data?.page || params.page || 1, pageSize: data?.pageSize || params.pageSize || 10 })
    }, '学生中心审计记录加载失败')
  },

  getFieldColumns(viewKey) {
    const defaults = FIELD_COLUMNS[viewKey]
    if (!defaults) return fail('未配置该视图的列定义', 'NOT_FOUND')
    try {
      const raw = window.localStorage.getItem(`student-columns:${viewKey}`)
      return ok(raw ? JSON.parse(raw) : defaults)
    } catch {
      return ok(defaults)
    }
  },
  saveFieldColumns(viewKey, columns = []) {
    const defaults = FIELD_COLUMNS[viewKey]
    if (!defaults) return fail('未配置该视图的列定义', 'NOT_FOUND')
    const locked = defaults.filter((x) => x.locked).map((x) => x.key)
    const incoming = columns.map((x) => x.key)
    if (locked.some((key) => !incoming.includes(key))) return fail('固定列不可移除', 'VALIDATION_ERROR')
    try { window.localStorage.setItem(`student-columns:${viewKey}`, JSON.stringify(columns)) } catch { /* 本地偏好失败不影响业务事实 */ }
    return ok(columns)
  }
}

export default studentApi
