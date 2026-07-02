/**
 * Dashboard Adapter — 原始 mock/API 数据 → 领域 ViewModel
 * 接真实后端时仅修改本文件与 data provider。
 */
import { findTeacher } from '@/mocks/db'
import { HIGH_RISK_LEVELS, FOCUS_RISK_LEVELS, LATEST_LOG_LIMIT } from '../types/dashboard.types.js'

const pct = (n, d) => (d === 0 ? 0 : Math.round((n / d) * 1000) / 10)

const DEFAULT_SUGGESTIONS = [
  '联系学生确认在岗情况',
  '通知企业导师核实出勤',
  '提醒学生补交周报',
  '填写风险跟进记录'
]

const TASK_STATUS_MAP = {
  PENDING_HANDLE: 'todo',
  PENDING_REVIEW: 'doing',
  COMPLETED: 'done',
  OVERDUE: 'todo',
  RETURNED: 'doing'
}

const RISK_TYPE_MAP = {
  'risk-checkin': '岗位实习',
  'risk-report': '岗位实习',
  'risk-gd': '毕业设计',
  'risk-teacher': '教师待办',
  'risk-foundation': '基础能力验证'
}

/**
 * 输入 mock 原始数据，输出统一 dashboard state
 * @param {Awaited<ReturnType<import('../data/dashboard.mock.js').fetchDashboardRaw>>} rawData
 * @returns {import('../types/dashboard.types.js').DashboardState & { teacher: import('../types/dashboard.types.js').TeacherProfile, taskCompletionMetric: import('../types/dashboard.types.js').DashboardMetric | null }}
 */
export function normalizeDashboardData(rawData) {
  const students = adaptStudents(rawData.students, rawData.internships)
  const risks = adaptRisks(rawData.risks)
  const tasks = adaptTasks(rawData.todos, rawData.workbench.teacher.id, risks, rawData.students)
  const operationLogs = adaptOperationLogs(rawData.operationLogs)
  const lifecycleBannerStages = buildLifecycleStages(rawData, 'banner')
  const lifecycleStageCards = buildLifecycleStages(rawData, 'cards')
  const overviewMetrics = adaptMetrics(rawData.overview.overview || [])
  const gdMetrics = adaptMetrics(rawData.overview.graduationDesign || [])
  const internshipMetrics = adaptMetrics(rawData.overview.internship || [])

  const state = {
    students,
    risks,
    tasks,
    operationLogs,
    lifecycleStages: lifecycleStageCards,
    lifecycleBannerStages,
    overviewMetrics,
    gdMetrics,
    internshipMetrics,
    dataQuality: adaptDataQuality(rawData),
    teacher: {
      teacherId: rawData.workbench.teacher.id,
      name: rawData.workbench.teacher.name,
      identity:
        rawData.workbench.identity || rawData.workbench.teacher.identities?.[0] || '指导教师',
      dataScope: rawData.workbench.dataScope
    }
  }

  return state
}

/** @deprecated 使用 normalizeDashboardData */
export const adaptDashboard = normalizeDashboardData

/**
 * 根据 tasks 计算待办完成率指标（派生数据，由 store getter 调用）
 * @param {import('../types/dashboard.types.js').TeacherTask[]} tasks
 */
export function buildTaskCompletionMetric(tasks) {
  const done = tasks.filter((t) => t.status === 'done').length
  const total = tasks.length
  const rate = total ? pct(done, total) : 0
  const d = new Date()
  const p = (x) => String(x).padStart(2, '0')
  return {
    metricId: 'pt-todo-completion',
    id: 'pt-todo-completion',
    title: '待办完成率',
    value: rate,
    unit: '%',
    trendText: '+5% 较上周',
    trendType: 'up',
    trendQuality: 'good',
    trendLabel: '+5% 较上周',
    status: 'good',
    drillable: true,
    drillTarget: 'teacher-todos',
    updatedAt: `${p(d.getHours())}:${p(d.getMinutes())}`
  }
}

/**
 * 根据 students、risks、tasks 计算首页 KPI
 * @param {Pick<import('../types/dashboard.types.js').DashboardState, 'overviewMetrics'|'tasks'|'risks'|'students'> & { taskCompletionMetric?: import('../types/dashboard.types.js').DashboardMetric | null }} state
 */
export function buildDashboardMetrics(state) {
  const metrics = [...(state.overviewMetrics || [])]
  const taskCompletionMetric = state.taskCompletionMetric || buildTaskCompletionMetric(state.tasks)

  if (!metrics.some((m) => m.metricId === 'pt-todo-completion' || m.id === 'pt-todo-completion')) {
    metrics.push(taskCompletionMetric)
  }
  return metrics
}

/**
 * 根据 risks 聚合风险预警中心数据
 * @param {import('../types/dashboard.types.js').DashboardState} state
 */
export function buildRiskAlerts(state) {
  return state.risks.filter((r) => r.status !== 'resolved' && r.status !== 'ignored')
}

/**
 * 根据 tasks 按优先级和截止时间分组
 * @param {import('../types/dashboard.types.js').TeacherTask[]} tasks
 * @param {string} today
 */
export function buildTaskGroups(tasks, today) {
  const pending = tasks.filter((t) => t.status !== 'done')
  const urgent = pending.filter((t) => t.priority === 'high' || t.deadline <= today)
  const weekFocus = pending.filter((t) => t.priority === 'medium' && !urgent.includes(t))
  const deferred = pending.filter((t) => t.priority === 'low')
  return { urgent, weekFocus, deferred }
}

/** @deprecated 使用 buildTaskGroups */
export const groupTasks = buildTaskGroups

/**
 * 根据 students 生成重点学生画像
 * @param {import('../types/dashboard.types.js').DashboardState} state
 */
export function buildFocusStudents(state) {
  return filterFocusStudents(state.students)
}

/**
 * 生成生命周期阶段数据
 * @param {Awaited<ReturnType<import('../data/dashboard.mock.js').fetchDashboardRaw>>} raw
 * @param {'banner'|'cards'} mode
 */
export function buildLifecycleStages(raw, mode = 'cards') {
  if (mode === 'banner') return buildBannerStages(raw)
  return buildStageCards(raw)
}

export function filterHighRiskStudents(students) {
  return students.filter((s) => HIGH_RISK_LEVELS.includes(s.riskLevel))
}

export function filterFocusStudents(students) {
  return students.filter((s) => FOCUS_RISK_LEVELS.includes(s.riskLevel))
}

export function metricAccent(metric) {
  const id = metric.metricId || metric.id
  const warningIds = ['pt-teacher-todos', 'gd-midterm-pending', 'pt-todo-completion']
  const riskIds = ['pt-risk', 'int-abnormal-streak', 'int-risk', 'gd-overdue']
  if (warningIds.includes(id)) return 'warning'
  if (riskIds.includes(id) || metric.trendQuality === 'bad' || metric.status === 'bad')
    return 'risk'
  if (metric.trendQuality === 'good' || metric.status === 'good') return 'success'
  return 'primary'
}

export function taskStatusCode(status) {
  const map = { todo: 'PENDING_HANDLE', doing: 'PENDING_REVIEW', done: 'COMPLETED' }
  return map[status] || 'PENDING_HANDLE'
}

export function riskStatusCode(status) {
  const map = {
    pending: 'PENDING_HANDLE',
    processing: 'REVIEWING',
    resolved: 'COMPLETED',
    ignored: 'ARCHIVED'
  }
  return map[status] || 'PENDING_HANDLE'
}

export function riskStatusLabel(risk) {
  if (risk.status === 'resolved') return '已处理'
  if (risk.status === 'processing') return '处理中'
  return risk.statusLabel || '待处理'
}

/**
 * 构建抽屉展示详情
 * @param {import('../types/dashboard.types.js').RiskEvent} risk
 * @param {import('../types/dashboard.types.js').Student | null} student
 */
export function buildRiskHandleDetail(risk, student) {
  return {
    studentName: student?.name || '—',
    riskType: risk.riskType,
    riskReason: student?.lastActivity || risk.reason,
    responsibleTeacher: risk.ownerTeacher,
    deadline: risk.deadline || student?.handleDeadline || '—',
    status: riskStatusCode(risk.status),
    suggestions: risk.suggestions || student?.suggestions || DEFAULT_SUGGESTIONS
  }
}

/**
 * @param {import('../types/dashboard.types.js').TeacherTask} task
 * @param {import('../types/dashboard.types.js').Student | null} student
 * @param {string} teacherName
 */
export function buildTaskHandleDetail(task, student, teacherName) {
  return {
    studentName: task.studentName || student?.name || '—',
    riskType: task.module,
    riskReason: task.description || task.title,
    responsibleTeacher: teacherName,
    deadline: task.deadline,
    status: taskStatusCode(task.status),
    suggestions: student?.suggestions || DEFAULT_SUGGESTIONS
  }
}

/**
 * @param {import('../types/dashboard.types.js').Student} student
 * @param {boolean} resolved
 */
export function buildStudentHandleDetail(student, resolved) {
  return {
    studentName: student.name,
    riskType: student.currentStage,
    riskReason: student.lastActivity || '—',
    responsibleTeacher: student.advisorName || '—',
    deadline: student.handleDeadline || '—',
    status: resolved ? 'COMPLETED' : 'PENDING_HANDLE',
    suggestions: student.suggestions || DEFAULT_SUGGESTIONS
  }
}

function adaptStudents(rawStudents, internships) {
  const internMap = new Map(internships.map((i) => [i.studentId, i]))
  return rawStudents.map((s) => {
    const isFocus = FOCUS_RISK_LEVELS.includes(s.riskLevel)
    const advisor = s.internAdvisorId
      ? findTeacher(s.internAdvisorId)
      : s.gdAdvisorId
        ? findTeacher(s.gdAdvisorId)
        : findTeacher(s.counselorId)
    const intern = internMap.get(s.id)
    return {
      studentId: s.id,
      name: s.name,
      studentNo: s.studentId,
      college: s.college,
      major: s.major,
      className: s.className,
      phone: s.phone || '',
      currentStage: s.stage,
      riskLevel: s.riskLevel,
      avatar: s.avatar || '',
      advisorName: isFocus ? advisor?.name || '—' : undefined,
      enterpriseName: intern?.enterpriseName || intern?.company || '',
      lastActivity: s.lastActivity,
      handleDeadline: HIGH_RISK_LEVELS.includes(s.riskLevel)
        ? '2026-07-03 18:00'
        : '2026-07-05 18:00',
      suggestions: isFocus ? [...DEFAULT_SUGGESTIONS] : undefined
    }
  })
}

function adaptRisks(rawRisks) {
  return rawRisks.map((r) => ({
    riskId: r.riskId,
    studentId: r.studentId || undefined,
    riskType: RISK_TYPE_MAP[r.riskId] || '综合风险',
    riskTitle: r.title,
    riskLevel: r.level,
    reason: r.rule,
    status: r.status,
    statusLabel: r.statusLabel,
    ownerTeacher: r.responsibleTeacher,
    triggeredAt: r.triggeredAt,
    deadline: r.handleDeadline,
    durationText: r.durationLabel,
    suggestions: DEFAULT_SUGGESTIONS,
    relatedTaskIds: r.relatedTaskId ? [r.relatedTaskId] : [],
    affectedCount: r.affectedCount,
    title: r.title,
    level: r.level,
    rule: r.rule,
    responsibleTeacher: r.responsibleTeacher
  }))
}

function adaptTasks(rawTodos, teacherId, risks, rawStudents) {
  const studentMap = new Map(rawStudents.map((s) => [s.id, s]))
  const riskByTask = new Map()
  risks.forEach((r) => {
    ;(r.relatedTaskIds || []).forEach((tid) => riskByTask.set(tid, r.riskId))
  })

  return rawTodos
    .filter((t) => t.ownerType === 'teacher' && t.ownerId === teacherId)
    .map((t) => ({
      taskId: t.id,
      title: t.title,
      module: t.sourceModule,
      sourceModule: t.sourceModule,
      studentId: t.studentId,
      studentName: t.studentId ? studentMap.get(t.studentId)?.name || '' : '',
      deadline: t.deadline,
      priority: t.priority,
      status: TASK_STATUS_MAP[t.status] || 'todo',
      overdue: !!t.overdue,
      relatedRiskId: riskByTask.get(t.id),
      description: t.description || t.title
    }))
}

function adaptOperationLogs(raw) {
  return raw.map((l) => ({
    recordId: l.recordId,
    time: l.time,
    operator: l.operator,
    action: l.action,
    target: l.target || l.studentId || '',
    result: l.result,
    status: l.closed ? 'done' : 'processing',
    studentId: l.studentId || undefined,
    relatedRiskId: l.riskId || l.relatedRiskId || undefined,
    relatedTaskId: l.taskId || l.relatedTaskId || undefined,
    closed: l.closed,
    riskId: l.riskId,
    taskId: l.taskId
  }))
}

function adaptMetrics(rawMetrics) {
  return rawMetrics.map((m) => ({
    metricId: m.id || m.metricId,
    id: m.id || m.metricId,
    title: m.title,
    value: m.value,
    unit: m.unit,
    trendText: m.trendLabel || m.trendText || '',
    trendType: m.trendType,
    trendQuality: m.trendQuality,
    trendLabel: m.trendLabel,
    status: m.trendQuality || m.status,
    updatedAt: m.updatedAt,
    drillable: m.drillable,
    drillTarget: m.drillTarget
  }))
}

function adaptDataQuality(raw) {
  const dq = raw.dataQuality || {}
  return {
    baseDate: dq.baseDate || raw.overview?.updatedAt || raw.today,
    baselineDate: dq.baseDate || raw.overview?.updatedAt || raw.today,
    updatedAt: dq.updatedAt || raw.overview?.overview?.[0]?.updatedAt || '14:00',
    dataSources: dq.dataSources || ['学籍系统', '实习管理', '毕业设计', '就业台账'],
    statisticScope: dq.statisticScope || '全校在籍学生',
    statisticRules: dq.statisticRules || '按自然日汇总，高风险为 HIGH/CRITICAL 等级',
    environment: dq.environment || '体验环境'
  }
}

function buildBannerStages(raw) {
  const { students, gdTasks, internships, employments } = raw
  const onboard = internships.filter((i) => i.status === 'ONBOARD')
  const enrolled = students.length
  const employmentFilled = employments.filter((e) => e.direction !== 'PENDING').length

  return [
    {
      stageId: 'banner-enrollment',
      key: 'enrollment',
      name: '迎新完成',
      label: '迎新完成',
      status: 'done',
      completionRate: 100,
      rate: 100,
      riskCount: 0,
      detail: `${enrolled}/${enrolled} 人`,
      description: `${enrolled}/${enrolled} 人`
    },
    {
      stageId: 'banner-academic',
      key: 'academic',
      name: '在校学习',
      label: '在校学习',
      status: 'done',
      completionRate: 96,
      rate: 96,
      riskCount: 0,
      detail: '课程修读正常',
      description: '课程修读正常'
    },
    {
      stageId: 'banner-gd',
      key: 'gd',
      name: '毕业设计进行中',
      label: '毕业设计进行中',
      status: 'active',
      completionRate: pct(2, gdTasks.length),
      rate: pct(2, gdTasks.length),
      riskCount: gdTasks.filter(
        (t) => !t.nodes.opening.submittedAt && t.nodes.opening.deadline < raw.today
      ).length,
      detail: `${gdTasks.length} 人进行中`,
      description: `${gdTasks.length} 人进行中`
    },
    {
      stageId: 'banner-internship',
      key: 'internship',
      name: '岗位实习进行中',
      label: '岗位实习进行中',
      status: 'active',
      completionRate: pct(onboard.length, students.length),
      rate: pct(onboard.length, students.length),
      riskCount: 0,
      detail: `${onboard.length} 人在岗`,
      description: `${onboard.length} 人在岗`
    },
    {
      stageId: 'banner-foundation',
      key: 'foundation',
      name: '基础能力验证',
      label: '基础能力验证',
      status: 'pending',
      completionRate: 72,
      rate: 72,
      riskCount: 1,
      detail: '本学期试点',
      description: '本学期试点'
    },
    {
      stageId: 'banner-employment',
      key: 'employment',
      name: '就业归档',
      label: '就业归档',
      status: 'pending',
      completionRate: pct(employmentFilled, students.length),
      rate: pct(employmentFilled, students.length),
      riskCount: employments.filter((e) => e.materialStatus === 'RETURNED').length,
      detail: `${employmentFilled}/${students.length} 人已填报`,
      description: `${employmentFilled}/${students.length} 人已填报`
    }
  ]
}

function buildStageCards(raw) {
  const {
    internships,
    weeklyReports,
    gdTasks,
    employments,
    students,
    checkins,
    today,
    currentWeek
  } = raw
  const onboard = internships.filter((i) => i.status === 'ONBOARD')
  const onboardIds = onboard.map((i) => i.studentId)
  const weekSubmitted = weeklyReports.filter(
    (r) => r.week === currentWeek && r.status !== 'MISSING' && onboardIds.includes(r.studentId)
  ).length
  const gdOverdue = gdTasks.filter(
    (t) => !t.nodes.opening.submittedAt && t.nodes.opening.deadline < today
  )
  const streakCount = onboardIds.filter((sid) => {
    const recs = checkins
      .filter((c) => c.studentId === sid && c.date <= today)
      .sort((a, b) => (a.date < b.date ? 1 : -1))
    let n = 0
    for (const r of recs) {
      if (r.status === 'ABNORMAL' || r.status === 'MISSING') n++
      else break
    }
    return n >= 3
  }).length

  return [
    {
      stageId: 'stage-enrollment',
      key: 'enrollment',
      name: '迎新完成率',
      label: '迎新',
      status: 'done',
      cardStatus: '已完成',
      statusType: 'success',
      completionRate: 100,
      rate: 100,
      riskCount: 0,
      actionText: '查看台账',
      actionLabel: '查看台账',
      description: ''
    },
    {
      stageId: 'stage-academic',
      key: 'academic',
      name: '课程修读完成率',
      label: '在校',
      status: 'done',
      cardStatus: '稳定运行',
      statusType: 'success',
      completionRate: 96,
      rate: 96,
      riskCount: 0,
      actionText: '学籍台账',
      actionLabel: '学籍台账',
      description: ''
    },
    {
      stageId: 'stage-gd',
      key: 'gd',
      name: '毕业设计节点完成率',
      label: '毕设',
      status: 'active',
      cardStatus: '进行中',
      statusType: 'processing',
      completionRate: 67,
      rate: 67,
      riskCount: gdOverdue.length,
      actionText: '过程监测',
      actionLabel: '过程监测',
      description: ''
    },
    {
      stageId: 'stage-internship',
      key: 'internship',
      name: '岗位实习周报提交率',
      label: '实习',
      status: 'active',
      cardStatus: '进行中',
      statusType: 'processing',
      completionRate: pct(weekSubmitted, onboard.length),
      rate: pct(weekSubmitted, onboard.length),
      riskCount: streakCount,
      actionText: '实习看板',
      actionLabel: '实习看板',
      description: ''
    },
    {
      stageId: 'stage-foundation',
      key: 'foundation',
      name: '基础能力验证完成率',
      label: '验证',
      status: 'pending',
      cardStatus: '试点运行',
      statusType: 'warning',
      completionRate: 72,
      rate: 72,
      riskCount: 1,
      actionText: '验证管理',
      actionLabel: '验证管理',
      description: ''
    },
    {
      stageId: 'stage-employment',
      key: 'employment',
      name: '就业归档进度',
      label: '就业',
      status: 'pending',
      cardStatus: '填报中',
      statusType: 'processing',
      completionRate: pct(
        employments.filter((e) => e.direction !== 'PENDING').length,
        students.length
      ),
      rate: pct(employments.filter((e) => e.direction !== 'PENDING').length, students.length),
      riskCount: employments.filter((e) => e.materialStatus === 'RETURNED').length,
      actionText: '就业台账',
      actionLabel: '就业台账',
      description: ''
    }
  ]
}

export function buildLatestOperationLogs(logs, limit = LATEST_LOG_LIMIT) {
  return logs.slice(0, limit)
}
