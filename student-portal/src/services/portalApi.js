/**
 * 学生 PC 门户 · API 门面。只暴露门户允许调用的接口（严格边界）。
 * 查看类走 /mobile/me/* 与 /mobile/{domain}/my；PC 重活（长表单/大表格/材料/证明/打印）走 /portal/*。
 * 后端 /portal/* 由服务层 _require_student + SELF 数据范围收口，仅本人可读写。
 * 禁止：/admin/*、/students、/students/{id}、/approvals/*、/todos 全量、/auth/mock-login。
 */
import { downloadFile, request, uploadFile } from './request'

const q = (obj) => {
  const parts = Object.entries(obj || {})
    .filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export const portalApi = {
  // ── 认证 / 通用查看 ──
  login: (loginName, password, tenantCode) =>
    request('/auth/login', {
      method: 'POST',
      auth: false,
      body: {
        loginName,
        password,
        ...(tenantCode ? { tenantCode } : {}),
        clientType: 'PC'
      }
    }),
  portalConfig: () => request('/mobile/me/portal-config'),
  overview: () => request('/mobile/me/overview'),
  profile: () => request('/mobile/me/profile'),
  todos: () => request('/mobile/me/todos'),
  messages: () => request('/mobile/me/messages'),
  domainMy: (domain) => request(`/mobile/${domain}/my`),

  // ── 首页工作台聚合（PC）──
  homeOverview: () => request('/portal/home/overview'),

  // ── 我的档案（学籍只读 + 敏感明文授权 + 家长授权代理）──
  profileEnrollment: () => request('/portal/profile/enrollment'),
  profileSensitive: (field, reason) =>
    request('/portal/profile/sensitive', { method: 'POST', body: { field, reason } }),
  listGuardians: () => request('/portal/parent/guardians'),
  bindGuardian: (body) => request('/portal/parent/guardians', { method: 'POST', body }),
  revokeGuardian: (linkId) =>
    request(`/portal/parent/guardians/${encodeURIComponent(linkId)}/revoke`, { method: 'POST' }),

  // ── 教务学业（成绩单/课表/选课/学籍/考试/缓考/补重修免修/毕业自查）──
  academicTranscript: () => request('/portal/academic/transcript'),
  academicTranscriptPrint: (body) => request('/portal/academic/transcript/print', { method: 'POST', body }),
  academicSchedule: () => request('/portal/academic/schedule'),
  academicSchedulePrint: (body) => request('/portal/academic/schedule/print', { method: 'POST', body }),
  academicCourseSelection: (batchId) => request(`/portal/academic/course-selection${q({ batchId })}`),
  academicEnroll: (body) => request('/portal/academic/course-selection/enroll', { method: 'POST', body }),
  academicDrop: (body) => request('/portal/academic/course-selection/drop', { method: 'POST', body }),
  academicSelectionRecords: (batchId) => request(`/portal/academic/course-selection/records${q({ batchId })}`),
  academicStatus: () => request('/portal/academic/status'),
  academicTransferOptions: () => request('/portal/academic/transfer-options'),
  academicStatusChange: (body) => request('/portal/academic/status-change', { method: 'POST', body }),
  academicStatusChangePrint: (body) => request('/portal/academic/status-change/print', { method: 'POST', body }),
  academicExam: () => request('/portal/academic/exam'),
  academicExamDefer: (status) => request(`/portal/academic/exam/defer${q({ status })}`),
  academicExamDeferApply: (body) => request('/portal/academic/exam/defer/apply', { method: 'POST', body }),
  academicExamDeferResubmit: (deferId) =>
    request(`/portal/academic/exam/defer/${encodeURIComponent(deferId)}/resubmit`, { method: 'POST' }),
  academicMakeup: () => request('/portal/academic/makeup'),
  academicRetakeApply: (body) => request('/portal/academic/retake/apply', { method: 'POST', body }),
  academicExemptionApply: (body) => request('/portal/academic/exemption/apply', { method: 'POST', body }),
  academicGraduationAudit: () => request('/portal/academic/graduation-audit'),
  academicEvaluationTasks: () => request('/portal/academic/evaluation/tasks'),
  academicEvaluationSubmit: (body) => request('/portal/academic/evaluation/submit', { method: 'POST', body }),
  academicExamDeferOptions: () => request('/portal/academic/exam/defer/options'),
  academicGradeRecheck: () => request('/portal/academic/grade-recheck'),
  academicGradeRecheckSubmit: (body) => request('/portal/academic/grade-recheck', { method: 'POST', body }),
  academicTextbook: () => request('/portal/academic/textbook'),
  academicTextbookSign: (recordId) =>
    request(`/portal/academic/textbook/${encodeURIComponent(recordId)}/sign`, { method: 'POST' }),
  academicLevelExam: () => request('/portal/academic/level-exam'),
  academicLevelRegister: (examId) =>
    request(`/portal/academic/level-exam/${encodeURIComponent(examId)}/register`, { method: 'POST' }),
  academicLevelCancel: (examId) =>
    request(`/portal/academic/level-exam/${encodeURIComponent(examId)}/cancel`, { method: 'POST' }),
  academicMajorSplit: () => request('/portal/academic/major-split'),
  academicMajorSplitSubmit: (body) => request('/portal/academic/major-split/submit', { method: 'POST', body }),
  academicCredits: () => request('/portal/academic/credits'),
  academicWarning: () => request('/portal/academic/warning'),
  academicRecognition: () => request('/portal/academic/recognition'),
  academicRecognitionSubmit: (body) => request('/portal/academic/recognition', { method: 'POST', body }),

  // ── 学工事务（在校服务）──
  affairsOverview: () => request('/portal/affairs/overview'),
  affairsLeave: () => request('/portal/affairs/leave'),
  affairsLeaveResubmit: (leaveId, body = {}) =>
    request(`/portal/affairs/leave/${encodeURIComponent(leaveId)}/resubmit`, { method: 'POST', body }),
  affairsLeaveCancel: (leaveId, body = {}) =>
    request(`/portal/affairs/leave/${encodeURIComponent(leaveId)}/cancel`, { method: 'POST', body }),
  affairsLeaveExtend: (leaveId, body = {}) =>
    request(`/portal/affairs/leave/${encodeURIComponent(leaveId)}/extension`, { method: 'POST', body }),
  affairsDorm: () => request('/portal/affairs/dorm'),
  affairsTalk: () => request('/portal/affairs/talk'),
  affairsFunding: () => request('/portal/affairs/funding'),
  affairsAid: () => request('/portal/affairs/aid'),
  affairsDiscipline: () => request('/portal/affairs/discipline'),
  affairsApplications: () => request('/portal/affairs/applications'),
  affairsServiceApply: (body) => request('/portal/affairs/service-apply', { method: 'POST', body }),
  affairsPrint: (body) => request('/portal/affairs/print', { method: 'POST', body }),
  affairsPsyQuestions: () => request('/portal/affairs/psy/questions'),
  affairsPsySubmit: (body) => request('/portal/affairs/psy/submit', { method: 'POST', body }),
  affairsPsyHistory: () => request('/portal/affairs/psy/history'),
  affairsDisciplineAppeal: (body) => request('/portal/affairs/discipline/appeal', { method: 'POST', body }),
  affairsFundingBatches: () => request('/portal/affairs/funding/batches'),
  affairsFundingApply: (body) => request('/portal/affairs/funding/apply', { method: 'POST', body }),
  affairsFundingAppeal: (body) => request('/portal/affairs/funding/appeal', { method: 'POST', body }),
  affairsAidBatches: () => request('/portal/affairs/aid/batches'),
  affairsAidApply: (body) => request('/portal/affairs/aid/apply', { method: 'POST', body }),
  affairsAidObjection: (body) => request('/portal/affairs/aid/objection', { method: 'POST', body }),
  affairsActivities: (page = 1, pageSize = 20) => request(`/portal/affairs/activities${q({ page, pageSize })}`),
  affairsActivitiesMy: () => request('/portal/affairs/activities/my'),
  affairsActivityEnroll: (activityId) =>
    request(`/portal/affairs/activities/${encodeURIComponent(activityId)}/enroll`, { method: 'POST' }),

  // ── 岗位实习 ──
  internshipMy: () => request('/portal/internship/my'),
  internshipWeeklySubmit: (body) => request('/portal/internship/weekly/submit', { method: 'POST', body }),
  internshipReportSubmit: (body) => request('/portal/internship/report/submit', { method: 'POST', body }),
  internshipAgreementPrint: (body) => request('/portal/internship/agreement/print', { method: 'POST', body }),
  internshipScoreAppeal: (body) => request('/portal/internship/score/appeal', { method: 'POST', body }),
  internshipLeaves: () => request('/portal/internship/leaves'),
  internshipLeaveApply: (body) => request('/portal/internship/leaves/apply', { method: 'POST', body }),
  internshipLeaveReturn: (leaveId, body) =>
    request(`/portal/internship/leaves/${encodeURIComponent(leaveId)}/return`, { method: 'POST', body }),
  internshipLeaveWithdraw: (leaveId) =>
    request(`/portal/internship/leaves/${encodeURIComponent(leaveId)}/withdraw`, { method: 'POST' }),
  internshipCheckin: (body) => request('/portal/internship/checkin', { method: 'POST', body }),
  internshipSelfEval: (body) => request('/portal/internship/self-eval', { method: 'POST', body }),
  internshipMakeupApply: (body) => request('/portal/internship/makeup', { method: 'POST', body }),
  internshipMakeups: () => request('/portal/internship/makeup'),
  internshipMakeupWithdraw: (id) =>
    request(`/portal/internship/makeup/${encodeURIComponent(id)}/withdraw`, { method: 'POST' }),
  internshipIntentionMy: () => request('/portal/internship/intention'),
  internshipIntentionSave: (body) => request('/portal/internship/intention', { method: 'POST', body }),
  internshipIntentionSubmit: () => request('/portal/internship/intention/submit', { method: 'POST' }),
  internshipIntentionWithdraw: () => request('/portal/internship/intention/withdraw', { method: 'POST' }),
  internshipApplications: () => request('/portal/internship/applications'),
  internshipApplicationSubmit: (body) => request('/portal/internship/applications', { method: 'POST', body }),
  internshipChangeApply: (body) => request('/portal/internship/change', { method: 'POST', body }),
  internshipChanges: () => request('/portal/internship/change'),
  internshipAgreements: () => request('/portal/internship/agreements'),
  internshipAgreementDetail: (id) => request(`/portal/internship/agreements/${encodeURIComponent(id)}`),
  internshipAgreementConfirm: (id, body) =>
    request(`/portal/internship/agreements/${encodeURIComponent(id)}/confirm`, { method: 'POST', body }),
  internshipInsurance: () => request('/portal/internship/insurance'),
  internshipInsuranceSave: (body) => request('/portal/internship/insurance', { method: 'POST', body }),
  internshipPlan: () => request('/portal/internship/plan'),
  internshipPlanAck: () => request('/portal/internship/plan/acknowledge', { method: 'POST' }),
  internshipEnterprises: (city = '') =>
    request(`/portal/internship/enterprises${city ? `?city=${encodeURIComponent(city)}` : ''}`),

  // ── 就业服务 ──
  employmentMy: () => request('/portal/employment/my'),
  employmentDestination: (body) => request('/portal/employment/destination', { method: 'POST', body }),
  employmentDestinationPrint: (body) => request('/portal/employment/destination/print', { method: 'POST', body }),

  // ── 迎新报到 ──
  orientationMy: () => request('/portal/orientation/my'),
  orientationCollect: (body) => request('/portal/orientation/collect', { method: 'POST', body }),
  orientationGreenChannel: (body) => request('/portal/orientation/green-channel', { method: 'POST', body }),
  orientationPrint: (body) => request('/portal/orientation/print', { method: 'POST', body }),

  // ── 办事大厅 ──
  serviceHallCatalog: () => request('/portal/service-hall/catalog'),

  // ── 消息中心（PC 分页 + 已读 + 偏好）──
  messagesInbox: (page = 1, pageSize = 20) => request(`/portal/messages${q({ page, pageSize })}`),
  messageRead: (messageId) => request(`/portal/messages/${encodeURIComponent(messageId)}/read`, { method: 'POST' }),
  messagePreferences: () => request('/portal/messages/preferences'),
  messageSetPreference: (body) => request('/portal/messages/preferences', { method: 'POST', body }),

  // ── PC 重活公共底座：电子签署 + 打印/导出留痕 ──
  commonSign: (body) => request('/portal/common/sign', { method: 'POST', body }),
  commonPrintLog: (body) => request('/portal/common/print-log', { method: 'POST', body }),
  commonExportLog: (body) => request('/portal/common/export-log', { method: 'POST', body }),

  // ── 毕业设计学生工作台（PC 签署/成绩走 portal；过程读写走 mobile 本人接口）──
  graduationTaskbook: () => request('/portal/graduation/taskbook'),
  signGraduationTaskbook: () => request('/portal/graduation/taskbook/sign', { method: 'POST', body: { confirm: true } }),
  graduationProposal: () => request('/portal/graduation/proposal'),
  submitGraduationProposal: (body) => request('/portal/graduation/proposal/submit', { method: 'POST', body }),
  graduationMidterm: () => request('/portal/graduation/midterm'),
  rectifyGraduationMidterm: (content) => request('/portal/graduation/midterm/rectify', { method: 'POST', body: { content } }),
  graduationFinal: () => request('/portal/graduation/final'),
  submitGraduationFinal: (body) => request('/portal/graduation/final/submit', { method: 'POST', body }),
  graduationDefense: () => request('/portal/graduation/defense'),
  graduationGrade: () => request('/portal/graduation/grade'),
  graduationGradeAppeal: (reason) => request('/portal/graduation/grade/appeal', { method: 'POST', body: { reason } }),
  graduationPeerTasks: () => request('/mobile/graduation/peer-tasks'),
  submitGraduationPeer: (pid, opinion) => request(`/mobile/graduation/peer/${encodeURIComponent(pid)}/submit`, { method: 'POST', body: { opinion } }),
  rectifyGraduationPeer: (pid, note) => request(`/mobile/graduation/peer/${encodeURIComponent(pid)}/rectify`, { method: 'POST', body: { note } }),
  graduationArchive: () => request('/mobile/graduation/archive'),
  graduationActiveRound: () => request('/mobile/graduation/active-round'),
  graduationTopics: (batchId) => request(`/mobile/graduation/topics${batchId ? `?batchId=${encodeURIComponent(batchId)}` : ''}`),
  submitGraduationChoices: (roundId, choices) => request('/mobile/graduation/choices', { method: 'POST', body: { roundId, choices } }),
  withdrawGraduationChoices: (roundId) => request('/mobile/graduation/withdraw-choices', { method: 'POST', body: { roundId } }),
  requestGraduationTopicChange: (newTopicId, reason) => request('/mobile/graduation/change-request', { method: 'POST', body: { newTopicId, reason } }),
  graduationChangeRequests: () => request('/mobile/graduation/change-requests/my'),
  uploadGraduationMaterial: (file) => uploadFile('/files/upload?bizType=GRADUATION_MATERIAL', file),
  downloadGraduationMaterial: (fileId, fileName) => downloadFile(`/mobile/graduation/materials/${encodeURIComponent(fileId)}/download`, fileName)
}

export default portalApi
