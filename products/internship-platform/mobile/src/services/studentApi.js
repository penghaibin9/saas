/** Standalone 岗位实习学生移动端 facade。只暴露岗位实习业务，不回落 mock。 */
import { realDownload, realRequest } from './request'
import * as internship from './internshipApi'

function mapInternshipDashboard(r) {
  if (!r || !r.hasData) {
    return {
      hasBatch: false, needSelect: !!r?.needSelect, candidates: r?.candidates || [],
      message: r?.message || '暂无实习记录', _real: true,
      company: '', post: '', schoolMentor: '', companyMentor: '', batch: '', batchId: '',
      timeline: [], weekly: { week: '第 1 周', submitted: false, lastFeedback: '' },
      checkin: { done: false, time: '', totalDays: 0, place: '', note: '仅在点击时采集定位，不后台定位' },
      status: { todayCheckin: 'PENDING', weekly: 'PENDING_SUBMIT', agreement: 'PENDING', insurance: 'PENDING', onboard: 'PENDING', leave: 'NONE' }
    }
  }
  return {
    eligibilityReview: r.eligibilityReview || null,
    hasBatch: true, needSelect: false, candidates: r.candidates || [],
    historyMode: !!r.historyMode, recordId: r.recordId || '', batchId: r.batchId || '',
    destinationType: r.destinationType || 'NONE',
    batch: r.batchName || '实习批次',
    company: r.destinationType === 'EXEMPTED' ? '学校已批准免实习' : (r.enterpriseName || ''),
    post: r.destinationType === 'EXEMPTED' ? '免实习' : (r.positionName || ''),
    schoolMentor: r.advisorName || '待分配', companyMentor: r.enterpriseMentor || '待分配',
    statusText: r.recordStatus || '', timeline: r.timeline || [], _real: true,
    score: r.score || null, archive: r.archive || null,
    weekly: { week: `第 ${Number(r.weekly?.weekNumber || 1)} 周`, submitted: !!r.weekly?.submitted, lastFeedback: r.weekly?.lastFeedback || '' },
    checkin: { done: !!r.todayCheckin?.done, time: r.todayCheckin?.time || '', totalDays: Number(r.todayCheckin?.totalDays || 0), place: r.workLocation || r.enterpriseName || '实习地点待定', note: '仅在点击时采集定位，不后台定位' },
    status: {
      todayCheckin: r.todayCheckin?.done ? 'COMPLETED' : 'PENDING',
      weekly: r.weekly?.submitted ? 'COMPLETED' : 'PENDING_SUBMIT',
      agreement: r.agreementStatus || 'PENDING', insurance: r.insuranceStatus || 'PENDING',
      onboard: r.recordStatus || 'PENDING', leave: r.leaveStatus || 'NONE'
    }
  }
}

export const studentApi = {
  getInternship: (batchId = '') => internship.studentInternshipDashboard(batchId).then(mapInternshipDashboard),
  getInternshipCompliance: (operation, batchId) => internship.studentInternshipCompliance(operation, batchId),
  getInternshipNotices: (batchId) => internship.studentInternshipEmergencyNotices(batchId),
  getPendingEmergencyNotices: (batchId) => internship.studentInternshipPendingEmergencyNotices(batchId),
  acknowledgeEmergencyNotice: (noticeId, batchId) => internship.studentInternshipAcknowledgeEmergencyNotice(noticeId, batchId),
  getInternshipAgreements: () => internship.studentInternshipAgreements(),
  getInternshipAgreementDetail: (id) => internship.studentInternshipAgreementDetail(id),
  confirmInternshipAgreement: (id, body) => internship.studentInternshipAgreementConfirm(id, body),
  getInternshipConsentDetail: (id) => internship.studentInternshipConsentDetail(id),
  viewInternshipConsent: (id) => internship.studentInternshipConsentView(id),
  confirmInternshipConsent: (id, body) => internship.studentInternshipConsentConfirm(id, body),
  rejectInternshipConsent: (id, body) => internship.studentInternshipConsentReject(id, body),
  getInternshipSafetyCourses: (batchId) => internship.studentInternshipSafetyCourses(batchId),
  getInternshipSafetyCompletions: (batchId) => internship.studentInternshipSafetyCompletions(batchId),
  getInternshipSafetyCourseDetail: (id) => internship.studentInternshipSafetyCourseDetail(id),
  startInternshipSafetyCourse: (id) => internship.studentInternshipSafetyStart(id),
  submitInternshipSafetyCourse: (id, body) => internship.studentInternshipSafetySubmit(id, body),
  commitInternshipSafety: (id, body) => internship.studentInternshipSafetyCommit(id, body),
  getInternshipProcessReports: (batchId, internshipId) => internship.studentInternshipProcessReports(batchId, internshipId),
  submitInternshipProcessReport: (body) => internship.studentInternshipProcessReportSubmit(body),
  getInternshipSelfEval: (batchId, internshipId) => internship.studentInternshipSelfEval(batchId, internshipId),
  submitInternshipSelfEval: (body) => internship.studentInternshipSelfEvalSubmit(body),
  getInternshipScoreAppeal: (batchId, internshipId) => internship.studentInternshipScoreAppeal(batchId, internshipId),
  submitInternshipScoreAppeal: (body) => internship.studentInternshipScoreAppealSubmit(body),
  getInternshipFeedback: (batchId, internshipId) => internship.studentInternshipFeedback(batchId, internshipId),
  submitInternshipFeedback: (body) => internship.studentInternshipFeedbackSubmit(body),
  withdrawInternshipFeedback: (feedbackId, body) => internship.studentInternshipFeedbackWithdraw(feedbackId, body),
  getInternshipHelp: (batchId, internshipId) => internship.studentInternshipHelp(batchId, internshipId),
  reportInternshipHelp: (body) => internship.studentInternshipHelpSubmit(body),
  getInternshipSupport: (batchId, internshipId) => internship.studentInternshipSupport(batchId, internshipId),
  askInternshipSupport: (body) => internship.studentInternshipSupportAsk(body),
  solveInternshipSupport: (sessionId, body) => internship.studentInternshipSupportSolved(sessionId, body),
  unresolvedInternshipSupport: (sessionId, body) => internship.studentInternshipSupportUnresolved(sessionId, body),
  submitCheckin: (body) => realRequest('/mobile/internship/checkin', { method: 'POST', data: body || {} }),
  getCheckinPreflight: (timezoneName = '', batchId = '') => {
    const q = []
    if (timezoneName) q.push('timezoneName=' + encodeURIComponent(timezoneName))
    if (batchId) q.push('batchId=' + encodeURIComponent(batchId))
    return realRequest('/mobile/internship/checkin/preflight' + (q.length ? '?' + q.join('&') : ''), { method: 'POST' })
  },
  getCheckinWeek: (timezoneName = '', batchId = '') => {
    const q = []
    if (timezoneName) q.push('timezoneName=' + encodeURIComponent(timezoneName))
    if (batchId) q.push('batchId=' + encodeURIComponent(batchId))
    return realRequest('/mobile/internship/checkin/week' + (q.length ? '?' + q.join('&') : ''))
  },
  getCheckinCalendar: (month = '', timezoneName = '', batchId = '') => {
    const q = []
    if (month) q.push('month=' + encodeURIComponent(month))
    if (timezoneName) q.push('timezoneName=' + encodeURIComponent(timezoneName))
    if (batchId) q.push('batchId=' + encodeURIComponent(batchId))
    return realRequest('/mobile/internship/checkin/calendar' + (q.length ? '?' + q.join('&') : ''))
  },
  getCheckinExemptions: (batchId, internshipId) =>
    realRequest(`/mobile/internship/context/checkin-exemptions?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  applyCheckinExemption: (body) =>
    realRequest('/mobile/internship/context/checkin-exemptions', { method: 'POST', data: body || {} }),
  withdrawCheckinExemption: (id, body) =>
    realRequest(`/mobile/internship/context/checkin-exemptions/${encodeURIComponent(id)}/withdraw`, { method: 'POST', data: body || {} }),
  getInternshipEnterprises: (city = '') => realRequest('/mobile/internship/enterprises' + (city ? `?city=${encodeURIComponent(city)}` : '')),
  getInternshipInsurance: () => realRequest('/mobile/internship/insurance'),
  submitInternshipInsurance: (body) => realRequest('/mobile/internship/insurance', { method: 'POST', data: body || {} }),
  getInternshipIntention: () => realRequest('/mobile/internship/intention'),
  saveInternshipIntention: (body) => realRequest('/mobile/internship/intention', { method: 'PUT', data: body || {} }),
  submitInternshipIntention: () => realRequest('/mobile/internship/intention/submit', { method: 'POST' }),
  withdrawInternshipIntention: () => realRequest('/mobile/internship/intention/withdraw', { method: 'POST' }),
  getInternshipMaterialRequirements: (batchId, internshipId) =>
    realRequest(`/mobile/internship/context/material-requirements?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  submitInternshipMaterial: (requirementId, body) =>
    realRequest(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/submit`, { method: 'POST', data: body || {} }),
  downloadInternshipMaterialTemplate: (requirementId, batchId, internshipId) =>
    realDownload(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/template/download?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`)
}
export default studentApi
