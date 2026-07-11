/**
 * P3 · 真实后端适配层：字段映射为各 mock 契约形状，页面零结构改动。
 * 全部经 realFirst() 使用：后端挂了自动回退 mock。
 */
import { ENV } from '@/config/env'
import { realRequest, setRefreshToken, setToken } from './request'

/* 小程序角色 key → 正式演示租户真实账号（demo-school，数据只读，行级隔离）。
 * P12：演示/体验全部走真实 /api/v1/auth/login，不再调用 /auth/mock-login。 */
const ROLE_DEMO_ACCOUNT = {
  student: 'student',
  counselor: 'teacher',
  gd_mentor: 'teacher',
  intern_mentor: 'teacher',
  employment: 'admin',
  academic: 'admin',
  college_admin: 'admin'
}
const DEMO_PASSWORD = '123456' // 演示/沙箱租户公开密码（登录页明示，非机密）

export function accountOf(roleKey, side) {
  return ROLE_DEMO_ACCOUNT[roleKey] || (side === 'teacher' ? 'teacher' : 'student')
}

function _holdLogin(data) {
  setToken(data.accessToken)
  setRefreshToken(data.refreshToken || '')
  return data
}

export async function loginReal(roleKey, side) {
  const data = await realRequest('/auth/login', {
    method: 'POST',
    auth: false,
    data: { loginName: accountOf(roleKey, side), password: DEMO_PASSWORD }
  })
  return _holdLogin(data)
}

export const brand = () => realRequest('/tenant/brand')
export const me = () => realRequest('/auth/me')

const STAGE_TEXT = {
  ORIENTATION: '迎新', ON_CAMPUS: '在校', INTERNSHIP: '实习',
  GRADUATION_DESIGN: '毕设', EMPLOYMENT: '就业'
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

/** 学生首页：真实阶段 + 待办计数合入 mock 结构 */
export async function enrichHome(mockHome) {
  const ov = await realRequest('/mobile/me/overview')
  const stu = (ov && ov.student) || {}
  if (stu.stage && mockHome.stageCard) {
    mockHome.stageCard.stageText = STAGE_TEXT[stu.stage] || mockHome.stageCard.stageText
    mockHome.stageCard.title = `你正处于「${mockHome.stageCard.stageText}」阶段`
  }
  if (ov && Array.isArray(ov.todos) && mockHome.todoOverview) {
    mockHome.todoOverview.pending = ov.todos.length
  }
  if (ov && Array.isArray(ov.alerts)) mockHome.realAlerts = ov.alerts
  if (ov && Array.isArray(ov.domains)) mockHome.realDomains = ov.domains
  mockHome.realApi = true
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
    payStatus: r.paymentStatus, materialStatus: r.materialStatus,
    blocked: r.blockedStep ? { step: r.blockedStep, reason: r.blockedReason } : null,
    steps: (r.steps && r.steps.length) ? r.steps.map((s) => ({ key: s.key, status: s.status })) : mock.steps,
    _real: true }
}

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

export async function enrichInternship(mock) {
  const r = await realRequest('/mobile/internship/my')
  if (!r || !r.hasData) return { ...mock, hasBatch: false, _real: false }
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
  const out = { ...mock, hasBatch: true, company: r.enterpriseName || mock.company,
    post: r.positionName || mock.post, schoolMentor: r.advisorName || mock.schoolMentor,
    statusText: r.status, riskLevel: r.riskLevel,
    weeklyList: reports, checkinExceptions: r.attendanceExceptions || [], _real: true,
    weekly: {
      ...(mock.weekly || {}),
      week: `第 ${weekNo} 周`,
      submitted,
      lastFeedback: lastFeedback || (mock.weekly && mock.weekly.lastFeedback) || ''
    } }
  // 真实打卡状态覆盖 mock 骨架
  if (r.todayCheckin) {
    out.checkin = { ...(mock.checkin || {}), done: !!r.todayCheckin.done,
      time: r.todayCheckin.time || '', totalDays: r.todayCheckin.totalDays || 0 }
    out.status = { ...(mock.status || {}), todayCheckin: r.todayCheckin.done ? 'COMPLETED' : 'PENDING',
      weekly: submitted ? 'COMPLETED' : (mock.status && mock.status.weekly) || 'PENDING_SUBMIT' }
  }
  return out
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

export async function enrichGraduation(mock) {
  const r = await realRequest('/mobile/graduation/my')
  if (!r || !r.hasData) return { ...mock, hasBatch: false, _real: false }
  const primary = GD_PRIMARY[r.stage] || { title: '毕业设计进行中', desc: '按导师指导推进各节点', actionText: '查看', anchor: 'nodes' }
  return { ...mock, hasBatch: true, topic: r.topicTitle || mock.topic, mentor: r.advisorName || mock.mentor,
    stage: r.stage, stageLabel: r.stageLabel || '', defenseGroup: r.defenseGroup, plagiarismRate: r.plagiarismRate,
    hasTopic: !!r.topicTitle && r.topicTitle !== '（未选题）',
    // 真实覆盖 mock 骨架：批次名 / 节点进度 / 指导记录 / 当前主任务
    batch: r.batchName || r.stageLabel || mock.batch,
    nodes: (r.nodes && r.nodes.length) ? r.nodes : mock.nodes,
    guideLogs: r.guideLogs || [],
    primaryAction: primary,
    returnedNote: '',
    proposals: r.proposals || [], finals: r.finals || [], _real: true }
}

/* ══════════ 选题管理：浏览题目库 / 提交志愿 / 课题变更申请（学生自服务，真实接口，不 mock 冒充） ══════════ */

export const gdTopics = () => realRequest('/mobile/graduation/topics')
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

export async function enrichEmployment(mock) {
  const r = await realRequest('/mobile/employment/my')
  if (!r || !r.hasData) return { ...mock, _real: false }
  const dMap = { SIGNED: '签约就业', FLEXIBLE: '灵活就业', FURTHER_STUDY: '升学', ENLISTED: '入伍',
    STARTUP: '自主创业', UNEMPLOYED: '待就业' }
  return { ...mock, stageText: dMap[r.destinationType] || mock.stageText,
    destination: r.destinationType === 'SIGNED'
      ? { company: r.companyName, job: r.jobTitle } : mock.destination,
    verifyStatus: r.verifyStatus, materialStatus: r.materialStatus,
    materials: r.materials || [], followUps: r.followUps || [], _real: true }
}

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

/* 教师工作台：真实待办计数覆盖到 mock 骨架（保留 dueSoon/riskStudents 展示结构） */
export async function enrichTeacherWorkbench(mock) {
  const r = await realRequest('/mobile/teacher/overview')
  if (!r || !r.hasData) return { ...mock, _real: false }
  const realMetrics = (r.metrics || []).slice(0, 4).map((m) => ({ key: m.key, label: m.label, value: m.value }))
  return { ...mock, metrics: realMetrics.length ? realMetrics : mock.metrics,
    pendingTotal: r.pendingTotal, _real: true }
}

/* ══════════ P9.2 · 学生端补齐（档案脱敏 / 本人消息 / 我的申请 / 写操作） ══════════ */

export const submitServiceApply = (body) =>
  realRequest('/mobile/campus-service/apply', { method: 'POST', data: body })

export const submitWeeklyReport = (body) =>
  realRequest('/mobile/internship/weekly', { method: 'POST', data: body })

/** 实习每日打卡（真实落库，一天一次，409=今日已打） */
export const submitCheckin = (body) =>
  realRequest('/mobile/internship/checkin', { method: 'POST', data: body || {} })

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
export async function enrichProfileReal(mockProfile) {
  const d = await realRequest('/mobile/me/profile')
  if (!d || !d.hasData) return { ...mockProfile, _real: false }
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
    overdue: r.status === 'OVERDUE', tasks: r.workContent || '', gain: r.harvestContent || '',
    problem: r.planContent || '' }))
  const abnormal = (d.abnormalCheckins || []).map((e) => ({
    id: String(e.id || ''), student: e.studentName || e.name || '',
    time: e.exceptionDate || e.date || '', type: e.exceptionType || e.type || '异常',
    distance: e.distance || '—', note: e.note || '', status: e.status || 'PENDING_HANDLE' }))
  return { reports: reports.length ? reports : (mock.reports || []),
    abnormal: abnormal.length ? abnormal : (mock.abnormal || []), _real: true }
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
export const affairsAidMy = () => realRequest('/mobile/affairs/aid/my')
export const affairsFundingMy = () => realRequest('/mobile/affairs/funding/my')
export const affairsDisciplineMy = () => realRequest('/mobile/affairs/discipline/my')
export const affairsDormMy = () => realRequest('/mobile/affairs/dorm/my')
export const affairsDormOptions = () => realRequest('/mobile/affairs/dorm/select-options')
export const affairsDormSelfSelect = (bedId) =>
  realRequest(`/mobile/affairs/dorm/beds/${bedId}/self-select`, { method: 'POST', data: {} })
export const affairsDormRooms = (buildingId, floor) =>
  realRequest(`/mobile/affairs/dorm/buildings/${buildingId}/rooms${floor ? '?floor=' + floor : ''}`)
export const affairsDormBeds = (roomId) =>
  realRequest(`/mobile/affairs/dorm/rooms/${roomId}/beds`)
export const teacherAffairs = () => realRequest('/mobile/teacher/affairs')

// ── 13B 教务中心（P7 多端收口，学生自视图：课表/成绩/学籍异动/毕业进度；教师课表）──
export const acadScheduleMy = () => realRequest('/mobile/academic/schedule/my')
export const acadTranscriptMy = () => realRequest('/mobile/academic/transcript/my')
export const acadStatusMy = () => realRequest('/mobile/academic/status/my')
export const acadStatusChange = (body) =>
  realRequest('/mobile/academic/status-change', { method: 'POST', data: body })
export const acadGraduationMy = () => realRequest('/mobile/academic/graduation/my')
export const acadTeacherScheduleMy = () => realRequest('/mobile/academic/teacher-schedule/my')
