/**
 * 学工 B 兼容导出层：旧方法名保留，内部全部委托 studentAffairs.api.js（唯一真实请求实现）。
 * B 页面习惯 try/catch + throw；因此对主客户端 {code,data,message} 做 unwrap。
 */
import { studentAffairsApi as core } from './studentAffairs.api.js'

function unwrap(res) {
  if (res && res.code !== 0) {
    const e = new Error(res.message || '操作失败')
    e.biz = true
    e.bizCode = res.bizCode || ''
    e.code = res.code
    throw e
  }
  return res
}

async function pass(promise) {
  return unwrap(await promise)
}

/** 规范化学生主档展示字段；禁止用 classId 冒充 className。 */
export function normalizeStudent(row = {}) {
  const classId = row.classId != null ? String(row.classId) : (row.class_id != null ? String(row.class_id) : '')
  const className = row.className || row.class_name || (classId ? '' : '未分班')
  return {
    studentId: String(row.id || row.studentId || ''),
    studentNo: row.studentNo || row.student_no || '',
    realName: row.realName || row.real_name || row.name || '',
    className,
    classId,
    collegeName: row.collegeName || row.college_name || '',
    majorName: row.majorName || row.major_name || '',
    grade: row.grade || '',
    currentStage: row.currentStage || row.current_stage || '',
    studentStatus: row.studentStatus || row.student_status || 'NORMAL',
    riskLevel: row.riskLevel || row.risk_level || 'LOW',
    phoneMasked: row.phoneMasked || row.phone_masked || row.phone || '',
    idCardMasked: row.idCardMasked || row.id_card_masked || row.idCard || '',
    updatedAt: row.updatedAt || row.updated_at || row.createdAt || row.created_at || ''
  }
}

function normalizeAudit(row = {}) {
  return {
    id: row.id || row.auditId || row.eventId || '',
    action: row.action || row.title || '未记录',
    actor: row.actor || row.operator || row.who || '未记录',
    actorRole: row.actorRole || row.roleName || row.currentRole || '',
    target: row.target || row.resource || row.module || '',
    reason: row.reason || row.detail || row.summary || '',
    at: (row.at || row.time || row.occurredAt || row.createdAt || '').replace('T', ' ').slice(0, 19),
    result: row.result || '未记录'
  }
}

export const studentAffairsApi = {
  getDashboard() {
    return pass(core.getDashboard())
  },

  async listStudents(params = {}) {
    const res = await pass(core.getStudents(params))
    const data = res.data || {}
    return {
      ...res,
      data: {
        items: (data.items || []).map(normalizeStudent),
        total: data.total || 0,
        page: data.page || params.page || 1,
        pageSize: data.pageSize || params.pageSize || 10
      }
    }
  },

  getProfile(studentId) {
    return pass(core.getStudentProfile(studentId))
  },

  getTimeline(studentId, params = {}) {
    return pass(core.getStudentTimeline(studentId, params))
  },

  listClasses() {
    return pass(core.getClasses())
  },

  listClassCadres(classId) {
    return pass(core.getClassCadres(classId))
  },

  getDormOccupancy() {
    return pass(core.getOccupancy())
  },

  listDormBuildings(params = {}) {
    return pass(core.getBuildings(params))
  },

  listDormRooms(buildingId, params = {}) {
    return pass(core.getRooms(buildingId, params))
  },

  listDormBeds(roomId) {
    return pass(core.getBeds(roomId))
  },

  getDormConfig() {
    return pass(core.getDormConfig())
  },

  createDormBuilding(body) {
    return pass(core.createBuilding(body))
  },

  generateDormLayout(buildingId, body) {
    return pass(core.generateLayout(buildingId, body))
  },

  dormCheckin(bedId, studentId) {
    return pass(core.checkinBed(bedId, studentId))
  },

  dormCheckout(bedId) {
    return pass(core.checkoutBed(bedId))
  },

  setDormSelfSelect(enabled) {
    return pass(core.setDormSelfSelect(enabled))
  },

  listDormTransfers(params = {}) {
    return pass(core.getDormTransfers(params))
  },

  submitDormTransfer(body) {
    return pass(core.submitDormTransfer(body))
  },

  reviewDormTransfer(transferId, action, reason = '', version) {
    return pass(core.reviewDormTransfer(transferId, action, reason, version))
  },

  listDormCheckTasks(params = {}) {
    return pass(core.getDormCheckTasks(params))
  },

  createDormCheckTask(body) {
    return pass(core.createDormCheckTask(body))
  },

  listDormCheckRecords(taskId, params = {}) {
    return pass(core.getDormCheckRecords(taskId, params))
  },

  submitDormCheckRecord(taskId, body) {
    return pass(core.submitDormCheckRecord(taskId, body))
  },

  listDormExceptions(params = {}) {
    return pass(core.getDormExceptions(params))
  },

  handleDormException(exceptionId, reason, version) {
    return pass(core.handleDormException(exceptionId, reason, version))
  },

  listPendingLeaves(params = {}) {
    return pass(core.getPendingLeaves(params))
  },

  getLeaveDetail(leaveId) {
    return pass(core.getLeaveDetail(leaveId))
  },

  approveLeave(leaveId, comment = '', version) {
    return pass(core.approveLeave(leaveId, comment, version))
  },

  rejectLeave(leaveId, reason, version) {
    return pass(core.rejectLeave(leaveId, reason, version))
  },

  returnLeave(leaveId, reason, version) {
    return pass(core.returnLeave(leaveId, reason, version))
  },

  cancelLeave(leaveId, proofNote = '', version) {
    return pass(core.cancelLeave(leaveId, proofNote, version))
  },

  confirmCancelLeave(leaveId, note = '', version) {
    return pass(core.confirmCancelLeave(leaveId, note, version))
  },

  applyLeaveExtension(leaveId, body = {}) {
    return pass(core.extendLeave(leaveId, body.newEnd, body.reason || '', body.version))
  },

  approveLeaveExtension(leaveId, version) {
    return pass(core.approveExtension(leaveId, version))
  },

  scanLeaveOverdue() {
    return pass(core.scanOverdueLeaves())
  },

  listRiskRecords(params = {}) {
    return pass(core.getRisks(params))
  },

  getRiskRecord(riskId, reason = '') {
    return pass(core.getRiskDetail(riskId, reason))
  },
  listRiskHandles(riskId) {
    return pass(core.listRiskHandles(riskId))
  },

  createRiskRecord(body) {
    return pass(core.createRisk(body))
  },

  assignRisk(riskId, ownerId, version) {
    return pass(core.assignRisk(riskId, ownerId, version))
  },

  processRisk(riskId, content, version) {
    return pass(core.processRisk(riskId, content, version))
  },

  followRisk(riskId, content = '', version) {
    return pass(core.followRisk(riskId, content, version))
  },

  transferRisk(riskId, newOwnerId, reason = '', version) {
    return pass(core.transferRisk(riskId, newOwnerId, reason, version))
  },

  escalateRisk(riskId, reason = '', version) {
    return pass(core.escalateRisk(riskId, reason, version))
  },

  takeoverRisk(riskId, content = '', version) {
    return pass(core.takeoverRisk(riskId, content, version))
  },

  closeRisk(riskId, conclusion, version) {
    return pass(core.closeRisk(riskId, conclusion, version))
  },

  reopenRisk(riskId, reason = '', version) {
    return pass(core.reopenRisk(riskId, reason, version))
  },

  scanRiskTimeout() {
    return pass(core.scanRiskTimeout())
  },

  // ── 心理关注 ──
  listMentalAttention(params = {}) {
    return pass(core.listMentalAttention(params))
  },

  getMentalReferral(refId, reason) {
    return pass(core.getMentalReferral(refId, reason))
  },

  getMentalSummary(studentId) {
    return pass(core.getMentalSummary(studentId))
  },

  createMentalReferral(body) {
    return pass(core.createMentalReferral(body))
  },

  followMentalReferral(refId, content, version) {
    return pass(core.followMentalReferral(refId, content, version))
  },

  escalateMentalReferral(refId, content = '', version) {
    return pass(core.escalateMentalReferral(refId, content, version))
  },

  closeMentalReferral(refId, conclusion, version) {
    return pass(core.closeMentalReferral(refId, conclusion, version))
  },

  getMentalStats() {
    return pass(core.getMentalStats())
  },

  async getStudentBasic(studentId) {
    const res = await pass(core.getStudentBasic(studentId))
    return { ...res, data: normalizeStudent(res.data || {}) }
  },

  async getAuditLogs(params = {}) {
    const res = await pass(core.getAuditLogs(params))
    const items = Array.isArray(res.data) ? res.data : (res.data?.items || [])
    return { ...res, data: items.map(normalizeAudit) }
  },

  exportProfileLedger(opts = {}) {
    return pass(core.exportProfileLedger(opts))
  }
}

export default studentAffairsApi
