import { realRequest } from './request'

const enc = encodeURIComponent

export const teacherInternshipEvidenceV3Api = {
  visitTargets() {
    return realRequest('/teacher-mobile/internship/visit-targets')
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
  }
}

export default teacherInternshipEvidenceV3Api
