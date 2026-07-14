/** 教师端数据服务：真实后端优先（主链：学生/审批/待办/消息/学生360），失败自动回退 mock。 */
import { mockRequest, realFirst, realFirstStrict } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const teacherApi = {
  getWorkbench: (roleKey) =>
    realFirstStrict('teacher.workbench',
      () => real.enrichTeacherWorkbench(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor),
      () => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor)),
  // 待办：mobile 范围接口（替代 PC /todos）
  getTodos: () =>
    realFirst('teacher.todos',
      () => real.teacherTodosReal(),
      () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
  // 审批列表：mobile 范围接口（替代通用 /approvals 全量）
  getApprovals: () =>
    realFirst('teacher.approvals',
      () => real.teacherApprovalsReal(M.approvals),
      () => mockRequest(M.approvals)),
  /** 审批操作沿用真实审批接口（数字 id）；已确认仅处理本人可见任务 */
  actApproval: (id, type, reason) => real.actApproval(id, type, reason),
  /** 教师写操作：真实后端（范围校验+审计），业务错误透出，不回退 mock */
  reviewWeekly: (id, action, comment) => real.reviewWeeklyReal(id, action, comment),
  reviewProposal: (id, action, comment) => real.reviewProposalReal(id, action, comment),
  handleWarning: (id, action, note) => real.handleWarningReal(id, action, note),
  handleCheckin: (id, action, comment) => real.handleCheckinReal(id, action, comment),
  remindWeekly: (id) => real.remindWeeklyReal(id),
  createFollowup: (body) => real.createFollowupReal(body),
  // 13A 学工待办卡 + 13B 教师课表（P7，真实优先无 mock 兜底）
  getAffairs: () => real.teacherAffairs(),
  getMySchedule: () => real.acadTeacherScheduleMy(),
  // 风险学生：后端范围过滤（不再调用 PC /students?pageSize=100）
  getRiskStudents: () =>
    realFirst('teacher.risk',
      () => real.teacherRiskStudents(),
      () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM'))),
  // getStudents 已弃用：不再打 PC 全列表；保留纯 mock 兜底以防旧引用（页面已不使用）
  getStudents: () => mockRequest(M.students),
  // 学生360：mobile 范围接口 + 权限校验（403/404 由业务错抛出，不兜底成功）
  getStudent360: (id) =>
    realFirstStrict('teacher.student360',
      () => real.teacherStudent360(id),
      () => mockRequest(M.student360[id] || null)),
  // 我的班级 / 我的学生（真实接口，无 mock 兜底）
  getMyClasses: () => real.teacherMyClasses(),
  getMyStudents: (classId) => real.teacherMyStudents(classId),
  // 实习批阅：mobile 范围真实数据
  getWeeklyReports: () =>
    realFirst('teacher.internship',
      () => real.teacherInternshipReal({ reports: M.weeklyReports, abnormal: M.abnormalCheckins }),
      () => mockRequest({ reports: M.weeklyReports, abnormal: M.abnormalCheckins })),
  // 单份周报正文（列表只回摘要，正文按需拉取，范围安全）；业务错误透出，不 mock 兜底
  getWeeklyDetail: (id) => real.teacherWeeklyDetail(id),
  // 毕设指导：mobile 范围真实数据
  getGdStudents: () =>
    realFirst('teacher.graduation',
      () => real.teacherGraduationReal({ list: M.gdStudents, detail: M.gdReviewDetail }),
      () => mockRequest({ list: M.gdStudents, detail: M.gdReviewDetail })),
  // 毕设指导：移动端快速新增指导记录（真实接口，不 mock 冒充成功）
  createGuidance: (gdStudentId, body) => real.teacherGraduationGuidanceCreate(gdStudentId, body),
  // 毕设开题：批阅前真实查看开题详情（背景/方案/成果+历史版本，范围校验）
  getGraduationProposalDetail: (id) => real.gdTeacherProposalDetail(id),
  // 毕设成果：详情 + 批阅（查重超标不可通过）
  getGraduationFinalDetail: (id) => real.gdTeacherFinalDetail(id),
  reviewFinal: (id, action, comment) => real.gdTeacherFinalReview(id, action, comment),
  // 毕设中期检查：队列 / 详情 / 结论 / 复核整改
  getGraduationMidtermQueue: () => real.gdTeacherMidtermQueue(),
  getGraduationMidtermDetail: (id) => real.gdTeacherMidtermDetail(id),
  midtermCheck: (id, conclusion, comment, deadline) => real.gdTeacherMidtermCheck(id, conclusion, comment, deadline),
  midtermRectifyReview: (id, action, comment) => real.gdTeacherMidtermRectifyReview(id, action, comment),
  // 毕设评阅：本人任务 / 提交评分+意见
  getGraduationMyReviews: () => real.gdTeacherReviewsMy(),
  submitReview: (id, score, opinion) => real.gdTeacherReviewSubmit(id, score, opinion),
  // 毕设答辩安排（只读）
  getGraduationDefenseArrangements: () => real.gdTeacherDefenseArrangements(),
  // 毕设成绩：队列 / 详情 / 复核
  getGraduationGradeQueue: () => real.gdTeacherGradeQueue(),
  getGraduationGradeDetail: (id) => real.gdTeacherGradeDetail(id),
  reviewGrade: (id, action, comment) => real.gdTeacherGradeReview(id, action, comment),
  // 就业跟进：mobile 范围真实数据
  getEmployment: () =>
    realFirst('teacher.employment',
      () => real.teacherEmploymentReal({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }),
      () => mockRequest({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool })),
  // 消息：mobile 范围接口（替代通用 /messages）
  getMessages: () =>
    realFirstStrict('teacher.messages',
      () => real.teacherMessagesReal({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }),
      () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages })),
  // 迎新·现场报到核验（真实写操作，业务错误透出，不 mock 兜底）
  orientationCheckin: (admissionNo) => real.teacherOrientationCheckin(admissionNo),
  getOrientationTodayCheckins: () => real.teacherOrientationTodayCheckins(),
  getOrientationDashboard: () => real.teacherOrientationDashboard(),
  // 指导巡访：本月计划学生列表 + 记录巡访（真实写操作，业务错误透出）
  getInternshipVisitPlans: () => real.teacherInternshipVisitPlans(),
  recordInternshipVisit: (internshipId) => real.teacherInternshipVisitRecord(internshipId),
  // 教务·成绩录入（真实接口，仅本人授课任务）
  getGradeTasks: (status) => real.teacherGradeTasks(status),
  getGradeRoster: (taskId) => real.teacherGradeRoster(taskId),
  enterGradeScore: (taskId, body) => real.teacherGradeEnterScore(taskId, body),
  submitGradeTask: (taskId) => real.teacherGradeSubmitTask(taskId),
  // 教务·课堂考勤（真实接口，移动端首创）
  getAttendanceSessions: () => real.teacherAttendanceSessions(),
  createAttendanceSession: (body) => real.teacherAttendanceCreate(body),
  getAttendanceDetail: (sessionId) => real.teacherAttendanceDetail(sessionId),
  markAttendance: (sessionId, studentId, status) => real.teacherAttendanceMark(sessionId, studentId, status),
  submitAttendanceSession: (sessionId) => real.teacherAttendanceSubmit(sessionId)
}
export default teacherApi
