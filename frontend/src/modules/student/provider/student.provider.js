/**
 * Student Provider — 兼容旧调用面的真实 facade 适配层。
 *
 * A2：正式 provider 不得默认指向 student.api.mock；暂未有真实合同的旧能力
 * 统一 fail-closed，避免未来页面误接回浏览器 fixture。
 */
import studentApi from '../api/student.api'

function unsupported(message) {
  return Promise.resolve({ code: 1, bizCode: 'UNSUPPORTED_ACTION', data: null, message })
}

export const getStudentOverview = () => studentApi.getDashboardSummary()
export const getStudentList = (params) => studentApi.getStudents(params)
export const getStudentDetail = (id) => studentApi.getStudentDetail(id)
export const getStudentProfile = (id) => studentApi.getStudentDetail(id)
export const getStudentIdentity = (id) => studentApi.getIdentityRecords({ studentId: id, page: 1, pageSize: 20 })
export const verifyStudentIdentity = (id) => studentApi.reviewIdentityRecord(id, { action: 'APPROVE' })
export const rejectStudentIdentity = (id, payload) => studentApi.reviewIdentityRecord(id, { action: 'RETURN', ...payload })
export const getStudentGuardians = () => unsupported('监护人旧 provider 尚未接入真实学生关系服务')
export const saveStudentGuardians = () => unsupported('监护人旧 provider 尚未接入真实学生关系服务')
export const changeStudentStatus = (id, payload) => studentApi.changeStatus(id, payload)
export const getStudentTimeline = () => unsupported('成长时间线请使用学生360正式详情接口')
export const getStudentOptions = () => studentApi.getContext()
export const validateStudentImport = (payload) => studentApi.validateImport(payload)
export const exportStudents = (payload) => studentApi.createExport(payload)
export const getStudentAuditLogs = () => studentApi.getAuditLogs({ page: 1, pageSize: 20 })
