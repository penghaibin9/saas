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
  login: (loginName, password) =>
    request('/auth/login', { method: 'POST', auth: false, body: { loginName, password } }),
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
  academicCourseSelection: (batchId) => request(`/portal/academic/course-selection${q({ batchId })}`),
  academicEnroll: (body) => request('/portal/academic/course-selection/enroll', { method: 'POST', body }),
  academicDrop: (body) => request('/portal/academic/course-selection/drop', { method: 'POST', body }),
  academicSelectionRecords: (batchId) => request(`/portal/academic/course-selection/records${q({ batchId })}`),
  academicStatus: () => request('/portal/academic/status'),
  academicStatusChange: (body) => request('/portal/academic/status-change', { method: 'POST', body }),
  academicStatusChangePrint: (body) => request('/portal/academic/status-change/print', { method: 'POST', body }),
  academicExam: () => request('/portal/academic/exam'),
  academicExamDefer: (status) => request(`/portal/academic/exam/defer${q({ status })}`),
  academicExamDeferApply: (body) => request('/portal/academic/exam/defer/apply', { method: 'POST', body }),
  academicMakeup: () => request('/portal/academic/makeup'),
  academicRetakeApply: (body) => request('/portal/academic/retake/apply', { method: 'POST', body }),
  academicGraduationAudit: () => request('/portal/academic/graduation-audit'),

  // ── 学工事务（在校服务）──
  affairsOverview: () => request('/portal/affairs/overview'),
  affairsLeave: () => request('/portal/affairs/leave'),
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
  affairsFundingApply: (body) => request('/portal/affairs/funding/apply', { method: 'POST', body }),
  affairsAidApply: (body) => request('/portal/affairs/aid/apply', { method: 'POST', body }),
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

  // ── 毕业设计学生工作台（沿用 /mobile/graduation 本人接口）──
  graduationTaskbook: () => request('/mobile/graduation/taskbook'),
  confirmGraduationTaskbook: () => request('/mobile/graduation/taskbook/confirm', { method: 'POST' }),
  graduationProposal: () => request('/mobile/graduation/proposal'),
  submitGraduationProposal: (body) => request('/mobile/graduation/proposal', { method: 'POST', body }),
  graduationMidterm: () => request('/mobile/graduation/midterm'),
  rectifyGraduationMidterm: (content) => request('/mobile/graduation/midterm/rectify', { method: 'POST', body: { content } }),
  graduationFinal: () => request('/mobile/graduation/final'),
  submitGraduationFinal: (body) => request('/mobile/graduation/final', { method: 'POST', body }),
  graduationDefense: () => request('/mobile/graduation/defense'),
  graduationGrade: () => request('/mobile/graduation/grade'),
  graduationArchive: () => request('/mobile/graduation/archive'),
  graduationActiveRound: () => request('/mobile/graduation/active-round'),
  graduationTopics: (batchId) => request(`/mobile/graduation/topics${batchId ? `?batchId=${encodeURIComponent(batchId)}` : ''}`),
  submitGraduationChoices: (roundId, choices) => request('/mobile/graduation/choices', { method: 'POST', body: { roundId, choices } }),
  uploadGraduationMaterial: (file) => uploadFile('/files/upload?bizType=GRADUATION_MATERIAL', file),
  downloadGraduationMaterial: (fileId, fileName) => downloadFile(`/mobile/graduation/materials/${encodeURIComponent(fileId)}/download`, fileName)
}

export default portalApi
