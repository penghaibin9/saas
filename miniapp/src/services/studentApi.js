/** 学生端数据服务：真实后端优先（主链：首页/档案/消息），其余仍 mock；失败自动回退。 */
import { mockRequest, realFirst, realFirstStrict } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const studentApi = {
  getHome: () =>
    realFirst('student.home',
      () => mockRequest(M.studentHome).then((d) => real.enrichHome(d)),
      () => mockRequest(M.studentHome)),
  getProfile: () =>
    realFirstStrict('student.profile',
      () => real.enrichProfileReal(M.studentProfile),
      () => mockRequest(M.studentProfile)),
  getOrientation: () =>
    realFirstStrict('student.orientation',
      () => real.enrichOrientation(M.studentOrientation),
      () => mockRequest(M.studentOrientation)),
  getServices: () =>
    realFirstStrict('student.campus',
      () => real.enrichCampusService({ categories: M.serviceCategories, items: M.serviceItems }),
      () => mockRequest({ categories: M.serviceCategories, items: M.serviceItems })),
  getAcademic: () =>
    realFirstStrict('student.academic',
      () => real.enrichAcademic(M.studentAcademic),
      () => mockRequest(M.studentAcademic)),
  getInternship: () =>
    realFirstStrict('student.internship',
      () => real.enrichInternship(M.studentInternship),
      () => mockRequest(M.studentInternship)),
  getGraduation: () =>
    realFirstStrict('student.graduation',
      () => real.enrichGraduation(M.studentGraduation),
      () => mockRequest(M.studentGraduation)),
  getEmployment: () =>
    realFirstStrict('student.employment',
      () => real.enrichEmployment(M.studentEmployment),
      () => mockRequest(M.studentEmployment)),
  getApplications: () =>
    realFirst('student.applications',
      () => real.selfApplications(),
      () => mockRequest({ tabs: M.applicationTabs, list: M.applications })),
  getMessages: () =>
    realFirstStrict('student.messages',
      () => real.selfMessages({ tabs: M.studentMessageTabs, groups: M.studentMessages }),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })),
  // 写操作：业务错误（401/403/409/422）透出，不兜底成成功
  submitServiceApply: (body) => real.submitServiceApply(body),
  submitWeeklyReport: (body) => real.submitWeeklyReport(body),
  submitCheckin: (body) => real.submitCheckin(body),
  markMessageRead: (id) => real.markMessageRead(id)
}
export default studentApi
