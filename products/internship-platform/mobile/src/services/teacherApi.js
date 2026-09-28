/** Standalone 岗位实习教师移动端 facade。禁止回落其他业务域或 mock。 */
import { realRequest } from './request'
import * as sequential from './teacherSequentialV3Api'

export const teacherApi = {
  getWeeklyReports: (options = {}) => sequential.getInternshipReviewQueue(options),
  handleCheckin: (id, action, comment, riskLevel = null) => sequential.handleCheckin(id, action, comment, riskLevel),
  async getWeeklyDetail(id) {
    const d = await realRequest('/internship/reports/' + encodeURIComponent(String(id || '')))
    const c = d?.content || {}
    return {
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
  getInternshipVisitPlans: () => realRequest('/mobile/teacher/internship/visit-plans'),
  createInternshipGuidance: (body) => realRequest('/mobile/teacher/internship/guidance', { method: 'POST', data: body || {} }),
  getInternshipRisks: () => realRequest('/mobile/teacher/internship/risks'),
  handleInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/handle`, { method: 'POST', data: body || {} }),
  followInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/follow`, { method: 'POST', data: body || {} }),
  closeInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/close`, { method: 'POST', data: body || {} }),
  getMyInternshipCheckins: (batchId, limit = 31) => realRequest(`/teacher-mobile/internship/activity/checkins?batchId=${encodeURIComponent(String(batchId || ''))}&limit=${encodeURIComponent(limit)}`),
  createMyInternshipCheckin: (body) => realRequest('/teacher-mobile/internship/activity/checkins', { method: 'POST', data: body || {} }),
  getMyInternshipWorkReports: (batchId, page = 1, pageSize = 20) => realRequest(`/teacher-mobile/internship/activity/work-reports?batchId=${encodeURIComponent(String(batchId || ''))}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  saveMyInternshipWorkReport: (body) => realRequest('/teacher-mobile/internship/activity/work-reports', { method: 'POST', data: body || {} }),
  getMyInternshipPeriodReports: (batchId, page = 1, pageSize = 20) => realRequest(`/teacher-mobile/internship/activity/period-reports?batchId=${encodeURIComponent(String(batchId || ''))}&page=${encodeURIComponent(page)}&pageSize=${encodeURIComponent(pageSize)}`),
  saveMyInternshipPeriodReport: (body) => realRequest('/teacher-mobile/internship/activity/period-reports', { method: 'POST', data: body || {} }),
  getInternshipEmergencyNotices: (batchId, includeWithdrawn = true) => realRequest(`/teacher-mobile/internship/emergency-notices?batchId=${encodeURIComponent(String(batchId || ''))}&includeWithdrawn=${includeWithdrawn ? 'true' : 'false'}`),
  publishInternshipEmergencyNotice: (body) => realRequest('/teacher-mobile/internship/emergency-notices', { method: 'POST', data: body || {} }),
  withdrawInternshipEmergencyNotice: (id, reason) => realRequest(`/teacher-mobile/internship/emergency-notices/${encodeURIComponent(String(id || ''))}/withdraw`, { method: 'POST', data: { reason } }),
  computeInternshipScore: (body) => realRequest('/mobile/teacher/internship/scores/compute', { method: 'POST', data: body || {} })
}
export default teacherApi
