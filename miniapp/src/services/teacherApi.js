/** 教师端数据服务：真实后端优先（主链：学生/审批/待办/消息/学生360），失败自动回退 mock。 */
import { mockRequest, realFirst } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const teacherApi = {
  getWorkbench: (roleKey) => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor),
  getTodos: () =>
    realFirst('teacher.todos',
      () => real.todos().then((list) => ({ filters: M.todoFilters, list })),
      () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })),
  getApprovals: () =>
    realFirst('teacher.approvals', () => real.approvals(), () => mockRequest(M.approvals)),
  /** 审批操作（真实：数字 id；mock 编号由页面本地演示） */
  actApproval: (id, type, reason) => real.actApproval(id, type, reason),
  getRiskStudents: () =>
    realFirst('teacher.risk', () => real.riskStudents(),
      () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM'))),
  getStudents: () =>
    realFirst('teacher.students', () => real.students(), () => mockRequest(M.students)),
  getStudent360: (id) =>
    /^\d+$/.test(String(id))
      ? realFirst('teacher.student360', () => real.student360(id), () => mockRequest(M.student360[id] || null))
      : mockRequest(M.student360[id] || null),
  getWeeklyReports: () => mockRequest({ reports: M.weeklyReports, abnormal: M.abnormalCheckins }),
  getGdStudents: () => mockRequest({ list: M.gdStudents, detail: M.gdReviewDetail }),
  getEmployment: () => mockRequest({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }),
  getMessages: () =>
    realFirst('teacher.messages',
      () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }).then((d) => real.enrichMessages(d)),
      () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages }))
}
export default teacherApi
