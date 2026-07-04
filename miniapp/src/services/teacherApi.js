/** 教师端数据服务（mock）。多身份：入参 roleKey 返回对应工作台。 */
import { mockRequest } from './request'
import * as M from '@/mock'

export const teacherApi = {
  getWorkbench: (roleKey) => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor),
  getTodos: () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos }),
  getApprovals: () => mockRequest(M.approvals),
  getRiskStudents: () => mockRequest(M.students.filter((s) => s.risk === 'HIGH' || s.risk === 'MEDIUM')),
  getStudents: () => mockRequest(M.students),
  getStudent360: (id) => mockRequest(M.student360[id] || null),
  getWeeklyReports: () => mockRequest({ reports: M.weeklyReports, abnormal: M.abnormalCheckins }),
  getGdStudents: () => mockRequest({ list: M.gdStudents, detail: M.gdReviewDetail }),
  getEmployment: () => mockRequest({ stats: M.employmentStats, tabs: M.employmentTabs, list: M.employmentStudents, jobs: M.jobPool }),
  getMessages: () => mockRequest({ tabs: M.teacherMessageTabs, groups: M.teacherMessages })
}
export default teacherApi
