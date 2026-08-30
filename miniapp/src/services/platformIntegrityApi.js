import { realRequest } from './request'

export const platformIntegrityApi = {
  myFrozenPackage: () => realRequest('/mobile/student/graduation/frozen-package'),
  teacherSummary: (limit = 100) => realRequest(`/mobile/teacher/platform-integrity/summary?limit=${encodeURIComponent(limit)}`)
}

export default platformIntegrityApi
