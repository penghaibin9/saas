/**
 * Dashboard Mock Provider（开发阶段唯一原始数据源）
 * 风险 / 学生 / 待办 / 处理记录通过 riskId、studentId、taskId、relatedRiskId 关联。
 */
import * as db from '@/mocks/db'
import { getPracticeTeachingOverview, getTeacherWorkbench } from '@/services/mock'

const delay = (ms = 200) => new Promise((r) => setTimeout(r, ms))

/** 首页展示的核心风险（至少 3 条，保留完整关联） */
function buildRiskDefinitions() {
  const onboard = db.internships.filter((i) => i.status === 'ONBOARD')
  const onboardIds = onboard.map((i) => i.studentId)

  const streakStudents = onboardIds.filter((sid) => {
    const recs = db.checkins
      .filter((c) => c.studentId === sid && c.date <= db.TODAY)
      .sort((a, b) => (a.date < b.date ? 1 : -1))
    let n = 0
    for (const r of recs) {
      if (r.status === 'ABNORMAL' || r.status === 'MISSING') n++
      else break
    }
    return n >= 3
  })

  const missingReports = onboard.filter(
    (i) =>
      !db.weeklyReports.some(
        (r) => r.studentId === i.studentId && r.week === db.CURRENT_WEEK && r.status !== 'MISSING'
      )
  )

  const gdOverdue = db.gdTasks.filter(
    (t) => !t.nodes.opening.submittedAt && t.nodes.opening.deadline < db.TODAY
  )

  const pendingTeacher = db.todos.filter(
    (t) => t.ownerType === 'teacher' && ['PENDING_HANDLE', 'PENDING_REVIEW'].includes(t.status)
  )

  return [
    {
      riskId: 'risk-checkin',
      title: '连续 3 天打卡异常',
      level: 'HIGH',
      rule: '连续 3 个工作日打卡状态为异常或未打卡',
      affectedCount: streakStudents.length,
      studentId: 'stu-001',
      responsibleTeacher: '刘强',
      relatedTaskId: 'td-101',
      status: 'pending',
      statusLabel: '待处理',
      triggeredAt: '2026-07-01 09:00',
      durationLabel: '持续 3 天',
      handleDeadline: '2026-07-03 18:00'
    },
    {
      riskId: 'risk-report',
      title: '周报未提交',
      level: 'MEDIUM',
      rule: `第 ${db.CURRENT_WEEK} 周实习周报截止日前未提交`,
      affectedCount: missingReports.length,
      studentId: 'stu-001',
      responsibleTeacher: '刘强',
      relatedTaskId: 'td-101',
      status: 'pending',
      statusLabel: '跟进中',
      triggeredAt: '2026-07-02 08:00',
      durationLabel: '逾期 1 天',
      handleDeadline: '2026-07-03 18:00'
    },
    {
      riskId: 'risk-gd',
      title: '毕设节点逾期',
      level: 'HIGH',
      rule: '开题/中期/终稿节点超过截止日期未提交',
      affectedCount: gdOverdue.length,
      studentId: 'stu-004',
      responsibleTeacher: '王芳',
      relatedTaskId: 'td-104',
      status: 'pending',
      statusLabel: '待催办',
      triggeredAt: '2026-07-01 09:00',
      durationLabel: '逾期 2 天',
      handleDeadline: '2026-07-04 18:00'
    },
    {
      riskId: 'risk-teacher',
      title: '指导教师未处理',
      level: 'MEDIUM',
      rule: '教师待办超过 24 小时未处理',
      affectedCount: pendingTeacher.filter((t) => t.priority === 'high').length,
      studentId: null,
      responsibleTeacher: '教学管理员',
      relatedTaskId: null,
      status: 'processing',
      statusLabel: '处理中',
      triggeredAt: '2026-07-02 08:00',
      durationLabel: '超 24 小时',
      handleDeadline: '2026-07-03 12:00'
    },
    {
      riskId: 'risk-foundation',
      title: '基础能力验证未完成',
      level: 'LOW',
      rule: '本学期基础能力验证项目未达标',
      affectedCount: 1,
      studentId: null,
      responsibleTeacher: '教务处',
      relatedTaskId: null,
      status: 'pending',
      statusLabel: '待启动',
      triggeredAt: '2026-06-28 10:00',
      durationLabel: '试点阶段',
      handleDeadline: '2026-07-10 18:00'
    }
  ]
}

function buildOperationLogs() {
  return [
    {
      recordId: 'rec-001',
      time: '2026-07-02 14:10',
      operator: '刘强',
      action: '发送周报补交通知',
      target: '赵一凡',
      result: '待学生确认',
      closed: false,
      riskId: 'risk-report',
      studentId: 'stu-001',
      taskId: null
    },
    {
      recordId: 'rec-002',
      time: '2026-07-02 14:30',
      operator: '刘强',
      action: '审核张明第 4 周周报',
      target: '张明',
      result: '已通过',
      closed: true,
      riskId: null,
      studentId: 'stu-005',
      taskId: 'td-102'
    },
    {
      recordId: 'rec-003',
      time: '2026-07-02 15:00',
      operator: '系统',
      action: '自动识别赵一凡打卡异常',
      target: '赵一凡',
      result: '待处理',
      closed: false,
      riskId: 'risk-checkin',
      studentId: 'stu-001',
      taskId: null
    },
    {
      recordId: 'rec-004',
      time: '2026-07-02 13:20',
      operator: '王芳',
      action: '催办王浩提交开题报告',
      target: '王浩',
      result: '已发送提醒',
      closed: false,
      riskId: 'risk-gd',
      studentId: 'stu-004',
      taskId: 'td-104'
    },
    {
      recordId: 'rec-005',
      time: '2026-07-02 11:45',
      operator: '李敏',
      action: '退回李佳就业证明材料',
      target: '李佳',
      result: '待重新上传',
      closed: false,
      riskId: null,
      studentId: 'stu-003',
      taskId: null
    }
  ]
}

function buildDataQuality() {
  return {
    baseDate: db.TODAY,
    updatedAt: '14:00',
    dataSources: ['学籍系统', '实习管理', '毕业设计', '就业台账', '考勤打卡'],
    statisticScope: '全校在籍学生（含岗位实习在岗）',
    statisticRules: '高风险口径：学生 riskLevel 为 HIGH/CRITICAL；重点关注口径：MEDIUM 及以上',
    environment: '体验环境'
  }
}

/**
 * 拉取 Dashboard 原始数据（模拟 API 响应）
 * @param {string} teacherId
 */
export async function fetchDashboardRaw(teacherId = 't-002') {
  await delay()
  const [overview, workbench] = await Promise.all([
    getPracticeTeachingOverview(),
    getTeacherWorkbench(teacherId)
  ])

  const students = db.students.slice(0, 5)

  return {
    students,
    teachers: db.teachers,
    todos: db.todos,
    risks: buildRiskDefinitions(),
    operationLogs: buildOperationLogs(),
    dataQuality: buildDataQuality(),
    overview,
    workbench,
    gdTasks: db.gdTasks,
    internships: db.internships,
    weeklyReports: db.weeklyReports,
    checkins: db.checkins,
    employments: db.employments,
    today: db.TODAY,
    currentWeek: db.CURRENT_WEEK
  }
}

const delayShort = (ms = 80) => new Promise((r) => setTimeout(r, ms))

/**
 * 模拟 POST /risks/:riskId/resolve
 * @param {string} riskId
 */
export async function resolveRiskApiMock(riskId) {
  await delayShort()
  return { success: true, riskId, status: 'resolved' }
}

/**
 * 模拟 POST /risks/:riskId/remind
 * @param {string} riskId
 */
export async function remindStudentApiMock(riskId) {
  await delayShort()
  return { success: true, riskId, status: 'processing' }
}

/**
 * 模拟 POST /tasks/:taskId/complete
 * @param {string} taskId
 */
export async function completeTaskApiMock(taskId) {
  await delayShort()
  return { success: true, taskId, status: 'done' }
}
