/**
 * 01 学生主档 — API Contract（15 接口冻结）
 * 统一响应：{ code, message, data, timestamp, requestId }（与 dashboard/workflow 一致）
 * 每接口冻结：method/path/description/params/data/errors/emptyState/permissionKey/auditAction/sensitiveFields
 */
import { STUDENT_PERMISSION as P } from '../constants/student.constants'

export const STUDENT_ERROR_CODES = Object.freeze({
  OK: 0,
  NOT_FOUND: 40401,
  INVALID_PARAM: 40001,
  REJECT_REASON_TOO_SHORT: 40002, // 身份核验退回原因不足 5 字
  CHANGE_REASON_REQUIRED: 40003, // 状态变更原因缺失
  NO_PERMISSION: 41001,
  MODULE_READONLY: 41003,
  ALREADY_FINAL: 42001, // 已终态（已认证/已归档）不可重复操作
  SERVER_ERROR: 50000
})

const SENSITIVE_STUDENT = ['idCard', 'phone', 'homeAddress', 'currentAddress', 'email']
const SENSITIVE_GUARDIAN = ['guardianPhone', 'guardianIdCard', 'guardianAddress']

export const STUDENT_API_CONTRACT = Object.freeze({
  /** 1 */ getStudentOverview: {
    method: 'GET',
    path: '/api/student/overview',
    description: '学生主档概览：总数/在校/待核验/资料缺失/学业预警/账号未绑定 + 最近动态',
    params: {},
    data: '{ totalCount, activeCount, pendingVerifyCount, dataMissingCount, academicWarningCount, accountUnboundCount, recentStatusChanges:[], recentVerifies:[] }',
    errors: ['SERVER_ERROR'],
    emptyState: '各计数为 0，列表为 []',
    permissionKey: P.PROFILE_VIEW,
    auditAction: '',
    sensitiveFields: []
  },
  /** 2 */ getStudentList: {
    method: 'GET',
    path: '/api/student/list',
    description: '学生列表（分页+多条件筛选）',
    params: {
      keyword: 'string? 姓名/学号/手机号后四位',
      schoolId: 'string?',
      collegeId: 'string?',
      majorId: 'string?',
      classId: 'string?',
      grade: 'string?',
      studentStatus: 'string?',
      academicStatus: 'string?',
      identityVerifyStatus: 'string?',
      accountStatus: 'string?',
      page: 'number=1',
      pageSize: 'number=10'
    },
    data: '{ list:[StudentBrief], total }',
    errors: ['INVALID_PARAM'],
    emptyState: '{ list: [], total: 0 }',
    permissionKey: P.PROFILE_VIEW,
    auditAction: '',
    sensitiveFields: SENSITIVE_STUDENT
  },
  /** 3 */ getStudentDetail: {
    method: 'GET',
    path: '/api/student/detail/:studentId',
    description: '学生详情（主档+学籍+账号+风险聚合）',
    params: { studentId: 'string' },
    data: 'StudentDetail',
    errors: ['NOT_FOUND'],
    emptyState: 'data=null + NOT_FOUND',
    permissionKey: P.PROFILE_VIEW,
    auditAction: 'SENSITIVE_VIEW（查看详情留痕）',
    sensitiveFields: [...SENSITIVE_STUDENT, ...SENSITIVE_GUARDIAN]
  },
  /** 4 */ getStudentProfile: {
    method: 'GET',
    path: '/api/student/profile/:studentId',
    description: '学生基础档案（基本信息子集）',
    params: { studentId: 'string' },
    data: 'StudentProfile',
    errors: ['NOT_FOUND'],
    emptyState: 'NOT_FOUND',
    permissionKey: P.PROFILE_VIEW,
    auditAction: '',
    sensitiveFields: SENSITIVE_STUDENT
  },
  /** 5 */ getStudentIdentity: {
    method: 'GET',
    path: '/api/student/identity/:studentId',
    description: '身份认证信息（证件、核验状态、核验记录）',
    params: { studentId: 'string' },
    data: '{ studentId, name, idCard, identityVerifyStatus, idCardExpireDate, verifyRecords:[] }',
    errors: ['NOT_FOUND'],
    emptyState: 'NOT_FOUND',
    permissionKey: P.IDENTITY_VIEW,
    auditAction: 'SENSITIVE_VIEW',
    sensitiveFields: ['idCard']
  },
  /** 6 */ verifyStudentIdentity: {
    method: 'POST',
    path: '/api/student/identity/:studentId/verify',
    description: '身份核验通过',
    params: { studentId: 'string' },
    data: 'StudentIdentity（更新后）',
    errors: ['NOT_FOUND', 'NO_PERMISSION', 'MODULE_READONLY', 'ALREADY_FINAL'],
    emptyState: '—',
    permissionKey: P.IDENTITY_VERIFY,
    auditAction: 'APPROVAL（身份核验通过）',
    sensitiveFields: []
  },
  /** 7 */ rejectStudentIdentity: {
    method: 'POST',
    path: '/api/student/identity/:studentId/reject',
    description: '身份核验退回（原因必填≥5字，复用 workflow validateRejectReason）',
    params: { studentId: 'string' },
    data: 'StudentIdentity（更新后）; body: { reason }',
    errors: ['NOT_FOUND', 'REJECT_REASON_TOO_SHORT', 'NO_PERMISSION', 'MODULE_READONLY'],
    emptyState: '—',
    permissionKey: P.IDENTITY_VERIFY,
    auditAction: 'APPROVAL（身份核验退回，含脱敏原因）',
    sensitiveFields: []
  },
  /** 8 */ getStudentGuardians: {
    method: 'GET',
    path: '/api/student/guardians/:studentId',
    description: '监护人/联系人列表',
    params: { studentId: 'string' },
    data: '{ list:[Guardian] }',
    errors: ['NOT_FOUND'],
    emptyState: '{ list: [] }',
    permissionKey: P.GUARDIAN_VIEW,
    auditAction: 'SENSITIVE_VIEW',
    sensitiveFields: SENSITIVE_GUARDIAN
  },
  /** 9 */ saveStudentGuardians: {
    method: 'POST',
    path: '/api/student/guardians/:studentId',
    description: '保存监护人/联系人（整表覆盖）',
    params: { studentId: 'string' },
    data: '{ list:[Guardian] }; body: { guardians:[Guardian] }',
    errors: ['NOT_FOUND', 'INVALID_PARAM', 'NO_PERMISSION', 'MODULE_READONLY'],
    emptyState: '—',
    permissionKey: P.GUARDIAN_UPDATE,
    auditAction: 'PERMISSION_CHANGE（监护人变更留痕，detail 脱敏）',
    sensitiveFields: SENSITIVE_GUARDIAN
  },
  /** 10 */ changeStudentStatus: {
    method: 'POST',
    path: '/api/student/status/:studentId/change',
    description: '变更学生状态（原因必填；身份证/学籍等关键字段变更走二次复核——设计文档冻结）',
    params: { studentId: 'string' },
    data: 'StudentDetail（更新后）; body: { targetStatus, reason }',
    errors: ['NOT_FOUND', 'CHANGE_REASON_REQUIRED', 'NO_PERMISSION', 'MODULE_READONLY'],
    emptyState: '—',
    permissionKey: P.STATUS_UPDATE,
    auditAction: 'APPROVAL（状态变更 before/after + 原因）',
    sensitiveFields: []
  },
  /** 11 */ getStudentTimeline: {
    method: 'GET',
    path: '/api/student/timeline/:studentId',
    description: '学生主档时间线（建档/核验/状态变更/导入导出）',
    params: { studentId: 'string' },
    data: '{ list:[{ time, type, title, operator, detail }] }',
    errors: ['NOT_FOUND'],
    emptyState: '{ list: [] }',
    permissionKey: P.PROFILE_VIEW,
    auditAction: '',
    sensitiveFields: []
  },
  /** 12 */ getStudentOptions: {
    method: 'GET',
    path: '/api/student/options',
    description: '筛选字典：院系/专业/班级/年级/学年/学期（页面下拉禁止硬编码）',
    params: {},
    data: '{ colleges:[], majors:[], classes:[], grades:[], academicYears:[], terms:[] }',
    errors: [],
    emptyState: '各数组为 []',
    permissionKey: P.PROFILE_VIEW,
    auditAction: '',
    sensitiveFields: []
  },
  /** 13 */ validateStudentImport: {
    method: 'POST',
    path: '/api/student/import/validate',
    description: '导入校验（预留：仅 mock 校验结果，不解析真实文件，01-P2 实做）',
    params: {},
    data: '{ totalRows, validRows, errorRows, errors:[{ row, field, message }] }',
    errors: ['NO_PERMISSION'],
    emptyState: '—',
    permissionKey: P.IMPORT,
    auditAction: 'UPLOAD（导入校验留痕）',
    sensitiveFields: []
  },
  /** 14 */ exportStudents: {
    method: 'POST',
    path: '/api/student/export',
    description: '导出学生主档（预留：经 security export guard + 审计，不产真实文件）',
    params: {},
    data: '{ taskId, rowCount, watermark: true }; body: { filters, exportType, purpose }',
    errors: ['NO_PERMISSION', 'MODULE_READONLY'],
    emptyState: '—',
    permissionKey: P.EXPORT,
    auditAction: 'EXPORT（必审计）',
    sensitiveFields: ['导出内容默认脱敏']
  },
  /** 15 */ getStudentAuditLogs: {
    method: 'GET',
    path: '/api/student/audit/:studentId',
    description: '学生主档审计记录',
    params: { studentId: 'string' },
    data: '{ list:[{ time, operator, action, before, after }] }',
    errors: ['NOT_FOUND'],
    emptyState: '{ list: [] }',
    permissionKey: P.AUDIT_VIEW,
    auditAction: '',
    sensitiveFields: []
  }
})
