import { realRequest } from './request'

export const teacherStudent360V3Api = {
  get: (studentId) => realRequest(`/teacher-mobile/students/${encodeURIComponent(String(studentId || ''))}/projection`)
}

export default teacherStudent360V3Api
