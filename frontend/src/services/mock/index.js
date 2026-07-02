/**
 * Mock Service 层（UI-P2）
 * - 用 Promise + 延迟模拟接口，不引入 axios、不接真实后端
 * - 所有指标经 utils/aggregate 由 mocks/db 底层数据计算，本层禁止硬编码指标
 * - 后续接真实 API 时，仅替换本层实现，store 与页面不变
 */
import * as db from '../../mocks'
import {
  aggregatePracticeTeachingMetrics,
  aggregateGraduationDesignMetrics,
  aggregateInternshipMetrics,
  aggregateEmploymentMetrics
} from '../../utils/aggregate'

const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))

const baseCtx = () => ({
  students: db.students,
  gdTasks: db.gdTasks,
  internships: db.internships,
  checkins: db.checkins,
  weeklyReports: db.weeklyReports,
  employments: db.employments,
  todos: db.todos,
  today: db.TODAY,
  currentWeek: db.CURRENT_WEEK
})

/** 学生 PC 首页数据（默认：高风险实习学生剧本） */
export async function getStudentDashboard(studentDbId = 'stu-001') {
  await delay()
  const student = db.findStudent(studentDbId)
  if (!student) throw new Error('STUDENT_NOT_FOUND')
  return {
    student,
    todos: db.todos.filter((t) => t.ownerType === 'student' && t.ownerId === studentDbId),
    messages: db.messages.filter((m) => m.toType === 'student' && m.toId === studentDbId),
    gdTask: db.gdTasks.find((t) => t.studentId === studentDbId) || null,
    internship: db.internships.find((i) => i.studentId === studentDbId) || null,
    weeklyReports: db.weeklyReports.filter((r) => r.studentId === studentDbId),
    employment: db.employments.find((e) => e.studentId === studentDbId) || null
  }
}

/** 教师工作台数据（默认：实习指导教师剧本） */
export async function getTeacherWorkbench(teacherId = 't-002') {
  await delay()
  const teacher = db.findTeacher(teacherId)
  if (!teacher) throw new Error('TEACHER_NOT_FOUND')
  const myTodos = db.todos.filter((t) => t.ownerType === 'teacher' && t.ownerId === teacherId)
  // 授权学生：毕设导师看指导毕设学生，实习导师看指导实习学生，辅导员看所带班级
  const myStudents = db.students.filter(
    (s) =>
      s.gdAdvisorId === teacherId || s.internAdvisorId === teacherId || s.counselorId === teacherId
  )
  const riskStudents = myStudents.filter((s) => ['HIGH', 'CRITICAL'].includes(s.riskLevel))
  return {
    teacher,
    identity: teacher.identities[0],
    dataScope: teacher.dataScope,
    todos: myTodos,
    students: myStudents,
    riskStudents,
    messages: db.messages.filter((m) => m.toType === 'teacher' && m.toId === teacherId)
  }
}

/** 毕业设计看板指标 + 学生进度行（行数据由底层数据关联组装，供列表展示） */
export async function getGraduationDesignMetrics() {
  await delay()
  const rows = db.gdTasks.map((t) => {
    const student = db.findStudent(t.studentId)
    const advisor = db.findTeacher(t.advisorId)
    const overdue = !t.nodes.opening.submittedAt && t.nodes.opening.deadline < db.TODAY
    return {
      id: t.id,
      student,
      title: t.title,
      batch: t.batch,
      advisorName: advisor ? advisor.name : '',
      opening: t.nodes.opening,
      midterm: t.nodes.midterm,
      final: t.nodes.final,
      openingOverdue: overdue,
      excellent: t.nodes.opening.score === '优秀'
    }
  })
  return {
    metrics: aggregateGraduationDesignMetrics(baseCtx()),
    rows,
    overdueRows: rows.filter((r) => r.openingOverdue),
    excellentRows: rows.filter((r) => r.excellent),
    updatedAt: db.TODAY
  }
}

/** 岗位实习看板指标 + 实习明细行 + 企业侧待办（行数据由底层数据关联组装） */
export async function getInternshipMetrics() {
  await delay()
  const abnormalStreakOf = (sid) => {
    const recs = db.checkins
      .filter((c) => c.studentId === sid && c.date <= db.TODAY)
      .sort((a, b) => (a.date < b.date ? 1 : -1))
    let n = 0
    for (const r of recs) {
      if (r.status === 'ABNORMAL' || r.status === 'MISSING') n++
      else break
    }
    return n
  }
  const rows = db.internships
    .filter((i) => i.status === 'ONBOARD')
    .map((i) => {
      const student = db.findStudent(i.studentId)
      const enterprise = db.findEnterprise(i.enterpriseId)
      const todayCheckin = db.checkins.find(
        (c) => c.studentId === i.studentId && c.date === db.TODAY
      )
      const weekReport = db.weeklyReports.find(
        (r) => r.studentId === i.studentId && r.week === db.CURRENT_WEEK
      )
      return {
        id: i.id,
        student,
        enterpriseName: enterprise ? enterprise.name : '',
        enterpriseRisk: enterprise ? enterprise.riskFlag : 'NORMAL',
        post: i.post,
        riskLevel: i.riskLevel,
        intendedHire: !!i.intendedHire,
        todayCheckinStatus: todayCheckin ? todayCheckin.status : 'MISSING',
        weekReportStatus: weekReport ? weekReport.status : 'MISSING',
        abnormalStreak: abnormalStreakOf(i.studentId)
      }
    })
  return {
    metrics: aggregateInternshipMetrics(baseCtx()),
    rows,
    riskRows: rows.filter(
      (r) => ['HIGH', 'CRITICAL'].includes(r.riskLevel) || r.abnormalStreak >= 3
    ),
    enterpriseTodos: db.todos.filter((t) => t.ownerType === 'enterprise'),
    updatedAt: db.TODAY
  }
}

/** 实践教学总览（驾驶舱） */
export async function getPracticeTeachingOverview() {
  await delay()
  const ctx = baseCtx()
  return {
    overview: aggregatePracticeTeachingMetrics(ctx),
    graduationDesign: aggregateGraduationDesignMetrics(ctx),
    internship: aggregateInternshipMetrics(ctx),
    employment: aggregateEmploymentMetrics(ctx),
    riskStudents: db.students.filter((s) => ['HIGH', 'CRITICAL'].includes(s.riskLevel)),
    overdueStudents: db.students.filter((s) =>
      db.gdTasks.some(
        (t) =>
          t.studentId === s.id &&
          !t.nodes.opening.submittedAt &&
          t.nodes.opening.deadline < db.TODAY
      )
    ),
    updatedAt: db.TODAY
  }
}

/** 企业导师首页数据（默认：正常企业剧本） */
export async function getEnterpriseDashboard(enterpriseId = 'ent-001') {
  await delay()
  const enterprise = db.findEnterprise(enterpriseId)
  if (!enterprise) throw new Error('ENTERPRISE_NOT_FOUND')
  const myInternships = db.internships.filter((i) => i.enterpriseId === enterpriseId)
  const authorizedStudents = myInternships
    .map((i) => ({ ...db.findStudent(i.studentId), post: i.post, intendedHire: i.intendedHire }))
    .filter((s) => s.id)
  const myReports = db.weeklyReports.filter((r) =>
    myInternships.some((i) => i.studentId === r.studentId)
  )
  return {
    enterprise,
    students: authorizedStudents, // 仅授权学生，敏感字段展示必须脱敏
    todos: db.todos.filter((t) => t.ownerType === 'enterprise' && t.ownerId === enterpriseId),
    messages: db.messages.filter((m) => m.toType === 'enterprise' && m.toId === enterpriseId),
    weeklyReports: myReports,
    // 待确认周报：学生已提交、尚未批阅的本周周报（关联学生姓名，仅授权范围内）
    pendingReports: myReports
      .filter((r) => r.status === 'SUBMITTED')
      .map((r) => ({ ...r, studentName: (db.findStudent(r.studentId) || {}).name || '' })),
    // 录用意向确认待办
    intentionTodos: db.todos.filter(
      (t) =>
        t.ownerType === 'enterprise' && t.ownerId === enterpriseId && t.title.includes('录用意向')
    )
  }
}
