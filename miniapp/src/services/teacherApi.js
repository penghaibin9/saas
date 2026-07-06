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
  createFollowup: (body) => real.createFollowupReal(body),
  // 13A 学工待办卡（P7，真实优先无 mock 兜底）
  getAffairs: () => real.teacherAffairs(),
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
  // 实习批阅：mobile 范围真实数据
  getWeeklyReports: () =>
    realFirst('teacher.internship',
      () => real.teacherInternshipReal({ reports: M.weeklyReports, abnormal: M.abnormalCheckins }),
      () => mockRequest({ reports: M.weeklyReports, abnormal: M.abnormalCheckins })),
  // 毕设指导：mobile 范围真实数据
  getGdStudents: () =>
    realFirst('teacher.graduation',
      () => real.teacherGraduationReal({ list: M.gdStudents, detail: M.gdReviewDetail }),
      () => mockRequest({ list: M.gdStudents, detail: M.gdReviewDetail })),
  // 就业跟进：mobile 范围真实数据
  getEmployment: () =>
    realFirst('teacher.employment',
      () => real.teacherEmploymentReal({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }),
      () => mockRequest({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool })),
  // 消息：mobile 范围接口（替代通用 /messages）
  getMessages: () =>
    realFirstStrict('teacher.messages',
      () => real.teacherMessagesReal({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }),
      () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }))
}
export default teacherApi
