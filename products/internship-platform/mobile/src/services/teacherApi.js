/** Standalone 岗位实习教师移动端 facade。禁止回落其他业务域或 mock。 */
import { realRequest } from './request'
import * as sequential from './teacherSequentialV3Api'

export const teacherApi = {
  getWeeklyReports: (options = {}) => sequential.getInternshipReviewQueue(options),
  handleCheckin: (id, action, comment, riskLevel = null) => sequential.handleCheckin(id, action, comment, riskLevel),
  async getWeeklyDetail(id) {
    const d = await realRequest('/internship/reports/' + encodeURIComponent(String(id || '')))
    const c = d?.content || {}
    return { work: c.work || '', harvest: c.harvest || '', plan: c.plan || '', positionName: d?.positionName || '', reviewComment: d?.reviewComment || '' }
  },
  reviewWeekly: (id, action, comment, expectedVersion) =>
    realRequest(`/mobile/teacher/internship/weekly/${encodeURIComponent(String(id || ''))}/review`, {
      method: 'POST', data: { action, comment: comment || '', expectedVersion }
    }),
  getInternshipVisitPlans: () => realRequest('/mobile/teacher/internship/visit-plans'),
  createInternshipGuidance: (body) => realRequest('/mobile/teacher/internship/guidance', { method: 'POST', data: body || {} }),
  getInternshipRisks: () => realRequest('/mobile/teacher/internship/risks'),
  handleInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/handle`, { method: 'POST', data: body || {} }),
  followInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/follow`, { method: 'POST', data: body || {} }),
  closeInternshipRisk: (id, body) => realRequest(`/mobile/teacher/internship/risks/${encodeURIComponent(String(id || ''))}/close`, { method: 'POST', data: body || {} }),
  computeInternshipScore: (body) => realRequest('/mobile/teacher/internship/scores/compute', { method: 'POST', data: body || {} })
}
export default teacherApi
