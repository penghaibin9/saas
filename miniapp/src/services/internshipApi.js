import { realRequest } from './request'

/** 教师小程序：服务端权限 + 本人数据范围内批次上下文。 */
export const teacherInternshipContext = () =>
  realRequest('/mobile/teacher/internship/context')

/** 教师小程序：本人当前批次实习学生。batchId 为强制业务上下文。 */
export const teacherInternshipMyStudents = (batchId) => {
  const value = String(batchId || '').trim()
  if (!value) {
    return Promise.reject({ code: 'BATCH_REQUIRED', biz: true, message: '请先选择实习批次' })
  }
  return realRequest(`/mobile/teacher/internship/my-students?batchId=${encodeURIComponent(value)}`)
}
