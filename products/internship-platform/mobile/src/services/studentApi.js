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
    basicInfo: r.basicInfo || null,
    hasBatch: true, needSelect: false, candidates: r.candidates || [],
    historyMode: !!r.historyMode, recordId: r.recordId || '', batchId: r.batchId || '',
    destinationType: r.destinationType || 'NONE',
    batch: r.batchName || '实习批次',
    company: r.destinationType === 'EXEMPTED' ? '学校已批准免实习' : (r.enterpriseName || ''),
    post: r.destinationType === 'EXEMPTED' ? '免实习' : (r.positionName || ''),
    schoolMentor: r.advisorName || '待分配', companyMentor: r.enterpriseMentor || '待分配',
    statusText: r.recordStatus || '', timeline: r.timeline || [], _real: true,
    score: r.score || null, archive: r.archive || null,
    weekly: { week: `第 ${Number(r.weekly?.weekNumber || 1)} 周`, submitted: !!r.weekly?.submitted, approved: !!r.weekly?.approved, lastFeedback: r.weekly?.lastFeedback || '' },
    checkin: { done: !!r.todayCheckin?.done, time: r.todayCheckin?.time || '', totalDays: Number(r.todayCheckin?.totalDays || 0), place: r.workLocation || r.enterpriseName || '实习地点待定', note: '仅在点击时采集定位，不后台定位' },
    status: {
      todayCheckin: r.todayCheckin?.done ? 'COMPLETED' : 'PENDING',
      weekly: r.weekly?.submitted || r.weekly?.approved ? 'COMPLETED' : 'PENDING_SUBMIT',
      agreement: r.agreementStatus || 'PENDING', insurance: r.insuranceStatus || 'PENDING',
      onboard: r.recordStatus || 'PENDING', leave: r.leaveStatus || 'NONE'
    }
  }
}

export const studentApi = {
  getMessages: (page = 1, readStatus = '') => realRequest(`/mobile/me/messages?page=${page}&pageSize=20${readStatus ? '&readStatus=' + encodeURIComponent(readStatus) : ''}`),
  getMessage: id => realRequest(`/mobile/me/messages/${encodeURIComponent(String(id))}`),
  readMessage: id => realRequest(`/mobile/me/messages/${encodeURIComponent(String(id))}/read`, { method: 'POST' }),
  getBasicInfo: (batchId, internshipId) => realRequest(`/mobile/internship/context/basic-info?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  saveBasicInfo: (batchId, internshipId, body) => realRequest(`/mobile/internship/context/basic-info?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`, { method: 'PUT', data: body }),
  getInternshipEmployment: (batchId,internshipId,page=1) => internship.studentInternshipEmployment(batchId,internshipId,page),
  submitInternshipEmployment: body => internship.studentInternshipEmploymentSubmit(body),
  readInternshipEmploymentResult: (id,batchId,internshipId) => internship.studentInternshipEmploymentResultRead(id,batchId,internshipId),
  getInternship: (batchId = '') => internship.studentInternshipDashboard(batchId).then(mapInternshipDashboard),
  getInternshipCompliance: (operation, batchId) => internship.studentInternshipCompliance(operation, batchId),
  getInternshipNotices: (batchId) => internship.studentInternshipEmergencyNotices(batchId),
  getPendingEmergencyNotices: (batchId) => internship.studentInternshipPendingEmergencyNotices(batchId),
  acknowledgeEmergencyNotice: (noticeId, batchId) => internship.studentInternshipAcknowledgeEmergencyNotice(noticeId, batchId),
  getInternshipAgreements: (batchId,internshipId) => internship.studentInternshipAgreements(batchId,internshipId),
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
  getInternshipProcessReports: (batchId, internshipId, page = 1, pageSize = 20, reportType = '', focusReportId = '') =>
    internship.studentInternshipProcessReports(batchId, internshipId, page, pageSize, reportType, focusReportId),
  async downloadInternshipReportPdf(batchId, internshipId, kind, id, isCurrent) {
    const enc = value => encodeURIComponent(String(value))
    const data = await realRequest(`/mobile/internship/context/reports/${enc(kind)}/${enc(id)}/pdf?batchId=${enc(batchId)}&internshipId=${enc(internshipId)}`)
    if (!isCurrent()) return
    if (String(data?.reportId) !== String(id) || data?.reportKind !== kind || String(data.batchId) !== String(batchId) ||
        String(data.internshipId) !== String(internshipId) || data.mediaType !== 'application/pdf' || !data.contentBase64) throw new Error('报告文书来源不一致')
    const bytes = uni.base64ToArrayBuffer(data.contentBase64)
    if (new Uint8Array(bytes).slice(0,4).join(',') !== '37,80,68,70') throw new Error('报告文书内容无效')
    const filename = String(data.filename || '实习报告.pdf').replace(/[\\/\:*?"<>|]/g, '_')
    if (typeof document !== 'undefined') {
      const url = URL.createObjectURL(new Blob([bytes], {type:'application/pdf'})), link = document.createElement('a')
      try { link.href = url; link.download = filename; document.body.appendChild(link); link.click() }
      finally { link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000) }
      return
    }
    if (typeof wx !== 'undefined' && wx.getFileSystemManager && wx.env?.USER_DATA_PATH) {
      const path = `${wx.env.USER_DATA_PATH}/${Date.now()}_${filename}`, fs = wx.getFileSystemManager()
      await new Promise((resolve,reject) => fs.writeFile({filePath:path,data:bytes,success:resolve,fail:reject}))
      if (isCurrent()) await new Promise((resolve,reject) => uni.openDocument({filePath:path,fileType:'pdf',showMenu:true,success:resolve,fail:reject}))
      return
    }
    throw new Error('当前宿主无法保存报告文书，请使用学生电脑端下载')
  },
  getInternshipProcessReportDetail: (reportId, batchId, internshipId) => internship.studentInternshipProcessReportDetail(reportId, batchId, internshipId),
  getInternshipWeeklyReports: (batchId, internshipId, page = 1, pageSize = 20, focusReportId = '') =>
    internship.studentInternshipWeeklyReports(batchId, internshipId, page, pageSize, focusReportId),
  getInternshipWeeklyReportDetail: (reportId, batchId, internshipId) =>
    internship.studentInternshipWeeklyDetail(reportId, batchId, internshipId),
  submitInternshipWeeklyReport: (body) => internship.studentInternshipWeeklySubmit(body),
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
  getInternshipApplicationPositions: (batchId, internshipId, page = 1) => {
    if (!batchId || !internshipId) return Promise.reject(new Error('请先选择本人实习批次'))
    return realRequest(`/mobile/internship/context/applications/positions?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}&page=${page}&pageSize=20`)
  },
  getInternshipInsurance: (batchId,internshipId) => realRequest('/mobile/internship/insurance?batchId='+encodeURIComponent(String(batchId || ''))+'&internshipId='+encodeURIComponent(String(internshipId || ''))),
  submitInternshipInsurance: (body) => realRequest('/mobile/internship/insurance', { method: 'POST', data: body || {} }),
  getInternshipIntention: (batchId, internshipId, page = 1) => realRequest(`/mobile/internship/context/intention?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}&page=${page}`),
  saveInternshipIntention: (body) => realRequest('/mobile/internship/context/intention', { method: 'PUT', data: body || {} }),
  submitInternshipIntention: (body) => realRequest('/mobile/internship/context/intention/submit', { method: 'POST', data: body || {} }),
  withdrawInternshipIntention: (body) => realRequest('/mobile/internship/context/intention/withdraw', { method: 'POST', data: body || {} }),
  getInternshipMaterialRequirements: (batchId, internshipId) =>
    realRequest(`/mobile/internship/context/material-requirements?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  submitInternshipMaterial: (requirementId, body) =>
    realRequest(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/submit`, { method: 'POST', data: body || {} }),
  downloadInternshipMaterialTemplate: (requirementId, batchId, internshipId, templateVersionId) =>
    realDownload(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/template/download?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}${templateVersionId ? `&templateVersionId=${encodeURIComponent(templateVersionId)}` : ''}`)
}
export default studentApi
