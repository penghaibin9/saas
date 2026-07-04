/** 学生端数据服务：真实后端优先（主链：首页/档案/消息），其余仍 mock；失败自动回退。 */
import { mockRequest, realFirst } from './request'
import * as real from './realApi'
import * as M from '@/mock'

export const studentApi = {
  getHome: () =>
    realFirst('student.home',
      () => mockRequest(M.studentHome).then((d) => real.enrichHome(d)),
      () => mockRequest(M.studentHome)),
  getProfile: () =>
    realFirst('student.profile',
      () => mockRequest(M.studentProfile).then((d) => real.enrichProfile(d)),
      () => mockRequest(M.studentProfile)),
  getOrientation: () => mockRequest(M.studentOrientation),
  getServices: () => mockRequest({ categories: M.serviceCategories, items: M.serviceItems }),
  getAcademic: () => mockRequest(M.studentAcademic),
  getInternship: () => mockRequest(M.studentInternship),
  getGraduation: () => mockRequest(M.studentGraduation),
  getEmployment: () => mockRequest(M.studentEmployment),
  getApplications: () => mockRequest({ tabs: M.applicationTabs, list: M.applications }),
  getMessages: () =>
    realFirst('student.messages',
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages }).then((d) => real.enrichMessages(d)),
      () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages }))
}
export default studentApi
