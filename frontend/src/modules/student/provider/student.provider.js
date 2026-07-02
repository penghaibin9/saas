/**
 * Student Provider — 页面唯一数据入口（默认 mock 实现）。
 * 接真实 API 时仅将 impl 切为 student.api.real.example，页面零改动。
 */
import * as mockApi from '../api/student.api.mock'

const impl = mockApi

export const getStudentOverview = () => impl.getStudentOverview()
export const getStudentList = (params) => impl.getStudentList(params)
export const getStudentDetail = (id) => impl.getStudentDetail(id)
export const getStudentProfile = (id) => impl.getStudentProfile(id)
export const getStudentIdentity = (id) => impl.getStudentIdentity(id)
export const verifyStudentIdentity = (id) => impl.verifyStudentIdentity(id)
export const rejectStudentIdentity = (id, payload) => impl.rejectStudentIdentity(id, payload)
export const getStudentGuardians = (id) => impl.getStudentGuardians(id)
export const saveStudentGuardians = (id, payload) => impl.saveStudentGuardians(id, payload)
export const changeStudentStatus = (id, payload) => impl.changeStudentStatus(id, payload)
export const getStudentTimeline = (id) => impl.getStudentTimeline(id)
export const getStudentOptions = () => impl.getStudentOptions()
export const validateStudentImport = (payload) => impl.validateStudentImport(payload)
export const exportStudents = (payload) => impl.exportStudents(payload)
export const getStudentAuditLogs = (id) => impl.getStudentAuditLogs(id)
