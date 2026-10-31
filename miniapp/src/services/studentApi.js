import { realDownload } from './request'
/** 学生端数据服务：关键业务走真实接口，岗位实习禁止回落 mock 假状态。 */
import { mockRequest, realFirst, realFirstStrict, realRequest } from './request'
import { latestRead } from './latestRead'
import * as real from './realApi'
import * as internship from './internshipApi'
import * as M from '@/mock'
import { presentMessagePage } from './messagePresentation'

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
  getHome: () =>
    realFirstStrict('student.home',
      () => real.studentHomeReal(),
      () => mockRequest(M.studentHome)),
  getAgenda: (days = 7, cursor = '', pageSize = 20) => real.studentAgenda(days, cursor, pageSize),
  getCases: (statusGroup = 'all', cursor = '', pageSize = 20) => real.studentCases(statusGroup, cursor, pageSize),
  getCaseDetail: (caseId) => real.studentCaseDetail(caseId),
  searchMine: (keyword, pageSize = 20) => real.studentSearch(keyword, pageSize),
  getProfile: () =>
    realFirstStrict('student.profile',
      () => real.enrichProfileReal(),
      () => mockRequest(M.studentProfile)),
  getOrientation: () =>
    realFirstStrict('student.orientation',
      () => real.enrichOrientation(),
      () => mockRequest(M.studentOrientation)),
  getOrientationBatchStatus: () => real.orientationBatchStatus(),
  submitOrientationCollect: (body) => real.orientationCollectSubmit(body),
  submitOrientationArrival: (body) => real.orientationArrivalSubmit(body),
  submitOrientationMaterial: (body) => real.orientationMaterialSubmit(body),
  submitOrientationGreenChannel: (body) => real.orientationGreenChannelSubmit(body),
  issueOrientationCheckinToken: () => real.orientationCheckinToken(),
  getServices: () => real.enrichCampusService(),
  getAcademic: () =>
    realFirstStrict('student.academic',
      () => real.enrichAcademic(),
      () => mockRequest(M.studentAcademic)),
  getInternship: (batchId = '') => internship.studentInternshipDashboard(batchId).then(mapInternshipDashboard),
  getInternshipWeeklyReports: (batchId, internshipId, page = 1, pageSize = 20, focusReportId = '') =>
    internship.studentInternshipWeeklyReports(batchId, internshipId, page, pageSize, focusReportId),
  submitInternshipWeeklyReport: (body) => internship.studentInternshipWeeklySubmit(body),
  getInternshipProcessReports: (batchId, internshipId, page = 1, pageSize = 20, reportType = '', focusReportId = '') =>
    internship.studentInternshipProcessReports(batchId, internshipId, page, pageSize, reportType, focusReportId),
  submitInternshipProcessReport: (body) => internship.studentInternshipProcessReportSubmit(body),
  getInternshipCompliance: (operation, batchId) => internship.studentInternshipCompliance(operation, batchId),
  getInternshipConsents: () => internship.studentInternshipConsents(),
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
  getGraduation: () => latestRead('student:graduation:overview', () => real.enrichGraduation()),
  // 办理进度 + 唯一“当前要做”：后端统一派生，与学生 PC 同源
  getGraduationJourney: () => latestRead('student:graduation:journey', () => realRequest('/mobile/graduation/journey')),
  getGraduationMaterialLibrary: () =>
    latestRead('student:graduation:materials', () => realRequest('/mobile/graduation/material-center/library?includeHistory=true')),
  submitGraduationMaterial: (materialCode, body) =>
    realRequest(`/mobile/graduation/material-center/materials/${encodeURIComponent(materialCode)}/submit`, {
      method: 'POST', data: { ...body, clientSurface: 'MP_WEIXIN' }
    }),
  getGraduationActiveRound: () => real.gdActiveRound(),
  getGraduationTopics: (params) => real.gdTopics(params),
  getMyGraduationChangeRequests: () => real.gdMyChangeRequests(),
  submitGraduationChoices: (roundId, choices) => real.gdSubmitChoices(roundId, choices),
  withdrawGraduationChoices: (roundId) => real.gdWithdrawChoices(roundId),
  requestGraduationTopicChange: (newTopicId, reason) => real.gdRequestChange(newTopicId, reason),
  getGraduationProposal: () => latestRead('student:graduation:proposal', () => real.gdProposal()),
  submitGraduationProposal: (body) => real.gdSubmitProposal(body),
  getGraduationFinal: () => latestRead('student:graduation:final', () => real.gdFinal()),
  submitGraduationFinal: (body) => real.gdSubmitFinal(body),
  getGraduationTaskbook: () => real.gdTaskbook(),
  // 必须携带页面实际展示的版本；后端据此拒绝过期页面确认新版本任务书。
  confirmGraduationTaskbook: (taskbookVersion) =>
    realRequest('/mobile/graduation/taskbook/confirm', {
      method: 'POST', data: { taskbookVersion }
    }),
  getGraduationMidterm: () => latestRead('student:graduation:midterm', () => real.gdMidterm()),
  submitGraduationMidtermRectify: (content) => real.gdMidtermRectify(content),
  getGraduationDefense: () => latestRead('student:graduation:defense', () => real.gdDefense()),
  getGraduationGrade: () => latestRead('student:graduation:grade', () => real.gdGrade()),
  appealGraduationGrade: (reason) => real.gdGradeAppeal(reason),
  getGraduationPeerTasks: () => latestRead('student:graduation:peer', () => real.gdPeerTasks()),
  submitGraduationPeer: (pid, opinion) => real.gdPeerSubmit(pid, opinion),
  rectifyGraduationPeer: (pid, note) => real.gdPeerRectify(pid, note),
  getGraduationArchive: () => latestRead('student:graduation:archive', () => real.gdArchive()),
  getEmployment: () => real.employmentMy(),
  getApplications: () =>
    realFirst('student.applications',
      () => real.selfApplications(),
      () => mockRequest({ tabs: M.applicationTabs, list: M.applications })),
  getMessagesPage: (tab = 'todo', page = 1, pageSize = 20) =>
    realFirstStrict('student.messages.page',
      () => real.selfMessagesPage(tab, page, pageSize),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })).then(presentMessagePage),
  getMessages: () =>
    realFirstStrict('student.messages',
      () => real.selfMessages(),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })).then(presentMessagePage),
  submitServiceApply: (body) => real.submitServiceApply(body),
  submitWeeklyReport: (body) => real.submitWeeklyReport(body),
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
  getInternshipEnterprises: (city) => real.internshipEnterprises(city),
  markMessageRead: (id) => real.markMessageRead(id),
  getMessageDetail: (id) => real.getMessageDetail(id),
  ackMessageReceipt: (id) => real.ackMessageReceipt(id),
  getInternshipAgreements: (batchId,internshipId) => internship.studentInternshipAgreements(batchId,internshipId),
  getInternshipAgreementDetail: (id) => internship.studentInternshipAgreementDetail(id),
  confirmInternshipAgreement: (id, body) => internship.studentInternshipAgreementConfirm(id, body),
  getInternshipLeaves: () => real.internshipLeaves(),
  applyInternshipLeave: (body) => real.applyInternshipLeave(body),
  withdrawInternshipLeave: (id) => real.withdrawInternshipLeave(id),
  returnInternshipLeave: (id, body) => real.returnInternshipLeave(id, body),
  getInternshipMakeups: () => real.internshipMakeups(),
  applyInternshipMakeup: (body) => real.applyInternshipMakeup(body),
  withdrawInternshipMakeup: (id) => real.withdrawInternshipMakeup(id),
  getInternshipSelfEval: (batchId, internshipId) => internship.studentInternshipSelfEval(batchId, internshipId),
  submitInternshipSelfEval: (body) => internship.studentInternshipSelfEvalSubmit(body),
  getInternshipScoreAppeal: (batchId, internshipId) => internship.studentInternshipScoreAppeal(batchId, internshipId),
  submitInternshipScoreAppeal: (body) => internship.studentInternshipScoreAppealSubmit(body),
  getInternshipHelp: (batchId, internshipId) => internship.studentInternshipHelp(batchId, internshipId),
  reportInternshipHelp: (body) => internship.studentInternshipHelpSubmit(body),
  getInternshipIntention: (batchId, internshipId, page = 1) => realRequest(`/mobile/internship/context/intention?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}&page=${page}`),
  saveInternshipIntention: (body) => realRequest('/mobile/internship/context/intention', { method: 'PUT', data: body || {} }),
  submitInternshipIntention: (body) => realRequest('/mobile/internship/context/intention/submit', { method: 'POST', data: body || {} }),
  withdrawInternshipIntention: (body) => realRequest('/mobile/internship/context/intention/withdraw', { method: 'POST', data: body || {} }),
  getInternshipChangeRequests: () => real.internshipChangeRequests(),
  applyInternshipChange: (body) => real.applyInternshipChange(body),
  getInternshipApplications: () => real.internshipApplications(),
  saveInternshipApplication: (body) => real.saveInternshipApplication(body),
  submitInternshipApplication: (id) => real.submitInternshipApplication(id),
  withdrawInternshipApplication: (id) => real.withdrawInternshipApplication(id),
  getInternshipInsurance: (batchId,internshipId) => realRequest('/mobile/internship/insurance?batchId='+encodeURIComponent(String(batchId || ''))+'&internshipId='+encodeURIComponent(String(internshipId || ''))),
  submitInternshipInsurance: (body) => realRequest('/mobile/internship/insurance', { method: 'POST', data: body || {} }),
  getInternshipPlan: () => real.internshipPlanMy(),
  getInternshipPlanTasks: () => real.internshipPlanTasksMy(),
  ackInternshipPlan: () => real.ackInternshipPlan(),
  submitInternshipPlanTask: (sortOrder, body) => real.submitInternshipPlanTask(sortOrder, body),
  submitProcessReport: (body) => real.submitProcessReport(body),
  getAffairsOverview: () => real.affairsOverview(),
  getMyLeaves: (page = 1, pageSize = 20) => real.affairsLeaveMy(page, pageSize),
  applyLeave: (body) => real.affairsLeaveApply(body),
  resubmitLeave: (leaveId, body) => real.affairsLeaveResubmit(leaveId, body),
  cancelLeave: (leaveId, body) => real.affairsLeaveCancel(leaveId, body),
  extendLeave: (leaveId, body) => real.affairsLeaveExtend(leaveId, body),
  getMyAid: () => real.affairsAidMy(),
  getAidBatches: (params) => real.affairsAidBatches(params),
  applyAid: (body) => real.affairsAidApply(body),
  objectAid: (body) => real.affairsAidObjection(body),
  getMyTalks: () => real.affairsTalkMy(),
  getMyFunding: () => real.affairsFundingMy(),
  getFundingDetail: (id) => real.affairsFundingDetail(id),
  getFundingBatches: (params) => real.affairsFundingBatches(params),
  applyFunding: (body) => real.affairsFundingApply(body),
  getWorkStudyPosts: (params) => real.affairsWorkStudyPosts(params),
  getMyWorkStudy: () => real.affairsWorkStudyMy(),
  applyWorkStudy: (postId, body) => real.affairsWorkStudyApply(postId, body),
  withdrawWorkStudy: (recordId, version) => real.affairsWorkStudyWithdraw(recordId, version),
  getMyLoans: () => real.affairsLoans(),
  submitLoan: (body) => real.affairsLoanSubmit(body),
  resubmitLoan: (loanId, body) => real.affairsLoanResubmit(loanId, body),
  withdrawLoan: (loanId, version) => real.affairsLoanWithdraw(loanId, version),
  getMyFeeReductions: () => real.affairsFeeReductions(),
  submitFeeReduction: (body) => real.affairsFeeReductionSubmit(body),
  resubmitFeeReduction: (feeId, body) => real.affairsFeeReductionResubmit(feeId, body),
  withdrawFeeReduction: (feeId, version) => real.affairsFeeReductionWithdraw(feeId, version),
  getMyDiscipline: () => real.affairsDisciplineMy(),
  appealDiscipline: (body) => real.affairsDisciplineAppeal(body),
  getMyDorm: () => real.affairsDormMy(),
  getDormOptions: () => real.affairsDormOptions(),
  getDormRooms: (buildingId, floor) => real.affairsDormRooms(buildingId, floor),
  getDormBeds: (roomId) => real.affairsDormBeds(roomId),
  selfSelectBed: (bedId) => real.affairsDormSelfSelect(bedId),
  getMyActivities: (page = 1, pageSize = 20) => real.affairsMyActivities(page, pageSize),
  enrollActivity: (activityId, action) => real.affairsActivityEnroll(activityId, action),
  checkinActivity: (activityId, method) => real.affairsActivityCheckin(activityId, method),
  getPsySurveyQuestions: () => real.psySurveyQuestions(),
  submitPsySurvey: (answers, wantsContact) => real.psySurveySubmit(answers, wantsContact),
  getPsySurveyHistory: () => real.psySurveyHistory(),
  getNotifyPreferences: () => real.notifyPreferences(),
  setNotifyPreference: (key, enabled) => real.notifySetPreference(key, enabled),
  getMySchedule: (params = {}) => real.acadScheduleMy(params),
  getMyTranscript: (params = {}) => real.acadTranscriptMy(params),
  getMyAcadStatus: (params = {}) => real.acadStatusMy(params),
  getTransferOptions: (params = {}) => real.acadTransferOptions(params),
  submitStatusChange: (body) => real.acadStatusChange(body),
  printMyTranscript: (reason) => real.acadTranscriptPrint(reason),
  printMySchedule: (reason) => real.acadSchedulePrint(reason),
  getMyGraduation: () => real.acadGraduationMy(),
  getMyCredits: (params = {}) => real.acadCreditsMy(params),
  getMyWarnings: (params) => real.acadWarningMy(params),
  getMyMakeup: (params = {}) => real.acadMakeupMy(params),
  getMakeupOptions: (params = {}) => real.acadMakeupOptions(params),
  applyRetake: (payload) => real.acadRetakeApply(payload),
  applyExemption: (payload) => real.acadExemptionApply(payload),
  resubmitExemption: (exemptionId, payload) => real.acadExemptionResubmit(exemptionId, payload),
  getMyRegistration: (params = {}) => real.acadRegistrationMy(params),
  registerSelf: (batchId) => real.acadRegistrationRegister(batchId),
  deferRegistration: (batchId, reason, requestedUntil) => real.acadRegistrationDefer(batchId, reason, requestedUntil),
  getMyAttendance: (params = {}) => real.acadAttendanceMy(params),
  getMyCalendar: () => real.acadCalendarMy(),
  getMyClearance: (params = {}) => real.acadClearanceMy(params),
  printExamTicket: (reason) => real.acadExamTicketPrint(reason),
  printStatusChange: (body) => real.acadStatusChangePrint(body),
  getSelectionCourses: (batchId) => real.acadSelectionCourses(batchId),
  getSelectionBatches: (params = {}) => real.acadSelectionBatches(params),
  getSelectionCoursesPage: (params = {}) => real.acadSelectionCoursesPage(params),
  preflightSelection: (selectionCourseId) => real.acadSelectionPreflight(selectionCourseId),
  preflightDropSelection: (selectionCourseId) => real.acadSelectionDropPreflight(selectionCourseId),
  enrollSelection: (selectionCourseId) => real.acadSelectionEnroll(selectionCourseId),
  dropSelection: (selectionCourseId) => real.acadSelectionDrop(selectionCourseId),
  getMySelections: (batchId) => real.acadSelectionMy(batchId),
  getMySelectionsPage: (params = {}) => real.acadSelectionMyPage(params),
  getMyExamSchedule: (params = {}) => real.acadExamMy(params),
  getMyDeferOptions: () => real.acadExamDeferOptions(),
  getMyDeferrals: (params = {}) => real.acadExamDeferMy(params),
  applyDefer: (examCourseId, reasonType, reason) => real.acadExamDeferApply(examCourseId, reasonType, reason),
  resubmitDefer: (deferId, expectedVersion, reason) => real.acadExamDeferResubmit(deferId, expectedVersion, reason),
  getRecognitionCourses: (params) => real.acadRecognitionCourses(params),
  getMyRecognition: (params = {}) => real.acadRecognitionMy(params),
  submitRecognition: (body) => real.acadRecognitionSubmit(body),
  getMyRecheck: (params = {}) => real.acadRecheckMy(params),
  getMyRecheckEligible: (gradeId) => real.acadRecheckEligible(gradeId),
  submitRecheck: (body) => real.acadRecheckSubmit(body),
  getMyTextbook: (params = {}) => real.acadTextbookMy(params),
  signTextbook: (recordId) => real.acadTextbookSign(recordId),
  getMyLevelExam: (params = {}) => real.acadLevelExamMy(params),
  registerLevelExam: (examId) => real.acadLevelRegister(examId),
  cancelLevelExam: (examId) => real.acadLevelCancel(examId),
  getMyMajorSplit: (params = {}) => real.acadMajorSplitMy(params),
  getMajorSplitOptions: (batchId, params = {}) => real.acadMajorSplitOptions(batchId, params),
  submitMajorSplit: (batchId, choices) => real.acadMajorSplitSubmit(batchId, choices),
  getMyEvaluationTasks: (params = {}) => real.acadEvaluationTasks(params),
  submitEvaluation: (body) => real.acadEvaluationSubmit(body),
  exportMyData: () => realRequest('/mobile/me/export-data'),
  getBasicInfo: (batchId, internshipId) => realRequest(`/mobile/internship/context/basic-info?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  saveBasicInfo: (batchId, internshipId, body) => realRequest(`/mobile/internship/context/basic-info?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`, { method: 'PUT', data: body }),
  getInternshipEmployment: (batchId,internshipId,page=1) => internship.studentInternshipEmployment(batchId,internshipId,page),
  submitInternshipEmployment: body => internship.studentInternshipEmploymentSubmit(body),
  readInternshipEmploymentResult: (id,batchId,internshipId) => internship.studentInternshipEmploymentResultRead(id,batchId,internshipId),
  getInternshipNotices: (batchId) => internship.studentInternshipEmergencyNotices(batchId),
  getPendingEmergencyNotices: (batchId) => internship.studentInternshipPendingEmergencyNotices(batchId),
  acknowledgeEmergencyNotice: (noticeId, batchId) => internship.studentInternshipAcknowledgeEmergencyNotice(noticeId, batchId),
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
  getInternshipWeeklyReportDetail: (reportId, batchId, internshipId) =>
    internship.studentInternshipWeeklyDetail(reportId, batchId, internshipId),
  getInternshipFeedback: (batchId, internshipId) => internship.studentInternshipFeedback(batchId, internshipId),
  submitInternshipFeedback: (body) => internship.studentInternshipFeedbackSubmit(body),
  withdrawInternshipFeedback: (feedbackId, body) => internship.studentInternshipFeedbackWithdraw(feedbackId, body),
  getInternshipSupport: (batchId, internshipId) => internship.studentInternshipSupport(batchId, internshipId),
  askInternshipSupport: (body) => internship.studentInternshipSupportAsk(body),
  solveInternshipSupport: (sessionId, body) => internship.studentInternshipSupportSolved(sessionId, body),
  unresolvedInternshipSupport: (sessionId, body) => internship.studentInternshipSupportUnresolved(sessionId, body),
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
  getInternshipMaterialRequirements: (batchId, internshipId) =>
    realRequest(`/mobile/internship/context/material-requirements?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}`),
  submitInternshipMaterial: (requirementId, body) =>
    realRequest(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/submit`, { method: 'POST', data: body || {} }),
  downloadInternshipMaterialTemplate: (requirementId, batchId, internshipId, templateVersionId) =>
    realDownload(`/mobile/internship/context/material-requirements/${encodeURIComponent(requirementId)}/template/download?batchId=${encodeURIComponent(batchId)}&internshipId=${encodeURIComponent(internshipId)}${templateVersionId ? `&templateVersionId=${encodeURIComponent(templateVersionId)}` : ''}`)
}
export default studentApi
