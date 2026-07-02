/**
 * 驾驶舱指标聚合函数（V2.1 §9.2 冻结要求）
 * 所有指标必须由底层 mock/业务数据计算得出：
 *  - 改一条学生/周报/打卡记录，指标自动变化
 *  - 禁止在页面、service、store 硬编码指标值
 *  - trendQuality 必须由本层返回，前端颜色只看 trendQuality
 */

const pct = (n, d) => (d === 0 ? 0 : Math.round((n / d) * 1000) / 10)

const nowLabel = () => {
  const d = new Date()
  const p = (x) => String(x).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 构造符合 MetricCardData 契约的指标对象 */
function metric({
  id,
  title,
  value,
  unit,
  description,
  trendType = 'flat',
  trendQuality = 'neutral',
  trendLabel = '',
  drillable = false,
  drillTarget = ''
}) {
  return {
    id,
    title,
    value,
    unit,
    description,
    trendType,
    trendQuality,
    trendLabel,
    drillable,
    drillTarget,
    updatedAt: nowLabel()
  }
}

/** 比较当前值与上期值，产出趋势三元组。goodWhen: 'up' 表示上升是好事，'down' 表示下降是好事，'none' 表示中性 */
function trendOf(current, previous, goodWhen, formatDelta) {
  if (previous == null || current === previous) {
    return {
      trendType: 'flat',
      trendQuality: 'neutral',
      trendLabel: previous == null ? '' : '与上期持平'
    }
  }
  const up = current > previous
  const trendType = up ? 'up' : 'down'
  let trendQuality = 'neutral'
  if (goodWhen === 'up') trendQuality = up ? 'good' : 'bad'
  if (goodWhen === 'down') trendQuality = up ? 'bad' : 'good'
  const delta = Math.round((current - previous) * 10) / 10
  const trendLabel = formatDelta ? formatDelta(delta) : `${delta > 0 ? '+' : ''}${delta} 较上期`
  return { trendType, trendQuality, trendLabel }
}

/** 计算某学生截至 today 的连续异常打卡天数 */
import {
  isContinuousCheckinAbnormal
} from '@/modules/dashboard/rules/dashboardRiskRules.js'

/* ==================== 岗位实习指标 ==================== */
export function aggregateInternshipMetrics({
  students: _students,
  internships,
  checkins,
  weeklyReports,
  today,
  currentWeek
}) {
  const onboard = internships.filter((i) => i.status === 'ONBOARD')
  const onboardIds = onboard.map((i) => i.studentId)

  // 今日/昨日打卡率（正常打卡数 / 在岗人数）
  const rateOf = (date) => {
    const normal = checkins.filter(
      (c) => c.date === date && c.status === 'NORMAL' && onboardIds.includes(c.studentId)
    ).length
    return pct(normal, onboard.length)
  }
  const dates = [...new Set(checkins.map((c) => c.date))].sort()
  const prevDate = dates.filter((d) => d < today).pop()
  const todayRate = rateOf(today)
  const prevRate = prevDate ? rateOf(prevDate) : null

  // 本周/上周周报提交率（SUBMITTED/APPROVED/RETURNED 均计为已提交）
  const reportRate = (week) => {
    const submitted = weeklyReports.filter(
      (r) => r.week === week && r.status !== 'MISSING' && onboardIds.includes(r.studentId)
    ).length
    return pct(submitted, onboard.length)
  }
  const weekRate = reportRate(currentWeek)
  const lastWeekRate = currentWeek > 1 ? reportRate(currentWeek - 1) : null

  // 连续 3 天及以上打卡异常人数
  const streakStudents = onboardIds.filter((sid) => isContinuousCheckinAbnormal(checkins, sid, today))

  // 实习风险学生数（实习记录风险等级 HIGH / CRITICAL）
  const riskCount = onboard.filter((i) => ['HIGH', 'CRITICAL'].includes(i.riskLevel)).length

  return [
    metric({
      id: 'int-onboard',
      title: '在岗实习人数',
      value: onboard.length,
      unit: '人',
      drillable: true,
      drillTarget: 'internship-students'
    }),
    metric({
      id: 'int-checkin-rate',
      title: '今日打卡率',
      value: todayRate,
      unit: '%',
      ...trendOf(todayRate, prevRate, 'up', (d) => `${d > 0 ? '+' : ''}${d}% 较昨日`),
      drillable: true,
      drillTarget: 'checkin-list'
    }),
    metric({
      id: 'int-abnormal-streak',
      title: '连续3天打卡异常',
      value: streakStudents.length,
      unit: '人',
      trendType: streakStudents.length > 0 ? 'up' : 'flat',
      trendQuality: streakStudents.length > 0 ? 'bad' : 'neutral',
      trendLabel: streakStudents.length > 0 ? '需立即处理' : '',
      drillable: true,
      drillTarget: 'risk-students'
    }),
    metric({
      id: 'int-report-rate',
      title: '本周周报提交率',
      value: weekRate,
      unit: '%',
      ...trendOf(weekRate, lastWeekRate, 'up', (d) => `${d > 0 ? '+' : ''}${d}% 较上周`),
      drillable: true,
      drillTarget: 'weekly-reports'
    }),
    metric({
      id: 'int-risk',
      title: '实习风险学生',
      value: riskCount,
      unit: '人',
      trendType: riskCount > 0 ? 'up' : 'flat',
      trendQuality: riskCount > 0 ? 'bad' : 'neutral',
      drillable: true,
      drillTarget: 'risk-students'
    })
  ]
}

/* ==================== 毕业设计指标 ==================== */
export function aggregateGraduationDesignMetrics({ gdTasks, today }) {
  const total = gdTasks.length
  const openings = gdTasks.map((t) => t.nodes.opening)
  const submitted = openings.filter((n) => !!n.submittedAt)
  const approved = openings.filter((n) => n.status === 'APPROVED')
  const overdue = openings.filter((n) => !n.submittedAt && n.deadline < today)
  const excellent = openings.filter((n) => n.score === '优秀')
  const midtermPending = gdTasks.filter((t) => t.nodes.midterm.status === 'PENDING_REVIEW')

  const submitRate = pct(submitted.length, total)
  const approveRate = pct(approved.length, submitted.length)

  return [
    metric({
      id: 'gd-total',
      title: '毕设学生数',
      value: total,
      unit: '人',
      drillable: true,
      drillTarget: 'gd-students'
    }),
    metric({
      id: 'gd-opening-submit',
      title: '开题提交率',
      value: submitRate,
      unit: '%',
      trendType: 'flat',
      trendQuality: submitRate < 100 ? 'bad' : 'good',
      trendLabel: overdue.length ? `${overdue.length} 人逾期未交` : '全部按时提交'
    }),
    metric({
      id: 'gd-opening-approve',
      title: '开题通过率',
      value: approveRate,
      unit: '%',
      trendType: 'flat',
      trendQuality: 'neutral',
      description: '通过数 / 已提交数'
    }),
    metric({
      id: 'gd-overdue',
      title: '开题逾期未提交',
      value: overdue.length,
      unit: '人',
      trendType: overdue.length > 0 ? 'up' : 'flat',
      trendQuality: overdue.length > 0 ? 'bad' : 'neutral',
      drillable: true,
      drillTarget: 'gd-overdue-list'
    }),
    metric({
      id: 'gd-excellent',
      title: '开题优秀',
      value: excellent.length,
      unit: '人',
      trendType: excellent.length > 0 ? 'up' : 'flat',
      trendQuality: excellent.length > 0 ? 'good' : 'neutral'
    }),
    metric({
      id: 'gd-midterm-pending',
      title: '中期待批阅',
      value: midtermPending.length,
      unit: '份',
      trendType: 'flat',
      trendQuality: midtermPending.length > 0 ? 'bad' : 'neutral',
      drillable: true,
      drillTarget: 'gd-midterm-review'
    })
  ]
}

/* ==================== 毕业就业指标 ==================== */
export function aggregateEmploymentMetrics({ students, employments }) {
  const graduating = students.filter((s) => ['毕业就业', '岗位实习', '毕业设计'].includes(s.stage))
  const filled = employments.filter((e) => e.direction !== 'PENDING')
  const returned = employments.filter((e) => e.materialStatus === 'RETURNED')
  const verified = employments.filter((e) => e.materialStatus === 'VERIFIED')
  const intentions = employments.filter((e) => e.direction === 'INTENTION')

  return [
    metric({
      id: 'emp-fill-rate',
      title: '就业去向填报率',
      value: pct(filled.length, graduating.length),
      unit: '%',
      trendType: 'flat',
      trendQuality: 'neutral',
      description: '已填报 / 应填报'
    }),
    metric({
      id: 'emp-returned',
      title: '材料被退回',
      value: returned.length,
      unit: '人',
      trendType: returned.length > 0 ? 'up' : 'flat',
      trendQuality: returned.length > 0 ? 'bad' : 'neutral',
      drillable: true,
      drillTarget: 'emp-returned-list'
    }),
    metric({
      id: 'emp-verified',
      title: '材料核验通过',
      value: verified.length,
      unit: '人',
      trendType: 'flat',
      trendQuality: 'neutral'
    }),
    metric({
      id: 'emp-intention',
      title: '企业拟录用',
      value: intentions.length,
      unit: '人',
      trendType: intentions.length > 0 ? 'up' : 'flat',
      trendQuality: intentions.length > 0 ? 'good' : 'neutral',
      drillable: true,
      drillTarget: 'emp-intention-list'
    })
  ]
}

/* ==================== 实践教学总览 ==================== */
export function aggregatePracticeTeachingMetrics({
  students,
  gdTasks,
  internships,
  checkins: _checkins,
  weeklyReports,
  todos,
  today,
  currentWeek
}) {
  const riskStudents = students.filter((s) => ['HIGH', 'CRITICAL'].includes(s.riskLevel))
  const gdOverdue = gdTasks.filter(
    (t) => !t.nodes.opening.submittedAt && t.nodes.opening.deadline < today
  )
  const onboard = internships.filter((i) => i.status === 'ONBOARD')
  const pendingTodos = todos.filter(
    (t) => t.ownerType === 'teacher' && !['COMPLETED'].includes(t.status)
  )
  const onboardIds = onboard.map((i) => i.studentId)
  const weekSubmitted = weeklyReports.filter(
    (r) => r.week === currentWeek && r.status !== 'MISSING' && onboardIds.includes(r.studentId)
  ).length

  return [
    metric({
      id: 'pt-students',
      title: '在管学生总数',
      value: students.length,
      unit: '人',
      drillable: true,
      drillTarget: 'student-list'
    }),
    metric({
      id: 'pt-gd',
      title: '毕设进行中',
      value: gdTasks.length,
      unit: '人',
      trendType: 'flat',
      trendQuality: gdOverdue.length > 0 ? 'bad' : 'neutral',
      trendLabel: gdOverdue.length ? `${gdOverdue.length} 人节点逾期` : ''
    }),
    metric({
      id: 'pt-onboard',
      title: '在岗实习',
      value: onboard.length,
      unit: '人',
      trendType: 'flat',
      trendQuality: 'neutral',
      trendLabel: `本周周报已交 ${weekSubmitted}/${onboard.length}`
    }),
    metric({
      id: 'pt-risk',
      title: '风险学生',
      value: riskStudents.length,
      unit: '人',
      trendType: riskStudents.length > 0 ? 'up' : 'flat',
      trendQuality: riskStudents.length > 0 ? 'bad' : 'neutral',
      drillable: true,
      drillTarget: 'risk-students'
    }),
    metric({
      id: 'pt-teacher-todos',
      title: '教师待办',
      value: pendingTodos.length,
      unit: '项',
      trendType: 'flat',
      trendQuality: 'neutral',
      drillable: true,
      drillTarget: 'teacher-todos'
    })
  ]
}
