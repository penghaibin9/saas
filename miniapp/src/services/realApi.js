/**
 * P3 · 真实后端适配层：字段映射为各 mock 契约形状，页面零结构改动。
 * 全部经 realFirst() 使用：后端挂了自动回退 mock。
 */
import { ENV } from '@/config/env'
import { realRequest, setRefreshToken, setToken } from './request'

/* 小程序角色 key → 正式演示租户真实账号（demo-school，数据只读，行级隔离）。
 * P12：演示/体验全部走真实 /api/v1/auth/login，不再调用 /auth/mock-login。 */
function _holdLogin(data) {
  setToken(data.accessToken)
  setRefreshToken(data.refreshToken || '')
  return data
}

export const switchRoleReal = (contextId, clientType = 'MP') =>
  realRequest('/auth/switch-role', { method: 'POST', data: { contextId, clientType } }).then(_holdLogin)

export const brand = () => realRequest('/tenant/brand')
export const me = () => realRequest('/auth/me')
export const changePassword = (oldPassword, newPassword) =>
  realRequest('/auth/change-password', { method: 'POST', data: { oldPassword, newPassword } })

/* 真实 t_student_profile.current_stage 枚举（backend/app/services/stats_service.py
 * _STAGE_WEIGHT 同一套口径），此前这里写的是 ORIENTATION/ON_CAMPUS/INTERNSHIP/
 * GRADUATION_DESIGN/EMPLOYMENT——和真实枚举完全对不上，STAGE_TEXT[d.stage] 永远
 * undefined，页面「学籍阶段」一直静默兜底显示 mock 的默认值「在校」，从未真正生效过。 */
const STAGE_TEXT = {
  ADMITTED: '录取', PRE_STUDENT_VERIFIED: '预备生', REGISTERED_PENDING_ENROLLMENT: '待注册',
  ENROLLED: '在校', INTERN: '实习', GRADUATING: '毕业年级', GRADUATED: '已毕业', ALUMNI: '校友'
}

/* P10：已彻底移除对 PC 管理端全量接口（/students、/students/{id}、/approvals/tasks 列表、
 * /todos、/messages）的调用。教师端一律走 /mobile/teacher/*（范围过滤 + 权限校验）。 */

/** 审批操作：approve / reject / return（return 映射为 reject，原因必填）。
 * P10：改走 /mobile/teacher/approvals/*（后端做教师校验 + 范围校验 + 审计 + 409 冲突）。 */
export function actApproval(id, type, reason) {
  if (type === 'approve') {
    return realRequest(`/mobile/teacher/approvals/${id}/approve`,
      { method: 'POST', data: { comment: reason || '' } })
  }
  return realRequest(`/mobile/teacher/approvals/${id}/reject`, {
    method: 'POST',
    data: { reason: reason && reason.trim().length >= 5 ? reason : '移动端驳回（未填详细原因）' }
  })
}

/* ══════════ P10 · 教师端写操作（mobile 范围接口，真实落库+审计） ══════════ */

/** 实习周报批阅：action=APPROVE/RETURN（退回需 comment ≥5 字） */
export const reviewWeeklyReal = (reportId, action, comment) =>
  realRequest(`/mobile/teacher/internship/weekly/${reportId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 毕设开题批阅：action=APPROVE/REJECT（驳回需 comment ≥5 字） */
export const reviewProposalReal = (proposalId, action, comment) =>
  realRequest(`/mobile/teacher/graduation/proposal/${proposalId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 打卡异常处理：action=REASONABLE/ABNORMAL/TO_RISK（意见 ≥5 字） */
export const handleCheckinReal = (exceptionId, action, comment) =>
  realRequest(`/mobile/teacher/internship/exception/${exceptionId}/handle`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 学业预警处理：action=CLOSE/ESCALATE（说明 ≥5 字） */
export const handleWarningReal = (warningId, action, note) =>
  realRequest(`/mobile/teacher/academic/warning/${warningId}/handle`,
    { method: 'POST', data: { action, note: note || '' } })

/** 就业跟进记录（真实落库） */
export const createFollowupReal = (body) =>
  realRequest('/mobile/teacher/employment/followup', { method: 'POST', data: body })

/** 学生首页：真实阶段 / 待办 / 通知 / 未读数 / 阻断全部覆盖 mock 骨架，不再展示假数量。
 * 今日课程、快捷服务入口暂无对应真实数据源，保留 mock 骨架（P13 夜间补强已知欠账，见施工记录）。 */
export async function enrichHome(mockHome) {
  const ov = await realRequest('/mobile/home')
  const stu = (ov && ov.student) || {}
  if (stu.stage && mockHome.stageCard) {
    mockHome.stageCard.stageText = STAGE_TEXT[stu.stage] || mockHome.stageCard.stageText
    mockHome.stageCard.title = `你正处于「${mockHome.stageCard.stageText}」阶段`
  }
  if (ov && Array.isArray(ov.todos)) {
    mockHome.todos = ov.todos.map((t) => ({
      id: t.id, title: t.title, module: t.module || t.type || '待办',
      deadline: t.dueAt || '', status: 'PENDING_HANDLE'
    }))
    if (mockHome.todoOverview) mockHome.todoOverview.pending = ov.todos.length
  }
  if (ov && Array.isArray(ov.notices)) {
    mockHome.notices = ov.notices.map((n) => ({
      id: n.id, title: n.title, source: n.source || '校园通知', important: !!n.important
    }))
  }
  if (ov && Array.isArray(ov.alerts)) {
    mockHome.blockers = ov.alerts.map((a, i) => ({
      id: a.domain || ('alert' + i), title: a.title, reason: a.title, solveText: '去处理', level: a.level
    }))
  }
  if (ov && typeof ov.unreadCount === 'number') {
    mockHome.metrics = mockHome.metrics || {}
    mockHome.metrics.unread = ov.unreadCount
  }
  mockHome.realApi = true
  mockHome.orientation = (ov && ov.orientation) || null
  mockHome.orientationBatch = (ov && ov.orientationBatch) || { open: false, daysLeft: 0 }
  return mockHome
}

/* ══════════ 移动端·学生自视图（mobile/<域>/my）字段适配 ══════════
 * 策略：真实数据覆盖到 mock 骨架的主展示字段，保证页面不破；hasData=false 时保留 mock 骨架。
 * 敏感信息（处分/心理）后端已只回摘要状态，不回明细。
 */
export const mobileOverview = () => realRequest('/mobile/me/overview')

export async function enrichOrientation(mock) {
  const r = await realRequest('/mobile/orientation/my')
  if (!r || !r.hasData) return { ...mock, _real: false }
  const stMap = { NOT_REPORTED: '未报到', PREPARED: '预报到完成', CHECKED_IN: '已现场报到',
    COLLEGE_CONFIRMED: '学院已确认' }
  return { ...mock, overallStatus: r.reportStatus, overallText: stMap[r.reportStatus] || mock.overallText,
    dorm: { building: r.building, room: r.room, status: r.dormStatus },
    payStatus: r.paymentStatus, materialStatus: r.materialStatus, greenChannelStatus: r.greenChannelStatus,
    blocked: r.blockedStep ? { step: r.blockedStep, reason: r.blockedReason } : null,
    steps: (r.steps && r.steps.length) ? r.steps.map((s) => ({ key: s.key, status: s.status })) : mock.steps,
    reportCode: { code: r.admissionNo || (mock.reportCode && mock.reportCode.code) || '',
      valid: !!r.reportCodeValid, note: r.reportCodeValid ? '现场核验时出示' : '已完成现场报到，二维码已失效' },
    identity: { name: r.name || '', gender: r.gender || '', collegeName: r.collegeName || '',
      majorName: r.majorName || '', className: r.className || '', grade: r.grade || '',
      origin: r.origin || '', phoneMasked: r.phoneMasked || '' },
    _real: true }
}

/** 迎新批次开放状态（公开·登录前可查，登录页限时入口倒计时用） */
export const orientationBatchStatus = () =>
  realRequest('/mobile/orientation/batch-status', { auth: false })

/** 预报到信息采集 / 绿色通道申请（本人提交，业务错误透出不兜底） */
export const orientationCollectSubmit = (body) =>
  realRequest('/mobile/orientation/collect', { method: 'POST', data: body || {} })
export const orientationGreenChannelSubmit = (body) =>
  realRequest('/mobile/orientation/green-channel', { method: 'POST', data: body })

/** 迎新老师·现场报到核验 / 今日已核验列表 */
export const teacherOrientationCheckin = (admissionNo) =>
  realRequest('/mobile/teacher/orientation/checkin', { method: 'POST', data: { admissionNo } })
export const teacherOrientationTodayCheckins = () =>
  realRequest('/mobile/teacher/orientation/today-checkins')
export const teacherOrientationDashboard = () =>
  realRequest('/mobile/teacher/orientation/dashboard')

/** 指导巡访·本月巡访计划学生列表 / 记录巡访 */
export const teacherInternshipVisitPlans = () => realRequest('/mobile/teacher/internship/visit-plans')
export const teacherInternshipVisitRecord = (internshipId) =>
  realRequest('/mobile/teacher/internship/visit-plans/record', { method: 'POST', data: { internshipId } })

/** 补卡审批·待处理队列 / 审批（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherMakeupPending = () => realRequest('/mobile/teacher/internship/makeups/pending')
export const teacherMakeupReview = (makeupId, action, comment) =>
  realRequest(`/mobile/teacher/internship/makeups/${makeupId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 实习请假审批·待处理队列 / 审批（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherLeavePending = () => realRequest('/mobile/teacher/internship/leaves/pending')
export const teacherLeaveReview = (leaveId, action, comment) =>
  realRequest(`/mobile/teacher/internship/leaves/${leaveId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })
export const teacherLeaveOverdue = () => realRequest('/mobile/teacher/internship/leaves/overdue')
export const teacherLeaveAckReturn = (leaveId, note) =>
  realRequest(`/mobile/teacher/internship/leaves/${leaveId}/ack-return`,
    { method: 'POST', data: { note: note || '' } })
export const teacherInternshipRisks = () => realRequest('/mobile/teacher/internship/risks')
export const teacherInternshipRiskHandle = (riskId, body) =>
  realRequest(`/mobile/teacher/internship/risks/${riskId}/handle`, { method: 'POST', data: body || {} })
export const teacherInternshipRiskFollow = (riskId, note) =>
  realRequest(`/mobile/teacher/internship/risks/${riskId}/follow`, { method: 'POST', data: { note } })
export const teacherInternshipRiskClose = (riskId, body) =>
  realRequest(`/mobile/teacher/internship/risks/${riskId}/close`, { method: 'POST', data: body || {} })

/** 指导教师·本人指导实习学生名单（供新增指导记录选学生用） / 新增指导记录（owner 校验，真实接口，无 mock 兜底） */
export const teacherInternshipMyStudents = () => realRequest('/mobile/teacher/internship/my-students')
export const teacherInternshipGuidanceCreate = (body) =>
  realRequest('/mobile/teacher/internship/guidance', { method: 'POST', data: body })

/** 学生实习鉴定：指导教师队列 / 详情 / 填写意见 / 审核（APPROVE/RETURN，owner 校验，真实接口，无 mock 兜底） */
export const teacherStudentEvalPending = () => realRequest('/mobile/teacher/internship/student-evals')
export const teacherStudentEvalDetail = (evalId) => realRequest(`/mobile/teacher/internship/student-evals/${evalId}`)
export const teacherStudentEvalAdvisorComment = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/student-evals/${evalId}/advisor-comment`, { method: 'POST', data: body })
export const teacherStudentEvalReview = (evalId, action, comment) =>
  realRequest(`/mobile/teacher/internship/student-evals/${evalId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 企业评价：教师端列表 / 录入(五维评分) / 审核（APPROVE/RETURN，owner 校验，真实接口，无 mock 兜底） */
export const teacherEnterpriseEvalPending = () => realRequest('/mobile/teacher/internship/enterprise-evals')
export const teacherEnterpriseEvalCreate = (body) =>
  realRequest('/mobile/teacher/internship/enterprise-evals', { method: 'POST', data: body })
export const teacherEnterpriseEvalReview = (evalId, action, comment) =>
  realRequest(`/mobile/teacher/internship/enterprise-evals/${evalId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 实习保险·待核验队列 / 核验（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherInsurancePending = () => realRequest('/mobile/teacher/internship/insurances/pending')
export const teacherInsuranceVerify = (insuranceId, action, comment) =>
  realRequest(`/mobile/teacher/internship/insurances/${insuranceId}/verify`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 调岗/退岗初审：待处理队列 / 审核（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherInternshipChangePending = () => realRequest('/mobile/teacher/internship/change-requests/pending')
export const teacherInternshipChangeReview = (changeId, action, comment) =>
  realRequest(`/mobile/teacher/internship/change-requests/${changeId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 实习成绩：教师端列表 / 核算(五项加权) / 发布（owner 校验，真实接口，无 mock 兜底） */
export const teacherInternshipScoreList = () => realRequest('/mobile/teacher/internship/scores')
export const teacherInternshipScoreCompute = (body) =>
  realRequest('/mobile/teacher/internship/scores/compute', { method: 'POST', data: body })
export const teacherInternshipScorePublish = (scoreId) =>
  realRequest(`/mobile/teacher/internship/scores/${scoreId}/publish`, { method: 'POST' })

/** 三方协议：待学校确认队列 / 学校确认生效（owner 校验，真实接口，无 mock 兜底） */
export const teacherAgreementPendingSchool = () => realRequest('/mobile/teacher/internship/agreements/pending-school')
export const teacherAgreementSchoolConfirm = (agreementId) =>
  realRequest(`/mobile/teacher/internship/agreements/${agreementId}/school-confirm`, { method: 'POST' })

/** 过程报告(日报/月报/总结)：教师端待批阅队列 / 详情 / 批阅（APPROVE/RETURN，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherProcessReportPending = () => realRequest('/mobile/teacher/internship/process-reports')
export const teacherProcessReportDetail = (reportId) => realRequest(`/mobile/teacher/internship/process-reports/${reportId}`)
export const teacherProcessReportReview = (reportId, action, comment) =>
  realRequest(`/mobile/teacher/internship/process-reports/${reportId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 实习计划任务完成度：教师端待确认队列 / 确认（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherPlanTaskPending = () => realRequest('/mobile/teacher/internship/plan-tasks/pending')
export const teacherPlanTaskReview = (progressId, action, comment) =>
  realRequest(`/mobile/teacher/internship/plan-tasks/${progressId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 实习申请：教师端待审核队列 / 审核（APPROVE/REJECT，owner+范围校验，真实接口，无 mock 兜底） */
export const teacherInternshipApplicationPending = () => realRequest('/mobile/teacher/internship/applications/pending')
export const teacherInternshipApplicationReview = (applicationId, action, comment) =>
  realRequest(`/mobile/teacher/internship/applications/${applicationId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 毕设任务书：教师端列表 / 下达 / 变更（owner 校验，真实接口，无 mock 兜底） */
export const teacherGraduationTaskbookList = () => realRequest('/mobile/teacher/graduation/taskbooks')
export const teacherGraduationTaskbookIssue = (gdStudentId, body) =>
  realRequest(`/mobile/teacher/graduation/taskbooks/${gdStudentId}/issue`, { method: 'POST', data: body })
export const teacherGraduationTaskbookChange = (gdStudentId, body) =>
  realRequest(`/mobile/teacher/graduation/taskbooks/${gdStudentId}/change`, { method: 'POST', data: body })

/** 答辩评委·本人待评分学生名单 / 录入评分（judgeName 服务端强制取当前登录人，真实接口，无 mock 兜底） */
export const teacherGraduationDefenseScorePending = () => realRequest('/mobile/teacher/graduation/defense/pending')
export const teacherGraduationDefenseScoreEntry = (gdStudentId, body) =>
  realRequest(`/mobile/teacher/graduation/defense/${gdStudentId}/score`, { method: 'POST', data: body })

/** 家校联系：可登记学生名单 / 记录列表 / 登记联系 / 登记回执（owner+范围校验，真实接口，无 mock 兜底） */
export const teacherFamilyContactStudents = () => realRequest('/mobile/teacher/affairs/family-contacts/students')
export const teacherFamilyContactList = (receiptStatus) =>
  realRequest('/mobile/teacher/affairs/family-contacts' + (receiptStatus ? `?receiptStatus=${receiptStatus}` : ''))
export const teacherFamilyContactCreate = (studentId, body) =>
  realRequest(`/mobile/teacher/affairs/family-contacts/${studentId}`, { method: 'POST', data: body })
export const teacherFamilyContactReceipt = (contactId, note) =>
  realRequest(`/mobile/teacher/affairs/family-contacts/${contactId}/receipt`, { method: 'POST', data: { note: note || '' } })

/** 学工请假审批链：待审批队列 / 后续处理台账 / 详情 / 审批通过驳回退回 / 销假确认代登记 /
 * 逾期处置 / 续假审批（owner+审批节点校验，真实接口，无 mock 兜底） */
export const teacherAffairsLeavePending = () => realRequest('/mobile/teacher/affairs/leaves/pending')
export const teacherAffairsLeaveFollowup = () => realRequest('/mobile/teacher/affairs/leaves/followup')
export const teacherAffairsLeaveDetail = (leaveId) => realRequest(`/mobile/teacher/affairs/leaves/${leaveId}`)
export const teacherAffairsLeaveApprove = (leaveId, comment) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/approve`, { method: 'POST', data: { comment: comment || '' } })
export const teacherAffairsLeaveReject = (leaveId, reason) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/reject`, { method: 'POST', data: { reason } })
export const teacherAffairsLeaveReturn = (leaveId, reason) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/return`, { method: 'POST', data: { reason } })
export const teacherAffairsLeaveCancelConfirm = (leaveId, action, body) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/cancel-confirm`,
    { method: 'POST', data: { action, ...(body || {}) } })
export const teacherAffairsLeaveProxyCancel = (leaveId, actualReturnAt, note) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/proxy-cancel`,
    { method: 'POST', data: { actualReturnAt, note: note || '' } })
export const teacherAffairsLeaveOverdueHandle = (leaveId, handleType, note) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/overdue-handle`,
    { method: 'POST', data: { handleType, note } })
export const teacherAffairsLeaveExtensionApprove = (leaveId, action, reason) =>
  realRequest(`/mobile/teacher/affairs/leaves/${leaveId}/extension-approve`,
    { method: 'POST', data: { action, reason: reason || '' } })

/** 学工待办处置：困难/奖助/处分/风险（复用 PC 服务层校验，真实接口） */
export const teacherAffairsAidPending = () => realRequest('/mobile/teacher/affairs/aid/pending')
export const teacherAffairsAidDetail = (applyId) => realRequest(`/mobile/teacher/affairs/aid/${applyId}`)
export const teacherAffairsAidReview = (applyId, body) =>
  realRequest(`/mobile/teacher/affairs/aid/${applyId}/review`, { method: 'POST', data: body || {} })
export const teacherAffairsFundingPending = () => realRequest('/mobile/teacher/affairs/funding/pending')
export const teacherAffairsFundingDetail = (appId) => realRequest(`/mobile/teacher/affairs/funding/${appId}`)
export const teacherAffairsFundingReview = (appId, body) =>
  realRequest(`/mobile/teacher/affairs/funding/${appId}/review`, { method: 'POST', data: body || {} })
export const teacherAffairsDisciplinePending = () => realRequest('/mobile/teacher/affairs/discipline/pending')
export const teacherAffairsDisciplineDetail = (caseId) => realRequest(`/mobile/teacher/affairs/discipline/${caseId}`)
export const teacherAffairsDisciplineReview = (caseId, body) =>
  realRequest(`/mobile/teacher/affairs/discipline/${caseId}/review`, { method: 'POST', data: body || {} })
export const teacherAffairsRiskPending = () => realRequest('/mobile/teacher/affairs/risk/pending')
export const teacherAffairsRiskDetail = (riskId) => realRequest(`/mobile/teacher/affairs/risk/${riskId}`)
export const teacherAffairsRiskProcess = (riskId, content) =>
  realRequest(`/mobile/teacher/affairs/risk/${riskId}/process`, { method: 'POST', data: { content } })
export const teacherAffairsRiskClose = (riskId, conclusion) =>
  realRequest(`/mobile/teacher/affairs/risk/${riskId}/close`, { method: 'POST', data: { conclusion } })

/** 班干部任命/免去：我的班级 / 班级学生名单 / 班干部名单 / 任命 / 免去
 * （owner+范围校验，真实接口，无 mock 兜底） */
export const teacherAffairsDormPending = () => realRequest('/mobile/teacher/affairs/dorm/pending')
export const teacherAffairsDormTransferReview = (transferId, body) =>
  realRequest(`/mobile/teacher/affairs/dorm/transfers/${transferId}/review`, { method: 'POST', data: body || {} })
export const teacherAffairsDormExceptionHandle = (exceptionId, note) =>
  realRequest(`/mobile/teacher/affairs/dorm/exceptions/${exceptionId}/handle`, { method: 'POST', data: { note } })

export const teacherAffairsMyClasses = () => realRequest('/mobile/teacher/affairs/classes')
export const teacherAffairsClassStudents = (classId) => realRequest(`/mobile/teacher/affairs/classes/${classId}/students`)
export const teacherAffairsCadreList = (classId) => realRequest(`/mobile/teacher/affairs/classes/${classId}/cadres`)
export const teacherAffairsCadreAppoint = (classId, body) =>
  realRequest(`/mobile/teacher/affairs/classes/${classId}/cadres`, { method: 'POST', data: body })
export const teacherAffairsCadreRemove = (cadreId, reason) =>
  realRequest(`/mobile/teacher/affairs/classes/cadres/${cadreId}/remove`, { method: 'POST', data: { reason: reason || '' } })

export const teacherAffairsClassMaterials = (classId, materialType) =>
  realRequest(`/mobile/teacher/affairs/classes/${classId}/materials`, { data: materialType ? { materialType } : {} })
export const teacherAffairsClassMaterialAdd = (classId, body) =>
  realRequest(`/mobile/teacher/affairs/classes/${classId}/materials`, { method: 'POST', data: body })
export const teacherAffairsClassMaterialVoid = (materialId, reason) =>
  realRequest(`/mobile/teacher/affairs/classes/materials/${materialId}/void`, { method: 'POST', data: { reason: reason || '' } })

export const teacherAcademicMyTasks = (status) =>
  realRequest('/mobile/teacher/academic/tasks', { data: status ? { status } : {} })
export const teacherAcademicTaskAct = (taskId, action, reason) =>
  realRequest(`/mobile/teacher/academic/tasks/${taskId}/act`, { method: 'POST', data: { action, reason: reason || '' } })

export const teacherAcademicMySchedule = (termId, week) =>
  realRequest('/mobile/teacher/academic/schedule/mine', { data: { termId: termId || '', week: week || '' } })
export const teacherAcademicScheduleConflictCheck = (body) =>
  realRequest('/mobile/teacher/academic/schedule-changes/conflict-check', { method: 'POST', data: body })
export const teacherAcademicScheduleSubmit = (body) =>
  realRequest('/mobile/teacher/academic/schedule-changes', { method: 'POST', data: body })
export const teacherAcademicScheduleChanges = (status) =>
  realRequest('/mobile/teacher/academic/schedule-changes', { data: status ? { status } : {} })
export const teacherAcademicScheduleChangeDetail = (changeId) =>
  realRequest(`/mobile/teacher/academic/schedule-changes/${changeId}`)
export const teacherAcademicScheduleCancel = (changeId, reason) =>
  realRequest(`/mobile/teacher/academic/schedule-changes/${changeId}/cancel`, { method: 'POST', data: { reason: reason || '' } })

export const teacherAcademicDeferPending = () => realRequest('/mobile/teacher/academic/defer/pending')
export const teacherAcademicDeferReview = (deferId, action, reason) =>
  realRequest(`/mobile/teacher/academic/defer/${deferId}/review`, { method: 'POST', data: { action, reason: reason || '' } })

export const teacherAcademicEvaluationBatches = () => realRequest('/mobile/teacher/academic/evaluation/batches')
export const teacherAcademicEvaluationMyTasks = (evaluatorType, batchId) =>
  realRequest('/mobile/teacher/academic/evaluation/tasks', { data: { evaluatorType, batchId: batchId || '' } })
export const teacherAcademicEvaluationSubmit = (taskId, body) =>
  realRequest(`/mobile/teacher/academic/evaluation/tasks/${taskId}/submit`, { method: 'POST', data: body })
export const teacherAcademicEvaluationResults = () => realRequest('/mobile/teacher/academic/evaluation/results')
export const teacherAcademicEvaluationAppeal = (resultId, reason) =>
  realRequest(`/mobile/teacher/academic/evaluation/results/${resultId}/appeal`, { method: 'POST', data: { reason } })

export const teacherEmploymentMyStudents = () => realRequest('/mobile/teacher/employment/my-students')
export const teacherEmploymentTransferStudent = (studentId, newTeacher) =>
  realRequest(`/mobile/teacher/employment/students/${studentId}/transfer`, { method: 'POST', data: { newTeacher } })

export const teacherEmploymentCompanies = (status) =>
  realRequest('/mobile/teacher/employment/companies', { data: status ? { status } : {} })
export const teacherEmploymentCompanyCreate = (body) =>
  realRequest('/mobile/teacher/employment/companies', { method: 'POST', data: body })
export const teacherEmploymentCompanyDisable = (companyId, reason) =>
  realRequest(`/mobile/teacher/employment/companies/${companyId}/disable`, { method: 'POST', data: { reason: reason || '' } })
export const teacherEmploymentJobs = (companyId, status) =>
  realRequest('/mobile/teacher/employment/jobs', { data: { companyId: companyId || '', status: status || '' } })
export const teacherEmploymentJobCreate = (body) =>
  realRequest('/mobile/teacher/employment/jobs', { method: 'POST', data: body })
export const teacherEmploymentJobDisable = (jobId, reason) =>
  realRequest(`/mobile/teacher/employment/jobs/${jobId}/disable`, { method: 'POST', data: { reason: reason || '' } })

export async function enrichAcademic(mock) {
  const r = await realRequest('/mobile/academic/my')
  if (!r || !r.hasData) return { ...mock, _real: false }
  const s = r.summary || {}
  return { ...mock,
    summary: { gpa: s.gpa, rank: mock.summary.rank, creditEarned: s.obtainedCredits,
      creditTotal: s.requiredCredits, warning: (s.warningLevel && s.warningLevel !== 'NONE'),
      academicStatus: s.academicStatus, failedCount: s.failedCount },
    courses: (r.grades || []).map((g) => ({ name: g.course, term: g.term, score: g.score,
      pass: g.passStatus === 'PASSED' })),
    warnings: r.warnings || [], _real: true }
}

export async function enrichInternship(_unused) {
  // 禁止网络失败回落 mock 假企业；无档案时仅返回中性空态
  const r = await realRequest('/mobile/internship/my')
  if (!r || !r.hasData) {
    return {
      hasBatch: false,
      _real: false,
      message: (r && r.message) || '暂无实习记录',
      company: '', post: '', schoolMentor: '', companyMentor: '',
      batch: '', timeline: [],
      weekly: { week: '第 1 周', submitted: false, lastFeedback: '' },
      checkin: { done: false, time: '', totalDays: 0, place: '', note: '仅在点击时采集定位，不后台定位' },
      status: {
        todayCheckin: 'PENDING', weekly: 'PENDING_SUBMIT',
        agreement: 'PENDING', insurance: 'PENDING', onboard: 'PENDING', leave: 'NONE'
      }
    }
  }
  const reports = r.weeklyReports || []
  const latest = reports[0]
  let weekNo = 1
  let submitted = false
  let lastFeedback = ''
  if (latest && latest.week != null) {
    const st = latest.status
    lastFeedback = latest.reviewComment || ''
    if (st === 'RETURNED') {
      weekNo = Number(latest.week)
      submitted = false
    } else if (st === 'APPROVED') {
      weekNo = Number(latest.week) + 1
      submitted = false
    } else {
      weekNo = Number(latest.week)
      submitted = ['PENDING_REVIEW', 'APPROVED'].includes(st)
    }
  }
  const place = r.checkinPlace || r.workLocation || r.enterpriseName || '实习地点待定'
  return {
    hasBatch: true,
    batch: r.batchName || '实习批次',
    company: r.enterpriseName || '',
    post: r.positionName || '',
    schoolMentor: r.advisorName || '待分配',
    companyMentor: r.enterpriseMentor || '待分配',
    statusText: r.status || '',
    riskLevel: r.riskLevel || 'NONE',
    weeklyList: reports,
    checkinExceptions: r.attendanceExceptions || [],
    timeline: Array.isArray(r.timeline) ? r.timeline : [],
    _real: true,
    weekly: {
      week: `第 ${weekNo} 周`,
      submitted,
      lastFeedback: lastFeedback || ''
    },
    checkin: {
      done: !!(r.todayCheckin && r.todayCheckin.done),
      time: (r.todayCheckin && r.todayCheckin.time) || '',
      totalDays: (r.todayCheckin && r.todayCheckin.totalDays) || 0,
      place,
      note: '仅在点击时采集定位，不后台定位'
    },
    status: {
      todayCheckin: (r.todayCheckin && r.todayCheckin.done) ? 'COMPLETED' : 'PENDING',
      weekly: submitted ? 'COMPLETED' : 'PENDING_SUBMIT',
      agreement: r.agreementStatus || 'PENDING',
      insurance: r.insuranceStatus || 'PENDING',
      onboard: r.onboardStatus || r.status || 'PENDING',
      leave: r.leaveStatus || 'NONE'
    }
  }
}

/* 毕设阶段 → 当前主任务（真实派生，按钮定位到本页对应真实功能区，不再 toast「请去 PC 端」）。 */
const GD_PRIMARY = {
  TOPIC_SELECTING: { title: '选择课题志愿', desc: '进入选题轮次，从题目库按志愿序提交', actionText: '去选题', anchor: 'topic' },
  TASKBOOK_CONFIRM: { title: '确认任务书', desc: '导师已下达任务书，请核对后确认', actionText: '去确认', anchor: 'taskbook' },
  GUIDING: { title: '提交开题报告', desc: '完成选题后提交开题报告，等待导师审阅', actionText: '去开题', anchor: 'proposal' },
  MIDTERM: { title: '完成中期检查', desc: '如需整改请在中期检查区提交整改内容', actionText: '去中期', anchor: 'midterm' },
  FINAL_CHECK: { title: '提交论文成果', desc: '提交论文初稿/定稿并关注查重结果', actionText: '去成果', anchor: 'final' },
  DEFENSE: { title: '查看答辩安排', desc: '答辩组已编排，发布后可见时间地点评委', actionText: '看答辩', anchor: 'defense' },
  ARCHIVED: { title: '查看毕设成绩', desc: '成绩发布后可查看构成，如有异议可申诉', actionText: '看成绩', anchor: 'grade' }
}

export async function enrichGraduation(_unused) {
  // 禁止网络失败回落 mock 假课题；无档案时仅返回中性空态
  const r = await realRequest('/mobile/graduation/my')
  if (!r || !r.hasData) {
    return {
      hasBatch: false, _real: false,
      message: (r && r.message) || '暂无毕设记录',
      topic: '', mentor: '', stage: '', stageLabel: '', batch: '', batchId: '',
      topicId: '', hasTopic: false, nodes: [], guideLogs: [], proposals: [], finals: [],
      primaryAction: { title: '暂无毕设任务', desc: '进入毕设阶段后这里会显示当前待办', actionText: '查看', anchor: 'nodes' },
      returnedNote: ''
    }
  }
  const primary = GD_PRIMARY[r.stage] || { title: '毕业设计进行中', desc: '按导师指导推进各节点', actionText: '查看', anchor: 'nodes' }
  const hasTopic = r.hasTopic != null ? !!r.hasTopic : !!r.topicId
  return {
    hasBatch: true, _real: true,
    topic: r.topicTitle || '（未选题）',
    mentor: r.advisorName || '（未分配导师）',
    stage: r.stage, stageLabel: r.stageLabel || '',
    defenseGroup: r.defenseGroup, plagiarismRate: r.plagiarismRate,
    topicId: r.topicId || '',
    hasTopic,
    batchId: r.batchId || '',
    batch: r.batchName || r.stageLabel || '',
    nodes: (r.nodes && r.nodes.length) ? r.nodes : [],
    guideLogs: r.guideLogs || [],
    primaryAction: primary,
    returnedNote: '',
    proposals: r.proposals || [], finals: r.finals || []
  }
}

/* ══════════ 选题管理：浏览题目库 / 提交志愿 / 课题变更申请（学生自服务，真实接口，不 mock 冒充） ══════════ */

export const gdTopics = (batchId) => realRequest(
  '/mobile/graduation/topics' + (batchId ? `?batchId=${encodeURIComponent(batchId)}` : '')
)
export const gdActiveRound = () => realRequest('/mobile/graduation/active-round')
export const gdSubmitChoices = (roundId, choices) =>
  realRequest('/mobile/graduation/choices', { method: 'POST', data: { roundId, choices } })
export const gdWithdrawChoices = (roundId) =>
  realRequest('/mobile/graduation/withdraw-choices', { method: 'POST', data: { roundId } })
export const gdRequestChange = (newTopicId, reason) =>
  realRequest('/mobile/graduation/change-request', { method: 'POST', data: { newTopicId, reason } })
export const gdMyChangeRequests = () => realRequest('/mobile/graduation/change-requests/my')

/* ══════════ 过程指导：任务书 / 中期检查 / 成绩（学生自服务，真实接口，不 mock 冒充） ══════════ */

export const gdProposal = () => realRequest('/mobile/graduation/proposal')
export const gdSubmitProposal = (data) =>
  realRequest('/mobile/graduation/proposal', { method: 'POST', data })
export const gdFinal = () => realRequest('/mobile/graduation/final')
export const gdSubmitFinal = (data) =>
  realRequest('/mobile/graduation/final', { method: 'POST', data })
export const gdTaskbook = () => realRequest('/mobile/graduation/taskbook')
export const gdTaskbookConfirm = () => realRequest('/mobile/graduation/taskbook/confirm', { method: 'POST' })
export const gdMidterm = () => realRequest('/mobile/graduation/midterm')
export const gdMidtermRectify = (content) =>
  realRequest('/mobile/graduation/midterm/rectify', { method: 'POST', data: { content } })
export const gdDefense = () => realRequest('/mobile/graduation/defense')
export const gdGradeAppeal = (reason) =>
  realRequest('/mobile/graduation/grade/appeal', { method: 'POST', data: { reason } })
export const gdPeerTasks = () => realRequest('/mobile/graduation/peer-tasks')
export const gdPeerSubmit = (pid, opinion) =>
  realRequest(`/mobile/graduation/peer/${pid}/submit`, { method: 'POST', data: { opinion } })
export const gdPeerRectify = (pid, note) =>
  realRequest(`/mobile/graduation/peer/${pid}/rectify`, { method: 'POST', data: { note } })
export const gdArchive = () => realRequest('/mobile/graduation/archive')
export const gdGrade = () => realRequest('/mobile/graduation/grade')

/* ══════════ 过程指导：教师端本人指导学生 + 快速新增指导记录 ══════════ */

export const gdTeacherMyStudents = () => realRequest('/mobile/teacher/graduation/my-students')
export const gdTeacherGuidanceCreate = (gdStudentId, body) =>
  realRequest(`/mobile/teacher/graduation/${gdStudentId}/guidance`, { method: 'POST', data: body })
/** 教师·开题详情（批阅前真实查看背景/方案/成果 + 历史版本，范围校验，越权 403/不存在 404） */
export const gdTeacherProposalDetail = (proposalId) =>
  realRequest(`/mobile/teacher/graduation/proposal/${proposalId}`)
/** 教师·成果详情 + 批阅（类型/版本/查重/真实附件；查重超标 GD-R09 不可直接通过） */
export const gdTeacherFinalDetail = (finalId) =>
  realRequest(`/mobile/teacher/graduation/final/${finalId}`)
export const gdTeacherFinalReview = (finalId, action, comment) =>
  realRequest(`/mobile/teacher/graduation/final/${finalId}/review`, { method: 'POST', data: { action, comment: comment || '' } })
/** 教师·中期检查：待办队列 / 详情 / 结论 PASS-RECTIFY-FAIL / 复核整改 */
export const gdTeacherMidtermQueue = () => realRequest('/mobile/teacher/graduation/midterm/queue')
export const gdTeacherMidtermDetail = (gdStudentId) => realRequest(`/mobile/teacher/graduation/midterm/${gdStudentId}`)
export const gdTeacherMidtermCheck = (gdStudentId, conclusion, comment, rectifyDeadline) =>
  realRequest(`/mobile/teacher/graduation/midterm/${gdStudentId}/check`,
    { method: 'POST', data: { conclusion, comment: comment || '', rectifyDeadline: rectifyDeadline || '' } })
export const gdTeacherMidtermRectifyReview = (gdStudentId, action, comment) =>
  realRequest(`/mobile/teacher/graduation/midterm/${gdStudentId}/rectify-review`,
    { method: 'POST', data: { action, comment: comment || '' } })
/** 教师·评阅：本人任务 / 提交评分+意见 */
export const gdTeacherReviewsMy = () => realRequest('/mobile/teacher/graduation/reviews/my')
export const gdTeacherReviewSubmit = (reviewId, score, opinion) =>
  realRequest(`/mobile/teacher/graduation/review/${reviewId}/submit`, { method: 'POST', data: { score, opinion: opinion || '' } })
/** 教师·答辩安排（本人指导学生，只读） */
export const gdTeacherDefenseArrangements = () => realRequest('/mobile/teacher/graduation/defense/arrangements')
/** 教师·成绩：待复核队列 / 三段构成详情 / 复核 APPROVE-RETURN */
export const gdTeacherGradeQueue = () => realRequest('/mobile/teacher/graduation/grade/queue')
export const gdTeacherGradeDetail = (gdStudentId) => realRequest(`/mobile/teacher/graduation/grade/${gdStudentId}`)
export const gdTeacherGradeReview = (gdStudentId, action, comment) =>
  realRequest(`/mobile/teacher/graduation/grade/${gdStudentId}/review`, { method: 'POST', data: { action, comment: comment || '' } })

/** 教师·毕设选题志愿确认（本人指导题目下待确认志愿 + CONFIRM/REJECT，范围校验+审计，无 mock 兜底） */
export const gdTeacherChoicesPending = () => realRequest('/mobile/teacher/graduation/choices/pending')
export const gdTeacherChoiceReview = (choiceId, action, reason) =>
  realRequest(`/mobile/teacher/graduation/choices/${choiceId}/review`,
    { method: 'POST', data: { action, reason: reason || '' } })
/** 教师·毕设选题变更审核（与本人相关的待审变更 + APPROVE/REJECT，范围校验+审计，无 mock 兜底） */
export const gdTeacherChangeRequestsPending = () => realRequest('/mobile/teacher/graduation/change-requests/pending')
export const gdTeacherChangeRequestReview = (requestId, action, comment) =>
  realRequest(`/mobile/teacher/graduation/change-requests/${requestId}/review`,
    { method: 'POST', data: { action, comment: comment || '' } })

/** 教师·学工统计（谈话工作量 / 心理关注，仅聚合，真实接口，无 mock 兜底） */
export const teacherTalkStats = () => realRequest('/mobile/teacher/talk-stats')
export const teacherMentalStats = () => realRequest('/mobile/teacher/mental-stats')

/** 教师·在校服务待处理 & 学业预警待处理列表（真实接口，_domain 结构：{hasData,list,total,module}，范围过滤，无 mock 兜底） */
export const teacherCampusServicePending = () => realRequest('/mobile/teacher/campus-service')
export const teacherAcademicWarnings = () => realRequest('/mobile/teacher/academic')

export const employmentMy = () => realRequest('/mobile/employment/my')

export async function enrichCampusService(mock) {
  const r = await realRequest('/mobile/campus-service/my')
  if (!r || !r.hasData) return { ...mock, myRecords: null, _real: false }
  return { ...mock, myRecords: { leaves: r.leaves || [], workOrders: r.workOrders || [],
    disciplineNotice: r.disciplineNotice, mentalNotice: r.mentalNotice }, _real: true }
}

/* 教师端·工作台聚合（本校待办，只读） */
export const mobileTeacherOverview = () => realRequest('/mobile/teacher/overview')
export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')
export const mobileTeacherDomain = (domain) => realRequest('/mobile/teacher/' + domain)

/* 教师工作台：真实待办计数 + 即将超时 + 风险学生覆盖到 mock 骨架，不再展示假名单。
 * 「最近学生动态」暂无对应真实数据源，保留 mock 骨架（P13 夜间补强已知欠账，见施工记录）。 */
export async function enrichTeacherWorkbench(mock) {
  // 三个只读接口互不依赖，并发拉取（校园弱网下由 3 次串行往返降为 1 次并发）。
  // overview 决定主体，失败则由外层 realFirst 兜底；todos/风险学生为增量展示，静默降级。
  const [r, td, rs] = await Promise.all([
    realRequest('/mobile/teacher/overview'),
    realRequest('/mobile/teacher/todos').catch(() => null),
    realRequest('/mobile/teacher/risk-students').catch(() => null)
  ])
  if (!r || !r.hasData) return { ...mock, _real: false }
  const realMetrics = (r.metrics || []).slice(0, 4).map((m) => ({ key: m.key, label: m.label, value: m.value }))
  const out = { ...mock, metrics: realMetrics.length ? realMetrics : mock.metrics,
    pendingTotal: r.pendingTotal, _real: true }
  if (td && Array.isArray(td.list)) {
    out.dueSoon = td.list.slice(0, 5).map((t) => ({
      id: t.id, title: t.title, module: t.module, student: t.student,
      deadline: t.deadline, status: t.status
    }))
  }
  if (rs && Array.isArray(rs.list)) {
    out.riskStudents = rs.list.slice(0, 5).map((s) => ({
      id: s.studentId || s.studentNo || s.id, name: s.name, className: s.className || '—',
      type: s.riskType + (s.reason ? '·' + s.reason : ''), level: s.riskLevel
    }))
  }
  return out
}

/* ══════════ P9.2 · 学生端补齐（档案脱敏 / 本人消息 / 我的申请 / 写操作） ══════════ */

export const submitServiceApply = (body) =>
  realRequest('/mobile/campus-service/apply', { method: 'POST', data: body })

export const submitWeeklyReport = (body) =>
  realRequest('/mobile/internship/weekly', { method: 'POST', data: body })

/** 实习每日打卡（真实落库，一天一次，409=今日已打） */
export const submitCheckin = (body) =>
  realRequest('/mobile/internship/checkin', { method: 'POST', data: body || {} })

/** 本周打卡记录（本人，正常/超范围/缺卡） */
export const internshipCheckinWeek = () => realRequest('/mobile/internship/checkin/week')

/** 企业岗位库（本人可浏览，城市筛选） */
export const internshipEnterprises = (city) =>
  realRequest('/mobile/internship/enterprises' + (city ? `?city=${encodeURIComponent(city)}` : ''))

/** 本人三方协议列表 / 详情 / 确认（含渲染正文，业务错误透出） */
export const internshipAgreements = () => realRequest('/mobile/internship/agreements')
export const internshipAgreementDetail = (id) =>
  realRequest(`/mobile/internship/agreements/${id}`)
export const confirmInternshipAgreement = (id, body) =>
  realRequest(`/mobile/internship/agreements/${id}/confirm`, { method: 'POST', data: body })

export const internshipLeaves = () => realRequest('/mobile/internship/leaves')
export const applyInternshipLeave = (body) =>
  realRequest('/mobile/internship/leave', { method: 'POST', data: body })
export const withdrawInternshipLeave = (id) =>
  realRequest(`/mobile/internship/leave/${id}/withdraw`, { method: 'POST' })
export const returnInternshipLeave = (id, body) =>
  realRequest(`/mobile/internship/leave/${id}/return`, { method: 'POST', data: body || {} })
export const internshipHelpReport = (body) =>
  realRequest('/mobile/internship/help', { method: 'POST', data: body || {} })

export const internshipMakeups = () => realRequest('/mobile/internship/makeup')
export const applyInternshipMakeup = (body) =>
  realRequest('/mobile/internship/makeup', { method: 'POST', data: body })
export const withdrawInternshipMakeup = (id) =>
  realRequest(`/mobile/internship/makeup/${id}/withdraw`, { method: 'POST' })

export const internshipSelfEval = () => realRequest('/mobile/internship/self-eval')
export const submitInternshipSelfEval = (body) =>
  realRequest('/mobile/internship/self-eval', { method: 'POST', data: body })

/** 本人实习意向：查看 / 保存草稿 / 提交 / 撤回 */
export const internshipIntentionMy = () => realRequest('/mobile/internship/intention')
export const saveInternshipIntention = (body) =>
  realRequest('/mobile/internship/intention', { method: 'PUT', data: body })
export const submitInternshipIntention = () =>
  realRequest('/mobile/internship/intention/submit', { method: 'POST' })
export const withdrawInternshipIntention = () =>
  realRequest('/mobile/internship/intention/withdraw', { method: 'POST' })

export const submitProcessReport = (body) =>
  realRequest('/mobile/internship/process-report', { method: 'POST', data: body })

export const internshipChangeRequests = () => realRequest('/mobile/internship/change-requests')

export const applyInternshipChange = (body) =>
  realRequest('/mobile/internship/change-request', { method: 'POST', data: body })

export const withdrawInternshipChange = (id) =>
  realRequest(`/mobile/internship/change-request/${id}/withdraw`, { method: 'POST' })

export const internshipApplications = () => realRequest('/mobile/internship/applications')
export const saveInternshipApplication = (body) =>
  realRequest('/mobile/internship/applications', { method: 'PUT', data: body || {} })
export const submitInternshipApplication = (id) =>
  realRequest(`/mobile/internship/applications/${id}/submit`, { method: 'POST' })
export const withdrawInternshipApplication = (id) =>
  realRequest(`/mobile/internship/applications/${id}/withdraw`, { method: 'POST' })

export const submitInternshipInsurance = (body) =>
  realRequest('/mobile/internship/insurance', { method: 'POST', data: body })

export const internshipPlanMy = () => realRequest('/mobile/internship/plan')
export const ackInternshipPlan = () => realRequest('/mobile/internship/plan/acknowledge', { method: 'POST' })
export const internshipPlanTasksMy = () => realRequest('/mobile/internship/plan/tasks')
export const submitInternshipPlanTask = (sortOrder, body) =>
  realRequest(`/mobile/internship/plan/tasks/${sortOrder}/submit`, { method: 'POST', data: body })
export const internshipInsuranceMy = () => realRequest('/mobile/internship/insurance')
export const signInternshipAgreementEsign = (id) =>
  realRequest(`/mobile/internship/agreements/${id}/esign/sign`, { method: 'POST' })

/** 教师·逾期未交周报催交 */
export const remindWeeklyReal = (reportId) =>
  realRequest(`/mobile/teacher/internship/weekly/${reportId}/remind`, { method: 'POST' })

/** 标记本人消息已读（严格本人校验） */
export const markMessageRead = (id) =>
  realRequest('/mobile/me/messages/' + id + '/read', { method: 'POST' })

/** 学生档案：真实脱敏字段覆盖 mock 骨架（手机/身份证仅脱敏串，住址不返回）。 */
/**
 * ⚠️ 已知未修复缺口（见 2026-07-18 真实交互巡检报告）：p.summaries.{internship,graduation,
 * employment} 完全沿用 mock 的「暂未进入 xx 阶段」文案，从未与真实数据合并——某学生即使已有
 * 真实在岗实习记录（岗位实习页可查真实企业/导师/周报）或真实毕设指导关系（毕业设计页可查真实
 * 指导教师/指导记录），本页仍会显示「暂未进入」。
 * 不能简单用 current_stage 顺序推断是否「已进入」某域：本系统 current_stage 是粗粒度全局阶段
 * （ADMITTED→...→ENROLLED→INTERN→GRADUATING→GRADUATED→ALUMNI），与各业务域（岗位实习/毕业
 * 设计）的真实启动时间并不同步——例如 stage=INTERN 的学生可能已经有真实的毕业设计指导记录
 * （毕设不等 stage 推进到 GRADUATING 才能选题/开题），按 stage 顺序纠正会把这类情况错判为
 * 「未进入」，反而制造新的假结论。正确修法需要后端 my_profile 分别下钻查询
 * InternshipRecord/GraduationStudent/EmpStudent 是否存在真实记录，本次未做（超出前端改动范围）。
 */
export async function enrichProfileReal(mockProfile) {
  const d = await realRequest('/mobile/me/profile')
  if (!d || !d.hasData) {
    // 真实档案无数据时，绝不回落 mock 假档案（假姓名/手机 13612345678/身份证）冒充真人资料。
    // 保留结构、清空敏感字段，标记空态，由页面渲染“暂无档案”而非虚假 PII。
    const empty = JSON.parse(JSON.stringify(mockProfile))
    empty.base = { ...empty.base, name: '', studentNo: '', idCard: '' }
    empty.contact = { ...empty.contact, phone: '', address: '' }
    empty._real = false
    empty._empty = true
    return empty
  }
  const p = JSON.parse(JSON.stringify(mockProfile))
  p.base = { ...p.base, name: d.name, studentNo: d.studentNo,
    gender: d.gender || p.base.gender, idCard: d.idCardMasked || '' }
  p.contact = { ...p.contact, phone: d.phoneMasked || '', address: '' }
  p.org = { ...p.org, college: d.collegeName || p.org.college, major: d.majorName || p.org.major,
    className: d.className || p.org.className, grade: d.grade || p.org.grade }
  p.status = { ...p.status, stageText: STAGE_TEXT[d.stage] || p.status.stageText }
  p._real = true
  p._identity = { studentId: d.studentId, studentNo: d.studentNo, name: d.name }
  return p
}

/** 学生消息（严格本人）→ mock tabs/groups 形状。 */
export async function selfMessages(mock) {
  const d = await realRequest('/mobile/me/messages')
  if (!d) return mock
  const tabs = (d.tabs && d.tabs.length) ? d.tabs : (mock.tabs || [])
  const groups = d.groups || {}
  tabs.forEach((t) => { t.badge = (groups[t.key] || []).filter((x) => !x.read).length })
  return { tabs, groups, unreadCount: d.unreadCount || 0, realApi: true }
}

/** 学生申请（本人聚合）→ 页面 {tabs,list}；applyTime 兜底防切片崩溃。 */
export async function selfApplications() {
  const d = await realRequest('/mobile/me/applications')
  const list = (d.applications || []).map((a) => ({
    ...a, applyTime: a.applyTime || '—', eta: a.eta || '—' }))
  return { tabs: d.tabs || [], list }
}

/* ══════════ P9.2 · 教师端补齐（范围接口，替代 PC 全列表） ══════════ */

/** 教师待办：真实结构（替代 PC /todos）。 */
export async function teacherTodosReal() {
  const d = await realRequest('/mobile/teacher/todos')
  return { filters: d.filters || [], pendingCount: d.pendingCount || 0,
    list: (d.list || []).map((t) => ({ ...t, soon: false })) }
}

/** 教师风险学生：后端筛选 + 范围过滤（替代 PC /students?pageSize=100）→ 页面数组。 */
export async function teacherRiskStudents() {
  const d = await realRequest('/mobile/teacher/risk-students')
  return (d.list || []).map((r) => ({
    id: r.studentId || r.studentNo || r.id, name: r.name, studentNo: r.studentNo || '',
    className: r.className || '—', major: '', stage: (r.tags && r.tags[0]) || '在校',
    task: r.riskType + (r.reason ? '·' + r.reason : ''), risk: r.riskLevel,
    pending: 0, last: r.latestTime || '' }))
}

/** 教师·我的班级 / 我的学生（真实接口，无 mock 兜底） */
export const teacherMyClasses = () => realRequest('/mobile/teacher/my-classes')
export const teacherMyStudents = (classId) =>
  realRequest('/mobile/teacher/my-students' + (classId ? `?classId=${classId}` : ''))

/** 教师·谈心谈话（真实接口，复用既有 affairs_talk_service） */
export const teacherTalkList = (params) => {
  const q = new URLSearchParams()
  if (params && params.talkType) q.set('talkType', params.talkType)
  if (params && params.status) q.set('status', params.status)
  if (params && params.studentId) q.set('studentId', params.studentId)
  const qs = q.toString()
  return realRequest('/mobile/teacher/talk' + (qs ? '?' + qs : ''))
}
export const teacherTalkDetail = (talkId) => realRequest(`/mobile/teacher/talk/${talkId}`)
export const teacherTalkCreate = (body) => realRequest('/mobile/teacher/talk', { method: 'POST', data: body })
export const teacherTalkRecord = (talkId, body) =>
  realRequest(`/mobile/teacher/talk/${talkId}/record`, { method: 'POST', data: body })
export const teacherTalkFollowUp = (talkId, action, content) =>
  realRequest(`/mobile/teacher/talk/${talkId}/follow-up`, { method: 'POST', data: { action, content } })

/** 教师·心理关注（真实接口，严格保留既有遮蔽+授权原因红线） */
export const teacherMentalList = (level) =>
  realRequest('/mobile/teacher/mental' + (level ? `?level=${level}` : ''))
export const teacherMentalDetail = (refId, reason) =>
  realRequest(`/mobile/teacher/mental/${refId}` + (reason ? `?reason=${encodeURIComponent(reason)}` : ''))
export const teacherMentalCreate = (body) => realRequest('/mobile/teacher/mental', { method: 'POST', data: body })
export const teacherMentalFollow = (refId, content) =>
  realRequest(`/mobile/teacher/mental/${refId}/follow`, { method: 'POST', data: { content } })
export const teacherMentalEscalate = (refId, content) =>
  realRequest(`/mobile/teacher/mental/${refId}/escalate`, { method: 'POST', data: { content } })
export const teacherMentalClose = (refId, conclusion) =>
  realRequest(`/mobile/teacher/mental/${refId}/close`, { method: 'POST', data: { conclusion } })

/** 教师学生360（权限校验后）→ 页面形状；无权限/不存在由业务错抛出。 */
export async function teacherStudent360(id) {
  const d = await realRequest('/mobile/teacher/student/' + id)
  if (!d || !d.hasData) return null
  const types = []
  if (d.academicSummary && d.academicSummary.warningCount) types.push('学业预警')
  if (d.risk && d.risk.internRisk && d.risk.internRisk !== 'NONE') types.push('实习风险')
  return {
    base: { name: d.base.name, className: d.base.className || '—', major: '', stage: d.base.stage },
    risk: (d.risk && d.risk.level !== 'LOW') ? { level: d.risk.level, types, since: '' } : null,
    tags: [],
    pendingItems: (d.pendingItems || []).map((p, i) => ({ id: 'pi' + i, title: p.title, action: p.action })),
    intern: (d.internshipSummary && d.internshipSummary.hasData)
      ? { company: d.internshipSummary.enterprise, post: d.internshipSummary.position,
          mentor: '—', companyMentor: '—' } : null,
    timeline: (d.lifecycle || []).map((e, i) => ({ id: 'tl' + i, time: e.time || '',
      text: (e.stage || '') + (e.reason ? '·' + e.reason : ''), type: 'normal' }))
  }
}

/** 教师·实习批阅页 → {reports, abnormal}。 */
export async function teacherInternshipReal(mock) {
  const d = await realRequest('/mobile/teacher/internship')
  const reports = (d.weeklyReports || []).map((r) => ({
    id: String(r.id || r.reportId || ''), student: r.studentName || r.name || '',
    className: r.className || '', week: r.weekNumber ? ('第 ' + r.weekNumber + ' 周') : (r.week || ''),
    company: r.enterpriseName || r.company || '', post: r.positionName || r.post || '',
    submitTime: r.submittedAt || r.submitTime || '—', status: r.status,
    // 跨端状态文案单一来源：透传后端 statusLabel（如"待批阅/逾期未交"），与 PC 端一致，
    // 不再让移动端 MobileStatusTag 的通用映射（待审核/已逾期）与 PC 分叉。
    statusLabel: r.statusLabel || '',
    overdue: r.status === 'OVERDUE', tasks: r.workContent || '', gain: r.harvestContent || '',
    problem: r.planContent || '' }))
  const abnormal = (d.abnormalCheckins || []).map((e) => ({
    id: String(e.id || ''), student: e.studentName || e.name || '',
    time: e.exceptionDate || e.date || '', type: e.exceptionType || e.type || '异常',
    distance: e.distance || '—', note: e.note || '', status: e.status || 'PENDING_HANDLE',
    statusLabel: e.statusLabel || '' }))
  return { reports: reports.length ? reports : (mock.reports || []),
    abnormal: abnormal.length ? abnormal : (mock.abnormal || []), _real: true }
}

/** 教师·单份周报正文详情（范围安全）。
 * 列表接口 /mobile/teacher/internship 只回摘要（字数/风险/状态），正文经后端
 * get_weekly_report_detail（已做 _rec_in_scope 范围校验：非本人范围→403/404）暴露于
 * /internship/reports/{id}；该接口仅教师可访问（学生调用返回 403），故移动端教师批阅
 * 可安全按需拉取正文。理想是补 /mobile/teacher/internship/weekly/{id}（见历史欠账）。 */
export async function teacherWeeklyDetail(reportId) {
  const d = await realRequest('/internship/reports/' + reportId)
  const c = (d && d.content) || {}
  return {
    work: c.work || '', harvest: c.harvest || '', plan: c.plan || '',
    positionName: (d && d.positionName) || '', reviewComment: (d && d.reviewComment) || ''
  }
}

/** 教师·毕设指导页 → {list, reviewQueue}。reviewQueue=待批阅开题真实队列（含 proposalId，供单页队列批阅）。 */
export async function teacherGraduationReal(mock) {
  const d = await realRequest('/mobile/teacher/graduation')
  const list = (d.students || []).map((s) => ({
    id: String(s.id || ''), name: s.name || s.studentName || '', className: s.className || '',
    topic: s.topicTitle || s.topic || '（未选题）', node: s.stage || '毕设',
    status: s.status || 'PROCESSING', deadline: s.deadline || '' }))
  // 待批阅开题队列：仅真实待审(status=PENDING_REVIEW)且有数字 proposalId 的记录，供逐条批阅
  const reviewQueue = (d.reviewDetail || [])
    .filter((p) => (p.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(p.id || '')))
    .map((p) => ({ proposalId: String(p.id), gdStudentId: String(p.projectId || p.gdStudentId || ''),
      studentName: p.studentName || p.name || '', className: p.className || '',
      topicTitle: p.topicTitle || '', submitAt: p.submitAt || p.submittedAt || '',
      version: p.version || '', isResubmit: !!p.isResubmit }))
  // 待批阅成果队列：真实待审成果（含类型/版本/查重）
  const finalQueue = (d.finalDetail || [])
    .filter((f) => (f.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(f.id || '')))
    .map((f) => ({ finalId: String(f.id), gdStudentId: String(f.projectId || f.gdStudentId || ''),
      studentName: f.studentName || f.name || '', className: f.className || '',
      topicTitle: f.topicTitle || '', submitAt: f.submitAt || '', type: f.type || '',
      version: f.version || '', plagiarismRate: f.plagiarismRate || '—' }))
  return { list: list.length ? list : (mock.list || []),
    reviewQueue, finalQueue, _real: !!d.hasData || list.length > 0 }
}

/** 教师·移动端快速新增指导记录（仅本人指导学生，越权由后端 403 拦截）。 */
export const teacherGraduationGuidanceCreate = (gdStudentId, body) => gdTeacherGuidanceCreate(gdStudentId, body)

/** 教师·就业跟进页 → {stats, tabs, list, jobs}。 */
export async function teacherEmploymentReal(mock) {
  const d = await realRequest('/mobile/teacher/employment')
  const s = d.stats || {}
  const stats = { total: s.total || 0, employed: s.employed || 0, rate: s.rate || s.employmentRate || 0,
    unemployed: s.unemployed || 0, verified: s.verified || 0 }
  const list = (d.students || []).map((x) => ({
    id: String(x.id || ''), name: x.name || '', className: x.className || '',
    group: (x.destinationType && x.destinationType !== 'UNEMPLOYED') ? 'following' : 'unemployed',
    intention: x.intention || x.destinationType || '未填报', city: x.city || '—',
    company: x.companyName || '', contactTimes: x.contactTimes || 0,
    last: x.lastFollow || '', status: x.verifyStatus || 'PENDING_HANDLE' }))
  const jobs = (d.jobPool || []).map((j) => ({
    id: String(j.id || ''), company: j.companyName || j.company || '', post: j.jobTitle || j.post || '',
    salary: j.salaryRange || '—', city: j.city || '—', headcount: j.headcount || 1 }))
  return { stats: (d.stats ? stats : (mock.stats || stats)),
    tabs: mock.tabs || d.tabs || [], list: list.length ? list : (mock.list || []),
    jobs: jobs.length ? jobs : (mock.jobs || []), _real: true }
}

/** 教师消息（范围/系统）→ {tabs, groups}。 */
export async function teacherMessagesReal(mock) {
  const d = await realRequest('/mobile/teacher/messages')
  if (!d || !d.groups) return mock
  const groups = d.groups
  const tabs = (d.tabs && d.tabs.length) ? d.tabs : (mock.tabs || [])
  tabs.forEach((t) => { t.badge = (groups[t.key] || []).filter((x) => !x.read).length })
  return { tabs, groups, realApi: true }
}

/** 教师审批列表（mobile 范围）→ 页面数组。 */
export async function teacherApprovalsReal(mock) {
  const d = await realRequest('/mobile/teacher/approvals')
  const list = (d.approvals || []).map((t) => ({
    id: String(t.taskId || t.id || ''), title: t.title || '审批任务',
    type: t.sourceModule || t.sourceBizType || '审批', student: t.applicantName || '—',
    className: '', submitTime: (t.submittedAt || '').replace('T', ' ').slice(0, 16),
    status: 'PENDING_REVIEW', level: t.urgency === 'OVERDUE' ? 'high' : 'normal',
    fields: [{ label: '来源模块', value: t.sourceModule || '—' },
      { label: '当前节点', value: t.nodeName || t.nodeCode || '—' }],
    flow: [{ node: '学生提交', time: '', done: true },
      { node: t.nodeName || '审核', time: '待处理', done: false, current: true }] }))
  return list.length ? list : (mock || [])
}

// ── 13A 学工中心（P7 多端收口，学生自视图 + 自选床位；教师待办卡）──
export const affairsOverview = () => realRequest('/mobile/affairs/overview')
export const affairsLeaveMy = () => realRequest('/mobile/affairs/leave/my')
export const affairsLeaveResubmit = (leaveId, body) =>
  realRequest(`/mobile/affairs/leave/${leaveId}/resubmit`, { method: 'POST', data: body || {} })
export const affairsLeaveCancel = (leaveId, body) =>
  realRequest(`/mobile/affairs/leave/${leaveId}/cancel`, { method: 'POST', data: body || {} })
export const affairsLeaveExtend = (leaveId, body) =>
  realRequest(`/mobile/affairs/leave/${leaveId}/extension`, { method: 'POST', data: body || {} })

export const affairsAidMy = () => realRequest('/mobile/affairs/aid/my')
export const affairsAidBatches = () => realRequest('/mobile/affairs/aid/batches')
export const affairsAidApply = (body) =>
  realRequest('/mobile/affairs/aid/apply', { method: 'POST', data: body || {} })

export const affairsAidObjection = (body) =>
  realRequest('/mobile/affairs/aid/objection', { method: 'POST', data: body || {} })
export const affairsTalkMy = () => realRequest('/mobile/affairs/talk/my')
export const affairsFundingMy = () => realRequest('/mobile/affairs/funding/my')
export const affairsFundingBatches = () => realRequest('/mobile/affairs/funding/batches')
export const affairsFundingApply = (body) =>
  realRequest('/mobile/affairs/funding/apply', { method: 'POST', data: body || {} })

export const affairsFundingAppeal = (body) =>
  realRequest('/mobile/affairs/funding/appeal', { method: 'POST', data: body || {} })
export const affairsDisciplineMy = () => realRequest('/mobile/affairs/discipline/my')
export const affairsDisciplineAppeal = (body) =>
  realRequest('/mobile/affairs/discipline/appeal', { method: 'POST', data: body || {} })
export const affairsDormMy = () => realRequest('/mobile/affairs/dorm/my')
export const affairsDormOptions = () => realRequest('/mobile/affairs/dorm/select-options')
export const affairsDormSelfSelect = (bedId) =>
  realRequest(`/mobile/affairs/dorm/beds/${bedId}/self-select`, { method: 'POST', data: {} })
export const affairsDormRooms = (buildingId, floor) =>
  realRequest(`/mobile/affairs/dorm/buildings/${buildingId}/rooms${floor ? '?floor=' + floor : ''}`)
export const affairsDormBeds = (roomId) =>
  realRequest(`/mobile/affairs/dorm/rooms/${roomId}/beds`)
export const teacherAffairs = () => realRequest('/mobile/teacher/affairs')

/** 学生活动与第二课堂（真实接口，无 mock 兜底） */
export const affairsMyActivities = () => realRequest('/mobile/affairs/my-activities')
export const affairsActivityEnroll = (activityId, action) =>
  realRequest(`/mobile/affairs/activities/${activityId}/enroll`, { method: 'POST', data: { action: action || 'ENROLL' } })
export const affairsActivityCheckin = (activityId, method) =>
  realRequest(`/mobile/affairs/activities/${activityId}/checkin`, { method: 'POST', data: { method: method || 'MANUAL' } })

/** 心理健康自评（真实接口，无 mock 兜底，系统不做任何自动诊断） */
export const psySurveyQuestions = () => realRequest('/mobile/me/psy-survey/questions')
export const psySurveySubmit = (answers, wantsContact) =>
  realRequest('/mobile/me/psy-survey/submit', { method: 'POST', data: { answers, wantsContact } })
export const psySurveyHistory = () => realRequest('/mobile/me/psy-survey/history')

/** 消息通知设置（真实接口，真实过滤消息聚合，无 mock 兜底） */
export const notifyPreferences = () => realRequest('/mobile/me/notify-preferences')
export const notifySetPreference = (key, enabled) =>
  realRequest('/mobile/me/notify-preferences', { method: 'POST', data: { key, enabled } })
export const teacherNotifyPreferences = () => realRequest('/mobile/teacher/notify-preferences')
export const teacherNotifySetPreference = (key, enabled) =>
  realRequest('/mobile/teacher/notify-preferences', { method: 'POST', data: { key, enabled } })

/** 教师·发布通知（真实接口，无 mock 兜底） */
export const teacherNotifyPublish = (body) => realRequest('/mobile/teacher/notify/publish', { method: 'POST', data: body })

/** 教师·数据看板（真实接口，无 mock 兜底，复用既有 affairs_dashboard_service） */
export const teacherDashboard = () => realRequest('/mobile/teacher/dashboard')

// ── 13B 教务中心（P7 多端收口，学生自视图：课表/成绩/学籍异动/毕业进度；教师课表）──
export const acadScheduleMy = () => realRequest('/mobile/academic/schedule/my')
export const acadTranscriptMy = () => realRequest('/mobile/academic/transcript/my')
export const acadTranscriptPrint = (reason) =>
  realRequest('/mobile/academic/transcript/print', { method: 'POST', data: { reason: reason || '个人成绩单' } })
export const acadSchedulePrint = (reason) =>
  realRequest('/mobile/academic/schedule/print', { method: 'POST', data: { reason: reason || '个人课表' } })
export const acadTransferOptions = () => realRequest('/mobile/academic/transfer-options')
export const acadStatusMy = () => realRequest('/mobile/academic/status/my')
export const acadStatusChange = (body) =>
  realRequest('/mobile/academic/status-change', { method: 'POST', data: body })
export const acadGraduationMy = () => realRequest('/mobile/academic/graduation/my')
export const acadTeacherScheduleMy = () => realRequest('/mobile/academic/teacher-schedule/my')

/** 学分修读 / 学业预警 / 补考重修 / 网上选课（真实接口，无 mock 兜底，业务错误透出） */
export const acadCreditsMy = () => realRequest('/mobile/academic/credits/my')
export const acadWarningMy = () => realRequest('/mobile/academic/warning/my')
export const acadMakeupMy = () => realRequest('/mobile/academic/makeup/my')
export const acadRetakeApply = (courseName, termCode, reason) =>
  realRequest('/mobile/academic/makeup/retake-apply', { method: 'POST', data: { courseName, termCode, reason } })

export const acadExemptionApply = (courseName, termCode, reason) =>
  realRequest('/mobile/academic/makeup/exemption-apply', { method: 'POST', data: { courseName, termCode, reason } })
export const acadMakeupOptions = () => realRequest('/mobile/academic/makeup/options')
export const acadRetakeApply = (payload, termCode, reason) => {
  const data = typeof payload === 'string'
    ? { courseName: payload, termCode, reason }
    : (payload || {})
  return realRequest('/mobile/academic/makeup/retake-apply', { method: 'POST', data })
}
export const acadExemptionApply = (payload, termCode, reason) => {
  const data = typeof payload === 'string'
    ? { courseName: payload, termCode, reason }
    : (payload || {})
  return realRequest('/mobile/academic/makeup/exemption-apply', { method: 'POST', data })
}
export const acadRegistrationMy = () => realRequest('/mobile/academic/registration/my')
export const acadRegistrationRegister = (batchId) =>
  realRequest(`/mobile/academic/registration/${batchId}/register`, { method: 'POST' })
export const acadRegistrationDefer = (batchId, reason, requestedUntil) =>
  realRequest(`/mobile/academic/registration/${batchId}/defer`, { method: 'POST', data: { reason, requestedUntil } })
export const acadAttendanceMy = () => realRequest('/mobile/academic/attendance/my')
export const acadCalendarMy = () => realRequest('/mobile/academic/calendar/my')
export const acadClearanceMy = () => realRequest('/mobile/academic/clearance/my')
export const acadExamTicketPrint = (reason) =>
  realRequest('/mobile/academic/exam/ticket/print', { method: 'POST', data: { reason: reason || '个人准考证' } })
export const acadStatusChangePrint = (body) =>
  realRequest('/mobile/academic/status-change/print', { method: 'POST', data: body || {} })
export const teacherAcademicScheduleChangePending = () =>
  realRequest('/mobile/teacher/academic/schedule-changes/pending')
export const teacherAcademicScheduleChangeReview = (changeId, action, comment) =>
  realRequest(`/mobile/teacher/academic/schedule-changes/${changeId}/review`,
    { method: 'POST', data: { action, comment } })
export const teacherAcademicStatusChangePending = () =>
  realRequest('/mobile/teacher/academic/status-changes/pending')
export const teacherAcademicStatusChangeReview = (changeId, action, reason) =>

export const acadSelectionCourses = (batchId) =>
  realRequest('/mobile/academic/selection/courses' + (batchId ? `?batch_id=${batchId}` : ''))
export const acadSelectionEnroll = (selectionCourseId) =>
  realRequest('/mobile/academic/selection/enroll', { method: 'POST', data: { selectionCourseId } })
export const acadSelectionDrop = (selectionCourseId) =>
  realRequest('/mobile/academic/selection/drop', { method: 'POST', data: { selectionCourseId } })
export const acadSelectionMy = (batchId) =>
  realRequest('/mobile/academic/selection/my' + (batchId ? `?batch_id=${batchId}` : ''))
/** 成绩认定/课程替代（学生自助，对标正方 3.16/3.27） */
export const acadRecognitionMy = () => realRequest('/mobile/academic/recognition/my')
export const acadRecognitionSubmit = (body) =>
  realRequest('/mobile/academic/recognition/submit', { method: 'POST', data: body })
/** 等级考务报名（学生自助，对标正方 3.13） */
export const acadRecheckMy = () => realRequest('/mobile/academic/grade-recheck/my')
export const acadRecheckSubmit = (body) =>
  realRequest('/mobile/academic/grade-recheck/submit', { method: 'POST', data: body })
export const acadTextbookMy = () => realRequest('/mobile/academic/textbook/my')
export const acadTextbookSign = (recordId) =>
  realRequest(`/mobile/academic/textbook/${recordId}/sign`, { method: 'POST' })
export const acadLevelExamMy = () => realRequest('/mobile/academic/level-exam/my')
export const acadLevelRegister = (examId) =>
  realRequest(`/mobile/academic/level-exam/${examId}/register`, { method: 'POST' })
export const acadLevelCancel = (examId) =>
  realRequest(`/mobile/academic/level-exam/${examId}/cancel`, { method: 'POST' })
/** 专业分流志愿（学生自助） */
export const acadMajorSplitMy = () => realRequest('/mobile/academic/major-split/my')
export const acadMajorSplitSubmit = (batchId, choices) =>
  realRequest('/mobile/academic/major-split/submit', { method: 'POST', data: { batchId, choices } })
export const acadEvaluationTasks = () => realRequest('/mobile/academic/evaluation/tasks')
export const acadEvaluationSubmit = (body) =>
  realRequest('/mobile/academic/evaluation/submit', { method: 'POST', data: body })

/** 我的考试安排 + 缓考申请（考务管理·SM-10） */
export const acadExamMy = () => realRequest('/mobile/academic/exam/my')
export const acadExamDeferOptions = () => realRequest('/mobile/academic/exam/defer-options')
export const acadExamDeferMy = (status) =>
  realRequest('/mobile/academic/exam/defer/my' + (status ? `?status=${status}` : ''))
export const acadExamDeferApply = (examCourseId, reasonType, reason) =>
  realRequest('/mobile/academic/exam/defer/apply', { method: 'POST', data: { examCourseId, reasonType, reason } })
export const acadExamDeferResubmit = (deferId) =>
  realRequest(`/mobile/academic/exam/defer/${deferId}/resubmit`, { method: 'POST' })

/** 教师·成绩录入（真实接口） */
export const teacherGradeTasks = (status) =>
  realRequest('/mobile/teacher/academic/grade-tasks' + (status ? `?status=${status}` : ''))
export const teacherGradeRoster = (taskId) =>
  realRequest(`/mobile/teacher/academic/grade-tasks/${taskId}/roster`)
export const teacherGradeEnterScore = (taskId, body) =>
  realRequest(`/mobile/teacher/academic/grade-tasks/${taskId}/enter-score`, { method: 'POST', data: body })
export const teacherGradeSubmitTask = (taskId) =>
  realRequest(`/mobile/teacher/academic/grade-tasks/${taskId}/submit`, { method: 'POST' })

/** 教师·课堂考勤（真实接口） */
export const teacherAttendanceSessions = () => realRequest('/mobile/teacher/academic/attendance/sessions')
export const teacherAttendanceClassOptions = () =>
  realRequest('/mobile/teacher/academic/attendance/class-options')
export const teacherAttendanceCreate = (body) =>
  realRequest('/mobile/teacher/academic/attendance/sessions', { method: 'POST', data: body })
export const teacherAttendanceDetail = (sessionId) =>
  realRequest(`/mobile/teacher/academic/attendance/sessions/${sessionId}`)
export const teacherAttendanceMark = (sessionId, studentId, status) =>
  realRequest(`/mobile/teacher/academic/attendance/sessions/${sessionId}/mark`,
    { method: 'POST', data: { studentId, status } })
export const teacherAttendanceSubmit = (sessionId) =>
  realRequest(`/mobile/teacher/academic/attendance/sessions/${sessionId}/submit`, { method: 'POST' })
export const teacherWorkloadMy = () => realRequest('/mobile/teacher/academic/workload/my')
export const teacherWorkloadSubmit = (body) =>
  realRequest('/mobile/teacher/academic/workload/submit', { method: 'POST', data: body })
