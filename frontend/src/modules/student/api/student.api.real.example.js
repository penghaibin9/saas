/**
 * 01 学生主档 — 真实 API 示例（未启用；页面与 provider 默认走 mock）。
 * 接后端时：provider 将 impl 切换为本文件导出；统一经 security 的 secureRequest
 * （自动带 requestId / Authorization 预留 / CSRF / 401·403·419·500 分流 / 敏感错误清理）。
 * 路径与 student.contract.js 逐一对齐。
 */
import { secureRequest } from '@/security'

const p = (tpl, id) => tpl.replace(':studentId', encodeURIComponent(id))

export const getStudentOverview = () => secureRequest('/api/student/overview')
export const getStudentList = (params) => secureRequest('/api/student/list', { params })
export const getStudentDetail = (id) => secureRequest(p('/api/student/detail/:studentId', id))
export const getStudentProfile = (id) => secureRequest(p('/api/student/profile/:studentId', id))
export const getStudentIdentity = (id) => secureRequest(p('/api/student/identity/:studentId', id))
export const verifyStudentIdentity = (id) =>
  secureRequest(p('/api/student/identity/:studentId/verify', id), { method: 'POST' })
export const rejectStudentIdentity = (id, payload) =>
  secureRequest(p('/api/student/identity/:studentId/reject', id), { method: 'POST', body: payload })
export const getStudentGuardians = (id) => secureRequest(p('/api/student/guardians/:studentId', id))
export const saveStudentGuardians = (id, payload) =>
  secureRequest(p('/api/student/guardians/:studentId', id), { method: 'POST', body: payload })
export const changeStudentStatus = (id, payload) =>
  secureRequest(p('/api/student/status/:studentId/change', id), { method: 'POST', body: payload })
export const getStudentTimeline = (id) => secureRequest(p('/api/student/timeline/:studentId', id))
export const getStudentOptions = () => secureRequest('/api/student/options')
export const validateStudentImport = (payload) =>
  secureRequest('/api/student/import/validate', { method: 'POST', body: payload })
export const exportStudents = (payload) =>
  secureRequest('/api/student/export', { method: 'POST', body: payload })
export const getStudentAuditLogs = (id) => secureRequest(p('/api/student/audit/:studentId', id))
