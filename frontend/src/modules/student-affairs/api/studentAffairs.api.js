import { request } from '@/services/http/client'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

const ok = (data) => ({ code: 0, message: 'ok', data })

function normalizeStudent(row = {}) {
  return {
    studentId: String(row.id || row.studentId || ''),
    studentNo: row.studentNo || row.student_no || '',
    realName: row.realName || row.real_name || row.name || '',
    className: row.className || row.class_name || row.classId || row.class_id || '未分班',
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
    id: row.id || row.auditId || row.eventId || `${row.action || 'audit'}-${row.at || row.time || Math.random()}`,
    action: row.action || row.title || '查看记录',
    actor: row.actor || row.operator || row.who || '系统',
    actorRole: row.actorRole || row.roleName || row.currentRole || '',
    target: row.target || row.resource || row.module || '',
    reason: row.reason || row.detail || row.summary || '',
    at: (row.at || row.time || row.occurredAt || row.createdAt || '').replace('T', ' ').slice(0, 19),
    result: row.result || '成功'
  }
}

export const studentAffairsApi = {
  async getDashboard() {
    return ok(await request('/student-affairs/dashboard'))
  },

  async listStudents(params = {}) {
    const data = await request('/students', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 10,
        keyword: params.keyword,
        className: params.className,
        riskLevel: params.riskLevel
      }
    })
    return ok({
      items: (data.items || []).map(normalizeStudent),
      total: data.total || 0,
      page: data.page || params.page || 1,
      pageSize: data.pageSize || params.pageSize || 10
    })
  },

  async getProfile(studentId) {
    return ok(await request(`/student-affairs/students/${studentId}/profile`))
  },

  async getTimeline(studentId, params = {}) {
    return ok(await request(`/student-affairs/students/${studentId}/timeline`, { params }))
  },

  async listClasses() {
    return ok(await request('/student-affairs/classes'))
  },

  async listClassCadres(classId) {
    return ok(await request(`/student-affairs/classes/${classId}/cadres`))
  },

  async getDormOccupancy() {
    return ok(await request('/student-affairs/dorm/occupancy'))
  },

  async listDormBuildings(params = {}) {
    return ok(await request('/student-affairs/dorm/buildings', { params }))
  },

  async listDormRooms(buildingId, params = {}) {
    return ok(await request(`/student-affairs/dorm/buildings/${buildingId}/rooms`, { params }))
  },

  async listDormBeds(roomId) {
    return ok(await request(`/student-affairs/dorm/rooms/${roomId}/beds`))
  },

  async getDormConfig() {
    return ok(await request('/student-affairs/dorm/config'))
  },

  async listPendingLeaves(params = {}) {
    const data = await request('/student-affairs/leave/pending', {
      params: {
        page: params.page || 1,
        pageSize: params.pageSize || 20
      }
    })
    return ok({
      items: data.items || [],
      total: data.total || 0,
      page: data.page || params.page || 1,
      pageSize: data.pageSize || params.pageSize || 20
    })
  },

  async getLeaveDetail(leaveId) {
    return ok(await request(`/student-affairs/leave/${leaveId}`))
  },

  async approveLeave(leaveId, comment = '') {
    return ok(await request(`/student-affairs/leave/${leaveId}/approve`, {
      method: 'POST',
      body: { comment }
    }))
  },

  async rejectLeave(leaveId, reason) {
    return ok(await request(`/student-affairs/leave/${leaveId}/reject`, {
      method: 'POST',
      body: { reason }
    }))
  },

  async returnLeave(leaveId, reason) {
    return ok(await request(`/student-affairs/leave/${leaveId}/return`, {
      method: 'POST',
      body: { reason }
    }))
  },

  async cancelLeave(leaveId, proofNote = '') {
    return ok(await request(`/student-affairs/leave/${leaveId}/cancel`, {
      method: 'POST',
      body: { proofNote }
    }))
  },

  async confirmCancelLeave(leaveId, note = '') {
    return ok(await request(`/student-affairs/leave/${leaveId}/cancel-confirm`, {
      method: 'POST',
      body: { note }
    }))
  },

  async applyLeaveExtension(leaveId, body) {
    return ok(await request(`/student-affairs/leave/${leaveId}/extension`, {
      method: 'POST',
      body
    }))
  },

  async approveLeaveExtension(leaveId) {
    return ok(await request(`/student-affairs/leave/${leaveId}/extension-approve`, {
      method: 'POST'
    }))
  },

  async scanLeaveOverdue() {
    return ok(await request('/student-affairs/leave/scan-overdue', { method: 'POST' }))
  },

  async listRiskRecords(params = {}) {
    const data = await request('/student-affairs/risk/records', {
      params: {
        source: params.source,
        status: params.status,
        riskLevel: params.riskLevel,
        page: params.page || 1,
        pageSize: params.pageSize || 20
      }
    })
    return ok({
      items: data.items || [],
      total: data.total || 0,
      page: data.page || params.page || 1,
      pageSize: data.pageSize || params.pageSize || 20
    })
  },

  async getRiskRecord(riskId) {
    return ok(await request(`/student-affairs/risk/records/${riskId}`))
  },

  async createRiskRecord(body) {
    return ok(await request('/student-affairs/risk/records', {
      method: 'POST',
      body
    }))
  },

  async assignRisk(riskId, ownerId) {
    return ok(await request(`/student-affairs/risk/records/${riskId}/assign`, {
      method: 'POST',
      body: { ownerId }
    }))
  },

  async processRisk(riskId, content) {
    return ok(await request(`/student-affairs/risk/records/${riskId}/process`, {
      method: 'POST',
      body: { content }
    }))
  },

  async followRisk(riskId, content = '') {
    return ok(await request(`/student-affairs/risk/records/${riskId}/follow`, {
      method: 'POST',
      body: { content }
    }))
  },

  async transferRisk(riskId, newOwnerId, reason = '') {
    return ok(await request(`/student-affairs/risk/records/${riskId}/transfer`, {
      method: 'POST',
      body: { newOwnerId, reason }
    }))
  },

  async escalateRisk(riskId, reason = '') {
    return ok(await request(`/student-affairs/risk/records/${riskId}/escalate`, {
      method: 'POST',
      body: { reason }
    }))
  },

  async takeoverRisk(riskId, content = '') {
    return ok(await request(`/student-affairs/risk/records/${riskId}/takeover`, {
      method: 'POST',
      body: { content }
    }))
  },

  async closeRisk(riskId, conclusion) {
    return ok(await request(`/student-affairs/risk/records/${riskId}/close`, {
      method: 'POST',
      body: { conclusion }
    }))
  },

  async reopenRisk(riskId, reason = '') {
    return ok(await request(`/student-affairs/risk/records/${riskId}/reopen`, {
      method: 'POST',
      body: { reason }
    }))
  },

  async scanRiskTimeout() {
    return ok(await request('/student-affairs/risk/scan-timeout', { method: 'POST' }))
  },

  // ── 心理关注（强敏感·PSY_STUDENT·危机接风险中枢）──
  async listMentalAttention(params = {}) {
    const data = await request('/student-affairs/mental/list', {
      params: { level: params.level, page: params.page || 1, pageSize: params.pageSize || 50 }
    })
    return ok({
      items: data.items || [],
      total: data.total || 0,
      page: data.page || params.page || 1,
      pageSize: data.pageSize || params.pageSize || 50
    })
  },

  async getMentalReferral(refId, reason) {
    return ok(await request(`/student-affairs/mental/referrals/${refId}`, {
      params: reason ? { reason } : {}
    }))
  },

  async getMentalSummary(studentId) {
    return ok(await request(`/student-affairs/mental/students/${studentId}/summary`))
  },

  async createMentalReferral(body) {
    return ok(await request('/student-affairs/mental/referrals', { method: 'POST', body }))
  },

  async followMentalReferral(refId, content) {
    return ok(await request(`/student-affairs/mental/referrals/${refId}/follow`, {
      method: 'POST', body: { content }
    }))
  },

  async escalateMentalReferral(refId, content = '') {
    return ok(await request(`/student-affairs/mental/referrals/${refId}/escalate`, {
      method: 'POST', body: { content }
    }))
  },

  async closeMentalReferral(refId, conclusion) {
    return ok(await request(`/student-affairs/mental/referrals/${refId}/close`, {
      method: 'POST', body: { conclusion }
    }))
  },

  async getMentalStats() {
    return ok(await request('/student-affairs/mental/stats'))
  },

  async getStudentBasic(studentId) {
    return ok(normalizeStudent(await request(`/students/${studentId}`)))
  },

  async getAuditLogs(params = {}) {
    const data = await request('/audit/logs', {
      params: { page: params.page || 1, pageSize: params.pageSize || 8 }
    })
    return ok((data.items || []).map(normalizeAudit))
  },

  async exportProfileLedger({ purpose = '学工学生画像台账导出' } = {}) {
    const task = await request('/export/students', {
      method: 'POST',
      body: { purpose }
    })
    return {
      code: 0,
      message: 'ok',
      data: {
        filename: task.fileName || `student-affairs-profile-${Date.now()}.xlsx`,
        downloadUrl: `${API_BASE_URL}${API_PREFIX}/export/tasks/${task.taskId}/download`
      }
    }
  }
}

export default studentAffairsApi
