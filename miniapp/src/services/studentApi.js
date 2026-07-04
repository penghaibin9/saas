/** 学生端数据服务（mock） */
import { mockRequest } from './request'
import * as M from '@/mock'

export const studentApi = {
  getHome: () => mockRequest(M.studentHome),
  getProfile: () => mockRequest(M.studentProfile),
  getOrientation: () => mockRequest(M.studentOrientation),
  getServices: () => mockRequest({ categories: M.serviceCategories, items: M.serviceItems }),
  getAcademic: () => mockRequest(M.studentAcademic),
  getInternship: () => mockRequest(M.studentInternship),
  getGraduation: () => mockRequest(M.studentGraduation),
  getEmployment: () => mockRequest(M.studentEmployment),
  getApplications: () => mockRequest({ tabs: M.applicationTabs, list: M.applications }),
  getMessages: () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })
}
export default studentApi
