/** Standalone 岗位实习教师移动端 facade。禁止回落其他业务域或 mock。 */
import { realRequest } from './request'
import * as sequential from './teacherSequentialV3Api'
import { teacherInternshipEvidenceV3Api } from './teacherInternshipEvidenceV3Api'

export const teacherApi = {
  getReportObligations: ({ batchId, reportType, missingOnly = true, submittedOnly = false, page = 1, pageSize = 20 }) =>
    realRequest(`/internship/report-obligations?batchId=${encodeURIComponent(batchId)}&reportType=${encodeURIComponent(reportType)}&missingOnly=${missingOnly}&submittedOnly=${submittedOnly}&page=${page}&pageSize=${pageSize}`),
  remindReportObligation: (recordId, batchId, reportType) =>
    realRequest(`/internship/report-obligations/${encodeURIComponent(recordId)}/remind?batchId=${encodeURIComponent(batchId)}`, { method: 'POST', data: { reportType } }),
  getEmploymentRegistrations: ({batchId,status='ALL',page=1,pageSize=20}) => realRequest(`/teacher-mobile/internship/employment?batchId=${encodeURIComponent(String(batchId||''))}&status=${encodeURIComponent(status)}&page=${page}&pageSize=${pageSize}`),
  getEmploymentRegistration: id => realRequest(`/teacher-mobile/internship/employment/${encodeURIComponent(String(id||''))}`),
  discloseEmploymentRegistration: (id,purpose) => realRequest(`/teacher-mobile/internship/employment/${encodeURIComponent(String(id||''))}/disclose`,{method:'POST',data:{purpose}}),
  reviewEmploymentRegistration: (id,body) => realRequest(`/teacher-mobile/internship/employment/${encodeURIComponent(String(id||''))}/review`,{method:'POST',data:body}),
  getWeeklyReports: (options = {}) => sequential.getInternshipReviewQueue(options),
  handleCheckin: (id, action, comment, riskLevel = null) => sequential.handleCheckin(id, action, comment, riskLevel),
  async getWeeklyDetail(id) {
    const d = await realRequest('/internship/reports/' + encodeURIComponent(String(id || '')))
    const c = d?.content || {}
    return {
      id: String(d?.id || ''), batchId: String(d?.batchId || ''), version: d?.version, status: d?.status,
      work: c.work || '',
      harvest: c.harvest || '',
      plan: c.plan || '',
      positionName: d?.positionName || '',
      reviewComment: d?.reviewComment || '',
      attachments: d?.attachments || [],
      immutableVersions: d?.immutableVersions || []
    }
  },
  reviewWeekly: (id, action, comment, expectedVersion, ratingLevel = null) =>
    realRequest(`/internship/reports/${encodeURIComponent(String(id || ''))}/review`, {
      method: 'POST',
      data: { action, comment: comment || '', expectedVersion, ratingLevel }
    }),
  getInternshipVisitPlans: (batchId, options) => teacherInternshipEvidenceV3Api.visitTargets(batchId, options),
  createInternshipGuidance: (body) => realRequest('/internship/guidances', { method: 'POST', data: body || {} }),
  getInternshipRisks: ({ batchId, page = 1, pageSize = 20, status = '' } = {}) => {
    if (!batchId) return Promise.reject({ biz: true, message: '请先选择实习批次' })
    return realRequest(`/internship/risks?batchId=${encodeURIComponent(String(batchId))}&page=${page}&pageSize=${pageSize}&status=${encodeURIComponent(status)}`)
  },
  handleInternshipRisk: (id, body) => realRequest(`/internship/risks/${encodeURIComponent(String(id || ''))}/handle`, { method: 'POST', data: body || {} }),
  followInternshipRisk: (id, body) => realRequest(`/internship/risks/${encodeURIComponent(String(id || ''))}/follow`, { method: 'POST', data: body || {} }),
  closeInternshipRisk: (id, body) => realRequest(`/internship/risks/${encodeURIComponent(String(id || ''))}/close`, { method: 'POST', data: body || {} }),
  getInternshipWorkbenchTodos: ({ status='PENDING', group='ALL', page=1, pageSize=50 }={}) =>
    realRequest(`/teacher-mobile/internship/workbench/todos?status=${encodeURIComponent(status)}&group=${encodeURIComponent(group)}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  getInternshipWorkbenchMessages: ({ category='ALL', readStatus='', page=1, pageSize=20 }={}) =>
    realRequest(`/teacher-mobile/internship/workbench/messages?category=${encodeURIComponent(category)}&readStatus=${encodeURIComponent(readStatus)}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  readInternshipWorkbenchMessage: (messageId) =>
    realRequest(`/teacher-mobile/internship/workbench/messages/${encodeURIComponent(String(messageId||''))}/read`, { method:'POST' }),
  getInternshipMessageTarget: messageId =>
    realRequest(`/teacher-mobile/internship/workbench/messages/${encodeURIComponent(String(messageId||''))}/target`),
  getMyInternshipCheckins: (batchId, limit = 31, month = '') => realRequest(`/teacher-mobile/internship/activity/checkins?batchId=${encodeURIComponent(String(batchId || ''))}&limit=${encodeURIComponent(limit)}${month ? '&month='+encodeURIComponent(month) : ''}`),
  getMyInternshipCheckinRule: batchId => realRequest(`/teacher-mobile/internship/activity/checkin-rule?batchId=${encodeURIComponent(String(batchId || ''))}`),
  createMyInternshipCheckin: (body) => realRequest('/teacher-mobile/internship/activity/checkins', { method: 'POST', data: body || {} }),
  getMyInternshipMakeups: (batchId, status = '') => realRequest(`/teacher-mobile/internship/activity/makeups?batchId=${encodeURIComponent(String(batchId || ''))}${status ? '&status='+encodeURIComponent(status) : ''}`),
  applyMyInternshipMakeup: (body) => realRequest('/teacher-mobile/internship/activity/makeups', { method: 'POST', data: body || {} }),
  withdrawMyInternshipMakeup: (id) => realRequest(`/teacher-mobile/internship/activity/makeups/${encodeURIComponent(String(id || ''))}/withdraw`, { method: 'POST' }),
  getMyInternshipWorkReports: (batchId, page = 1, pageSize = 20) => realRequest(`/teacher-mobile/internship/activity/work-reports?batchId=${encodeURIComponent(String(batchId || ''))}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  saveMyInternshipWorkReport: (body) => realRequest('/teacher-mobile/internship/activity/work-reports', { method: 'POST', data: body || {} }),
  getMyInternshipPeriodReports: (batchId, page = 1, pageSize = 20) => realRequest(`/teacher-mobile/internship/activity/period-reports?batchId=${encodeURIComponent(String(batchId || ''))}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  saveMyInternshipPeriodReport: (body) => realRequest('/teacher-mobile/internship/activity/period-reports', { method: 'POST', data: body || {} }),
  getInternshipEmergencyNotices: (batchId, includeWithdrawn = true) => realRequest(`/teacher-mobile/internship/emergency-notices?batchId=${encodeURIComponent(String(batchId || ''))}&includeWithdrawn=${includeWithdrawn ? 'true' : 'false'}`),
  getPendingInternshipEmergencyNotices: (batchId) => realRequest(`/teacher-mobile/internship/emergency-notices/pending?batchId=${encodeURIComponent(String(batchId || ''))}`),
  acknowledgeInternshipEmergencyNotice: (id, batchId) => realRequest(`/teacher-mobile/internship/emergency-notices/${encodeURIComponent(String(id || ''))}/ack?batchId=${encodeURIComponent(String(batchId || ''))}`, { method: 'POST' }),
  publishInternshipEmergencyNotice: (body) => realRequest('/teacher-mobile/internship/emergency-notices', { method: 'POST', data: body || {} }),
  withdrawInternshipEmergencyNotice: (id, reason) => realRequest(`/teacher-mobile/internship/emergency-notices/${encodeURIComponent(String(id || ''))}/withdraw`, { method: 'POST', data: { reason } }),
  computeInternshipScore: (body) => realRequest('/internship/scores/compute', { method: 'POST', data: body || {} })
}
export default teacherApi
