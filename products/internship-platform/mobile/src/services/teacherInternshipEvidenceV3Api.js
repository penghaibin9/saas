import { realRequest } from './request'

const enc = encodeURIComponent

export const teacherInternshipEvidenceV3Api = {
  visitTargets(batchId, { page = 1, planId = '', studentPage = 1, internshipId = '', keyword = '' } = {}) {
    return realRequest(`/teacher-mobile/internship/visit-targets?batchId=${enc(String(batchId || ''))}&page=${enc(page)}&studentPage=${enc(studentPage)}&keyword=${enc(keyword)}${planId ? '&planId=' + enc(String(planId)) : ''}${internshipId ? '&internshipId=' + enc(String(internshipId)) : ''}`)
  },
  remindWeekly(reportId) {
    return realRequest(`/teacher-mobile/internship/weekly-reports/${enc(String(reportId || ''))}/remind`, {
      method: 'POST', data: {}
    })
  },
  createVisit(internshipId, body) {
    return realRequest(`/teacher-mobile/internship/visits/${enc(String(internshipId || ''))}`, {
      method: 'POST', data: body
    })
  },
  visitDetail(visitId) { return realRequest(`/internship/visits/${enc(String(visitId || ''))}`) },
  visitLocation(visitId, body) { return realRequest(`/internship/visits/${enc(String(visitId || ''))}/location/disclose`, { method: 'POST', data: body }) },
  rectifyVisit(visitId, body) {
    return realRequest(`/internship/visits/${enc(String(visitId || ''))}/rectify`, { method: 'POST', data: body })
  }
}

export default teacherInternshipEvidenceV3Api
